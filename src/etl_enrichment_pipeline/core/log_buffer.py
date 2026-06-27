"""In-memory ring-buffer log handler — replaces the file-based pipeline log.

Usage:
    from etl_enrichment_pipeline.core.log_buffer import buffer

    # Attach to any logger
    logger.addHandler(buffer)

    # Retrieve logs via the shared singleton
    buffer.get_logs(lines=100, level="INFO")
"""

from __future__ import annotations

import logging
from collections import deque

__all__ = ["BufferedLogHandler", "buffer"]


class BufferedLogHandler(logging.Handler):
    """Log handler that stores records in a fixed-capacity ring buffer.

    Each record is stored as a ``(levelno, formatted_text)`` tuple so that
    retrieval can filter by severity level without needing the original
    ``LogRecord`` object.
    """

    def __init__(self, capacity: int = 5000) -> None:
        super().__init__(level=logging.NOTSET)
        self._buffer: deque[tuple[int, str]] = deque(maxlen=capacity)
        self.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    def emit(self, record: logging.LogRecord) -> None:
        """Format and store a single log record."""
        try:
            self._buffer.append((record.levelno, self.format(record)))
        except Exception:
            self.handleError(record)

    # ── public API ─────────────────────────────────────────────

    @property
    def capacity(self) -> int:
        return self._buffer.maxlen

    def get_logs(
        self,
        lines: int = 200,
        level: str = "DEBUG",
    ) -> list[str]:
        """Return the *last* ``lines`` entries at-or-above *level*.

        Parameters
        ----------
        lines:
            Maximum number of log lines to return (most recent first).
        level:
            Minimum logging level name (e.g. ``"DEBUG"``, ``"INFO"``,
            ``"WARNING"``).
        """
        min_level = getattr(logging, level.upper(), logging.DEBUG)
        filtered = [msg for lvl, msg in self._buffer if lvl >= min_level]
        # Return the *last* ``lines`` entries
        return filtered[-lines:]


# Shared singleton — import this everywhere a log endpoint needs it.
buffer = BufferedLogHandler()
