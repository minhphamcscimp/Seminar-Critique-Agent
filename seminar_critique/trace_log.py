"""Per-run JSONL audit trace. A context variable isolates concurrent runs."""
from __future__ import annotations

import json
import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


@dataclass
class RunLog:
    run_id: str
    events: list[dict[str, Any]] = field(default_factory=list)


_ACTIVE: ContextVar[RunLog | None] = ContextVar("active_run_log", default=None)


def make_run_id(task_id: str, config: str, run: int) -> str:
    """Produce a predictable filename-safe identifier shared by CSV and trace."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", task_id):
        raise ValueError("task id must contain only ASCII letters, numbers, - or _")
    return f"{task_id}-{config}-run{run}"


@contextmanager
def log_session(run_id: str) -> Iterator[RunLog]:
    log = RunLog(run_id)
    token = _ACTIVE.set(log)
    try:
        yield log
    finally:
        _ACTIVE.reset(token)


def emit(event: str, **fields: Any) -> None:
    log = _ACTIVE.get()
    if log is not None:
        log.events.append({
            "run_id": log.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **fields,
        })


def write_jsonl(log: RunLog, out_dir: str, config: str) -> str:
    folder = Path(out_dir) / config
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{log.run_id}.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for entry in log.events:
            handle.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    return str(path)
