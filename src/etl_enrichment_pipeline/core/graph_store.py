"""Neo4j graph store for schema exploration and join-path discovery.

Manages a graph of tables, columns, foreign-key relationships, and business
entities using the Neo4j async driver. Supports schema initialisation,
bulk-loading from enriched metadata, and BFS-based join-path search.
"""

from __future__ import annotations

import os
from collections import deque
from dataclasses import dataclass
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

_NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
_NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


@dataclass(frozen=True)
class JoinPath:
    """A discovered join path between tables via foreign keys."""

    tables: list[str]
    path: list[tuple[str, str, str, str]]
    hops: int


class GraphStore:
    """Neo4j-backed graph store for schema metadata.

    Usage::

        store = GraphStore()
        await store.initialize_schema()
        await store.load_schema(enriched_metadata)
        paths = await store.find_join_paths(["employee", "flight"])
        await store.close()
    """

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        self._uri = uri or _NEO4J_URI
        self._user = user or _NEO4J_USER
        self._password = password or _NEO4J_PASSWORD
        self._driver: AsyncDriver | None = None

    _CONNECTION_TIMEOUT = 5  # seconds — fail fast when Neo4j is unavailable

    async def _get_driver(self) -> AsyncDriver:
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                self._uri,
                auth=(self._user, self._password),
                connection_timeout=self._CONNECTION_TIMEOUT,
            )
        return self._driver

    async def initialize_schema(self) -> None:
        """Create uniqueness constraints for ``Table.name``, ``Column(table,name)``,
        and ``Entity.name``.

        Safe to call repeatedly — ``CREATE CONSTRAINT IF NOT EXISTS``
        is idempotent.
        """
        driver = await self._get_driver()
        async with driver.session() as session:
            await session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Table) REQUIRE t.name IS UNIQUE"
            )
            await session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Column) REQUIRE (c.table, c.name) IS UNIQUE"
            )
            await session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE"
            )

    async def load_schema(self, metadata: dict[str, Any]) -> None:
        """Load enriched metadata into the Neo4j graph.

        Processes ``tables`` → ``Table`` nodes with ``HAS_COLUMN`` → ``Column``
        nodes; ``relationships`` → ``FK_TO`` edges; ``entities`` → ``Entity``
        nodes plus ``BELONGS_TO_ENTITY`` and ``RELATED_TO`` relationships.
        """
        driver = await self._get_driver()
        async with driver.session() as session:
            # --- tables → Table nodes + HAS_COLUMN → Column nodes ---
            for tbl in metadata.get("tables", []):
                table_name = tbl["table_name"]
                await session.run(
                    (
                        "MERGE (t:Table {name: $name}) "
                        "SET t.description = $description, "
                        "    t.business_role = $business_role, "
                        "    t.domain = $domain"
                    ),
                    name=table_name,
                    description=tbl.get("description", ""),
                    business_role=tbl.get("business_role", ""),
                    domain=tbl.get("domain", ""),
                )
                for col in tbl.get("columns", []):
                    await session.run(
                        (
                            "MERGE (c:Column {table: $table, name: $name}) "
                            "SET c.data_type = $data_type, "
                            "    c.is_nullable = $is_nullable, "
                            "    c.is_primary_key = $is_primary_key, "
                            "    c.description = $description, "
                            "    c.semantic_type = $semantic_type "
                            "WITH c "
                            "MATCH (t:Table {name: $table}) "
                            "MERGE (t)-[:HAS_COLUMN]->(c)"
                        ),
                        table=table_name,
                        name=col["column_name"],
                        data_type=col.get("data_type", ""),
                        is_nullable=col.get("is_nullable", False),
                        is_primary_key=col.get("is_primary_key", False),
                        description=col.get("description", ""),
                        semantic_type=col.get("semantic_type", ""),
                    )

            # --- relationships → FK_TO edges ---
            for rel in metadata.get("relationships", []):
                # Normalise child/parent → from/to keys so Cypher params are
                # always populated regardless of how the metadata was serialised.
                from_table = rel.get("from_table") or rel.get("child_table", "")
                from_column = rel.get("from_column") or rel.get("child_column", "")
                to_table = rel.get("to_table") or rel.get("parent_table", "")
                to_column = rel.get("to_column") or rel.get("parent_column", "")
                await session.run(
                    (
                        "MATCH (from_col:Column {table: $from_table, name: $from_column}) "
                        "MATCH (to_col:Column {table: $to_table, name: $to_column}) "
                        "MERGE (from_col)-[:FK_TO]->(to_col)"
                    ),
                    from_table=from_table,
                    from_column=from_column,
                    to_table=to_table,
                    to_column=to_column,
                )

            # --- entities → Entity nodes ---
            for ent in metadata.get("entities", []):
                await session.run(
                    "MERGE (e:Entity {name: $name})",
                    name=ent["name"],
                )

            # --- BELONGS_TO_ENTITY: link tables to entities by name ---
            entity_names = {e["name"].lower(): e["name"] for e in metadata.get("entities", [])}
            for tbl in metadata.get("tables", []):
                table_name = tbl["table_name"]
                if table_name.lower() in entity_names:
                    await session.run(
                        (
                            "MATCH (t:Table {name: $table}) "
                            "MATCH (e:Entity {name: $entity}) "
                            "MERGE (t)-[:BELONGS_TO_ENTITY]->(e)"
                        ),
                        table=table_name,
                        entity=entity_names[table_name.lower()],
                    )

            # --- entity_relationships → RELATED_TO between entities ---
            for er in metadata.get("entity_relationships", []):
                await session.run(
                    (
                        "MATCH (e1:Entity {name: $entity}) "
                        "MATCH (e2:Entity {name: $related}) "
                        "MERGE (e1)-[:RELATED_TO {business_meaning: $meaning}]->(e2)"
                    ),
                    entity=er["entity"],
                    related=er["related_entities"],
                    meaning=er.get("business_meaning", ""),
                )

    async def find_join_paths(
        self,
        start_tables: list[str],
        max_hops: int = 3,
    ) -> list[JoinPath]:
        """BFS-based join-path discovery between *start_tables*.

        Traverses ``FK_TO`` relationships bidirectionally up to *max_hops*
        deep and returns all simple paths (no repeated tables) found between
        distinct table pairs in *start_tables*.

        Returns:
            List of ``JoinPath`` objects, each containing the tables visited,
            the FK-level path details, and hop count.
        """
        driver = await self._get_driver()
        async with driver.session() as session:
            result = await session.run(

                    "MATCH (c1:Column)-[r:FK_TO]->(c2:Column) "
                    "RETURN c1.table AS src_tbl, c1.name AS src_col, "
                    "       c2.table AS tgt_tbl, c2.name AS tgt_col"

            )
            fk_edges = [
                (record["src_tbl"], record["src_col"], record["tgt_tbl"], record["tgt_col"])
                async for record in result
            ]

        adj: dict[str, list[tuple[str, str, str]]] = {}
        for src_tbl, src_col, tgt_tbl, tgt_col in fk_edges:
            adj.setdefault(src_tbl, []).append((tgt_tbl, src_col, tgt_col))
            adj.setdefault(tgt_tbl, []).append((src_tbl, tgt_col, src_col))

        paths: list[JoinPath] = []
        for i, src in enumerate(start_tables):
            for tgt in start_tables[i + 1 :]:
                queue: deque[tuple[str, list[str], list[tuple[str, str, str, str]], int]] = deque()
                queue.append((src, [src], [], 0))
                while queue:
                    node, tables, path_detail, hops = queue.popleft()
                    if node == tgt:
                        paths.append(
                            JoinPath(tables=tables, path=path_detail, hops=hops)
                        )
                        continue
                    if hops >= max_hops:
                        continue
                    for neighbor, src_col, tgt_col in adj.get(node, []):
                        if neighbor not in tables:
                            new_detail = path_detail + [(node, src_col, neighbor, tgt_col)]
                            queue.append((neighbor, tables + [neighbor], new_detail, hops + 1))

        return paths

    async def close(self) -> None:
        """Close the Neo4j driver and release all connections."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None


__all__ = ["GraphStore", "JoinPath"]
