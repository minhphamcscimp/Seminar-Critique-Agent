"""Tool registry with an allowlist. Owner: Tin.

Every tool is registered with a permission level. Only allowlisted tools can be called,
and only READ_ONLY tools are allowed to run. Other permissions are rejected.
This is the code-level guarantee the report (Section 3, R2 and Section 6) points to.

Every call, allowed or blocked, writes one line to the audit log
(`seminar_critique/security/audit.py`): time, run_id, agent, tool, arguments,
decision and reason.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Callable

from ..security.audit import ALLOWED, BLOCKED, record_tool_call
from .benchmark_lookup import lookup_benchmark


class Permission(str, Enum):
    READ_ONLY = "read_only"
    WRITE_REVERSIBLE = "write_reversible"
    WRITE_IRREVERSIBLE = "write_irreversible"
    CODE_EXECUTION = "code_execution"


# name -> (function, permission level). Add new tools here and nowhere else.
TOOL_REGISTRY: dict[str, tuple[Callable[..., Any], Permission]] = {
    "lookup_benchmark": (lookup_benchmark, Permission.READ_ONLY),
}

# Only these may be called by agents. Keep it minimal.
ALLOWED_PERMISSIONS = {Permission.READ_ONLY}


def call_tool(tool_name: str, /, **kwargs: Any) -> dict:
    """Call a registered tool, or raise PermissionError. Always writes one audit line.

    tool_name is positional-only so a tool argument may also be called `name`.
    """
    if tool_name not in TOOL_REGISTRY:
        reason = f"tool not registered: {tool_name}"
        record_tool_call(tool_name, kwargs, BLOCKED, reason, outcome="PermissionError")
        raise PermissionError(reason)
    fn, level = TOOL_REGISTRY[tool_name]
    if level not in ALLOWED_PERMISSIONS:
        reason = f"tool {tool_name} needs permission {level.value}, which is blocked"
        record_tool_call(
            tool_name, kwargs, BLOCKED, reason, permission=level.value, outcome="PermissionError"
        )
        raise PermissionError(reason)
    reason = f"registered, permission {level.value} is allowlisted"
    try:
        result = fn(**kwargs)
    except Exception as exc:
        # The gate allowed the call but the tool refused it (bad arguments, broken
        # data file). Log it and let the error reach the caller unchanged.
        record_tool_call(
            tool_name, kwargs, ALLOWED, reason, permission=level.value,
            outcome=f"error: {type(exc).__name__}",
        )
        raise
    found = result.get("found") if isinstance(result, dict) else None
    record_tool_call(
        tool_name, kwargs, ALLOWED, reason, permission=level.value, outcome="ok",
        found=found if isinstance(found, bool) else None,
    )
    return {"tool": tool_name, "args": kwargs, "result": result}
