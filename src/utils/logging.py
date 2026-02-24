"""JSONL execution logger — one line per event, appended to logs/execution_{run_id}.jsonl."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

from src.config import get_settings


def _get_logger(name: str = "agent") -> logging.Logger:
    settings = get_settings()
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, settings.log_level, logging.INFO))
    return logger


log = _get_logger()


class ExecutionLogger:
    """Append-only JSONL logger for a single agent run."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        settings = get_settings()
        self._path = settings.logs_dir / f"execution_{run_id}.jsonl"
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, event: dict[str, Any]) -> None:
        event.setdefault("run_id", self.run_id)
        event.setdefault("ts", time.time())
        try:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, default=str) + "\n")
        except OSError as exc:
            log.warning("Failed to write execution log: %s", exc)

    def node_start(self, node: str, state_keys: Optional[list[str]] = None) -> None:
        self._write({"event": "node_start", "node": node, "state_keys": state_keys or []})

    def node_end(
        self,
        node: str,
        duration_ms: float,
        output_keys: Optional[list[str]] = None,
        error: Optional[str] = None,
    ) -> None:
        self._write(
            {
                "event": "node_end",
                "node": node,
                "duration_ms": round(duration_ms, 2),
                "output_keys": output_keys or [],
                "error": error,
            }
        )

    def search_event(self, api: str, query_id: str, result_count: int, latency_ms: float, success: bool) -> None:
        self._write(
            {
                "event": "search",
                "api": api,
                "query_id": query_id,
                "result_count": result_count,
                "latency_ms": round(latency_ms, 2),
                "success": success,
            }
        )

    def error(self, node: str, message: str, exc: Optional[Exception] = None) -> None:
        self._write(
            {
                "event": "error",
                "node": node,
                "message": message,
                "exc_type": type(exc).__name__ if exc else None,
            }
        )

    def summary(
        self,
        persona_id: str,
        overall_risk: str,
        flag_count: int,
        report_path: str,
        langsmith_url: Optional[str] = None,
    ) -> None:
        self._write(
            {
                "event": "summary",
                "persona_id": persona_id,
                "overall_risk": overall_risk,
                "flag_count": flag_count,
                "report_path": report_path,
                "langsmith_url": langsmith_url,
            }
        )
