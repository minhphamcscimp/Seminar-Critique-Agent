"""Audit log for tool calls. Owner: Tin.

Every call that goes through `tools.call_tool` writes exactly one JSON line:
time, run_id, agent, tool, arguments, decision (allowed / blocked) and the reason.
Blocked calls are logged before the PermissionError is raised, so a refused call
always leaves evidence. A call whose tool raises (bad arguments, broken data file)
is logged as allowed with `outcome: error`.

Where the lines go:
    - `traces/audit.jsonl` under the repository root by default (traces/ is not
      committed), or the path in the SEMINAR_AUDIT_LOG environment variable;
    - plus the in-memory list of the innermost `audit_run(...)` block, so the attack
      harness and the tests can read the lines of one run.

`audit_run(run_id, agent=...)` sets the run id that links an audit line to the trace
of the same run (eval/runner.py and security/run_attacks.py use the same id in the
trace file). Outside such a block `run_id` is null; the line is still written.

If the line cannot be written the call fails: an audit log that silently drops
lines is worse than a failed run (fail closed).
"""
from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDIT_PATH = REPO_ROOT / "traces" / "audit.jsonl"
AUDIT_PATH_ENV = "SEMINAR_AUDIT_LOG"
MAX_ARG_CHARS = 300  # arguments may carry injected text; keep the log line bounded

ALLOWED = "allowed"
BLOCKED = "blocked"


@dataclass
class _Session:
    run_id: str | None
    agent: str
    path: Path | None
    records: list[dict[str, Any]] = field(default_factory=list)


_SESSION: ContextVar[_Session | None] = ContextVar("audit_session", default=None)
# A tool may run in a worker thread (for example a timeout wrapper). New threads do
# not inherit context variables, so keep the outermost session as a fallback too.
_FALLBACK: list[_Session] = []
_LOCK = threading.Lock()


def audit_path() -> Path:
    """File the audit lines are appended to (env var wins over the default)."""
    return Path(os.environ.get(AUDIT_PATH_ENV) or DEFAULT_AUDIT_PATH)


def _current() -> _Session | None:
    session = _SESSION.get()
    if session is not None:
        return session
    with _LOCK:
        return _FALLBACK[-1] if _FALLBACK else None


@contextmanager
def audit_run(
    run_id: str | None, agent: str = "orchestrator", path: str | Path | None = None
) -> Iterator[list[dict[str, Any]]]:
    """Attach run_id/agent to every tool call inside the block; yield its records.

    `agent` names the caller. In this pipeline Python code in the orchestrator
    selects and calls the tool (for the Critic and Reflection agents); no LLM
    output is executed as a tool call, so the default caller is "orchestrator".
    """
    session = _Session(run_id, agent, Path(path) if path else None)
    token = _SESSION.set(session)
    with _LOCK:
        _FALLBACK.append(session)
    try:
        yield session.records
    finally:
        _SESSION.reset(token)
        with _LOCK:
            _FALLBACK.remove(session)


def _bounded(value: Any) -> Any:
    """JSON-safe copy of a tool argument, cut to MAX_ARG_CHARS when it is text."""
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    text = value if isinstance(value, str) else repr(value)
    return text if len(text) <= MAX_ARG_CHARS else text[:MAX_ARG_CHARS] + "...[cut]"


def record_tool_call(
    tool: str,
    args: dict[str, Any],
    decision: str,
    reason: str,
    *,
    permission: str | None = None,
    outcome: str = "",
    found: bool | None = None,
) -> dict[str, Any]:
    """Write one audit line and return it. Raises OSError if it cannot be written."""
    if decision not in (ALLOWED, BLOCKED):
        raise ValueError(f"decision must be {ALLOWED!r} or {BLOCKED!r}")
    session = _current()
    line: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "run_id": session.run_id if session else None,
        "agent": session.agent if session else "unknown",
        "tool": _bounded(tool),
        "args": {str(k): _bounded(v) for k, v in args.items()},
        "permission": permission,
        "decision": decision,
        "reason": reason,
        "outcome": outcome,
    }
    if found is not None:
        line["found"] = found
    path = session.path if session and session.path else audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK, path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    if session is not None:
        session.records.append(line)
    return line


def read_audit(path: str | Path | None = None) -> list[dict[str, Any]]:
    """All lines of an audit file (missing file = no lines)."""
    file = Path(path) if path else audit_path()
    if not file.exists():
        return []
    with file.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]
