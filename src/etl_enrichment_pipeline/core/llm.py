"""LLM factory — shared across all agent nodes.

Loads ``.env`` from the project root automatically, then reads
environment variables so the provider can be swapped without
touching code::

    OPENAI_API_KEY=<key>
    OPENAI_BASE_URL=https://openrouter.ai/api/v1
    LLM_MODEL=nvidia/nemotron-3-super-120b-a12b:free

Legacy ``OPENAI_API_KEY``, ``OPENAI_BASE_URL``, and ``OPENAI_ORG_ID``
are respected for backward compatibility with the wider ecosystem.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Load .env from the project root (three levels up: core/ → pipeline/ → src/ → root)
_env_path = Path(__file__).resolve().parents[3] / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=True)

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-4o"
_DEFAULT_TIMEOUT_S = 300


def get_llm() -> ChatOpenAI:
    """Return a configured ``ChatOpenAI`` instance driven by environment variables.

    Env vars
    --------
    LLM_MODEL
        Model name (default ``gpt-4o``).
    OPENAI_API_KEY
        API key (required by the provider).
    OPENAI_BASE_URL
        Base URL for the API (defaults to OpenAI's ``https://api.openai.com/v1``).
    LLM_TIMEOUT
        Request timeout in **seconds** (default ``300``).

    A ``.env`` file in the project root is loaded automatically.
    See ``.env.template`` for available provider presets.
    """
    model = os.getenv("LLM_MODEL", _DEFAULT_MODEL)
    timeout = float(os.getenv("LLM_TIMEOUT", str(_DEFAULT_TIMEOUT_S)))
    base_url = os.getenv("OPENAI_BASE_URL")

    logger.debug(
        "LLM config: model=%s base_url=%s timeout=%.0fs",
        model,
        base_url or "(OpenAI default)",
        timeout,
    )

    kwargs: dict = {
        "model": model,
        "temperature": 0,
        "timeout": timeout,
        "max_retries": 1,
    }
    if base_url:
        kwargs["base_url"] = base_url

    return ChatOpenAI(**kwargs)


__all__ = ["get_llm"]
