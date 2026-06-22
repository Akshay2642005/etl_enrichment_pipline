#!/usr/bin/env python3
"""ETL Enrichment Pipeline — CLI entry point.

This file is a thin wrapper. The extraction logic has moved to::

    src/etl_enrichment_pipeline/agents/extraction_agent.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is on the path for direct python invocations
_src = str(Path(__file__).resolve().parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)


def main() -> None:
    from etl_enrichment_pipeline.agents.extraction_agent import main as extract_main

    extract_main()


if __name__ == "__main__":
    main()
