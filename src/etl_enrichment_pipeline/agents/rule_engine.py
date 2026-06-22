"""YAML-driven rule-based classification engine."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from etl_enrichment_pipeline.rules import RULES_DIR


class RuleEngine(BaseModel):
    """YAML-driven rule-based classification engine.

    Loads rules from YAML files and applies them without LLM calls.
    Covers: PII detection, audit patterns, soft delete, common semantic types.
    """
    rules_dir: str = ""

    # Private state initialized in model_post_init
    _pii_rules: list[dict[str, Any]] = []
    _semantic_rules: list[dict[str, Any]] = []

    def model_post_init(self, context: Any = None) -> None:
        """Initialize internal state after model fields are set."""
        self._pii_rules = []
        self._semantic_rules = []
        self.load_rules()

    # ------------------------------------------------------------------
    # Rule loading
    # ------------------------------------------------------------------

    def load_rules(self) -> None:
        """Load PII and semantic type rules from YAML files in *rules_dir*.

        If *rules_dir* is empty, it defaults to
        ``etl_enrichment_pipeline.rules.RULES_DIR``.
        """
        resolved = Path(self.rules_dir) if self.rules_dir else RULES_DIR

        pii_path = resolved / "pii_rules.yaml"
        if pii_path.is_file():
            with pii_path.open(encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            self._pii_rules = data.get("pii_columns", [])

        sem_path = resolved / "semantic_type_rules.yaml"
        if sem_path.is_file():
            with sem_path.open(encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            self._semantic_rules = data.get("semantic_types", [])

    # ------------------------------------------------------------------
    # Pattern matching helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _looks_like_regex(pattern: str) -> bool:
        """Return ``True`` when *pattern* contains regex metacharacters."""
        regex_chars = set(r"|.*+?^$()[]{}")
        return any(c in regex_chars for c in pattern)

    @staticmethod
    def _match(pattern: str, column_name: str) -> bool:
        """Case-insensitive match of *pattern* against *column_name*.

        * If *pattern* looks like a regex (contains metacharacters) it is
          compiled and matched via ``re.search``.
        * Otherwise a simple ``in`` substring check is used.
        """
        if RuleEngine._looks_like_regex(pattern):
            return bool(re.search(pattern, column_name, re.IGNORECASE))
        return pattern.lower() in column_name.lower()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, column_name: str, data_type: str) -> dict[str, Any]:
        """Classify a column using PII rules first, then semantic rules.

        Returns a dict with keys ``classification`` (``str | None``) and
        ``confidence`` (``float``).
        """
        # 1. PII rules (use confidence from YAML)
        for rule in self._pii_rules:
            if self._match(rule["pattern"], column_name):
                return {
                    "classification": rule["classification"],
                    "confidence": rule["confidence"],
                }

        # 2. Semantic type rules (default confidence 0.85)
        for rule in self._semantic_rules:
            if self._match(rule["pattern"], column_name):
                return {
                    "classification": rule["type"],
                    "confidence": 0.85,
                }

        return {"classification": None, "confidence": 0.0}

    def classify_column_semantic(self, column_name: str) -> dict[str, Any]:
        """Classify a column using semantic type rules only (no PII check).

        Returns a dict with keys ``classification`` (``str | None``) and
        ``confidence`` (``float``).
        """
        for rule in self._semantic_rules:
            if self._match(rule["pattern"], column_name):
                return {
                    "classification": rule["type"],
                    "confidence": 0.85,
                }

        return {"classification": None, "confidence": 0.0}
