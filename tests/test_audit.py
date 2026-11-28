"""Audit log of tool calls (D3, Tin). Offline; no API key needed."""
import json
import threading

import pytest

from seminar_critique.configs import CONFIGS
from seminar_critique.llm import FakeLLM
from seminar_critique.orchestrator import run_pipeline
from seminar_critique.schemas import Task
from seminar_critique.security import audit
from seminar_critique.security.audit import MAX_ARG_CHARS, audit_run, read_audit
from seminar_critique.tools import Permission, TOOL_REGISTRY, call_tool

FIELDS = {"timestamp", "run_id", "agent", "tool", "args", "permission", "decision",
          "reason", "outcome"}


def test_allowed_call_writes_one_line_with_every_field(_audit_log_in_tmp):
    with audit_run("t-A-r0", agent="critic") as records:
        call_tool("lookup_benchmark", name="GSM8K", metric="accuracy")
    lines = read_audit(_audit_log_in_tmp)
    assert lines == records and len(lines) == 1
    line = lines[0]
    assert FIELDS <= set(line)
    assert line["run_id"] == "t-A-r0" and line["agent"] == "critic"
    assert line["tool"] == "lookup_benchmark"
    assert line["args"] == {"name": "GSM8K", "metric": "accuracy"}
    assert line["decision"] == "allowed" and line["permission"] == "read_only"
    assert line["outcome"] == "ok" and line["found"] is True


def test_unknown_tool_is_blocked_and_logged(_audit_log_in_tmp):
    with audit_run("attack-x"):
        with pytest.raises(PermissionError):
            call_tool("write_file", path=".env", content="x")
    (line,) = read_audit(_audit_log_in_tmp)
    assert line["decision"] == "blocked"
    assert "not registered" in line["reason"]
    assert line["run_id"] == "attack-x" and line["tool"] == "write_file"


@pytest.mark.parametrize("permission", [
    Permission.WRITE_REVERSIBLE, Permission.WRITE_IRREVERSIBLE, Permission.CODE_EXECUTION,
])
def test_non_read_only_tool_is_blocked_before_running_and_logged(
    monkeypatch, _audit_log_in_tmp, permission
):
    ran = []
    monkeypatch.setitem(TOOL_REGISTRY, "dangerous", (lambda: ran.append(1), permission))
    with pytest.raises(PermissionError):
        call_tool("dangerous")
    assert ran == []
    (line,) = read_audit(_audit_log_in_tmp)
    assert line["decision"] == "blocked"
    assert line["permission"] == permission.value
    assert "blocked" in line["reason"]


def test_tool_error_is_logged_as_allowed_with_error_outcome(_audit_log_in_tmp):
    with pytest.raises(TypeError):
        call_tool("lookup_benchmark", name="GSM8K", metric="accuracy", path="/etc/passwd")
    (line,) = read_audit(_audit_log_in_tmp)
    assert line["decision"] == "allowed" and line["outcome"] == "error: TypeError"
    assert line["args"]["path"] == "/etc/passwd"


def test_long_or_injected_arguments_are_bounded_and_stay_one_json_line(_audit_log_in_tmp):
    payload = "x\n}{" * MAX_ARG_CHARS
    call_tool("lookup_benchmark", name=payload, metric="accuracy")
    text = _audit_log_in_tmp.read_text(encoding="utf-8")
    assert text.count("\n") == 1
    line = json.loads(text)
    assert len(line["args"]["name"]) <= MAX_ARG_CHARS + len("...[cut]")
    assert line["run_id"] is None and line["found"] is False


@pytest.mark.parametrize("config,expected_calls", [("A", 0), ("B", None), ("C", None)])
def test_every_pipeline_tool_call_has_an_audit_line(_audit_log_in_tmp, config, expected_calls):
    task = Task(id="audit", topic="tool-use-mcp", input="Yao et al. (2023) propose ReAct.")
    with audit_run(f"audit-{config}-r0") as records:
        result = run_pipeline(task, CONFIGS[config], FakeLLM())
    critic_calls = [c for s in result.trace if s.agent == "critic" for c in s.tool_calls]
    # The trace keeps only the records that were found; the audit log keeps every call.
    if expected_calls == 0:
        assert records == [] and critic_calls == []
    else:
        assert len(records) >= len(critic_calls) > 0
        assert all(r["run_id"] == f"audit-{config}-r0" for r in records)
        assert all(r["decision"] == "allowed" for r in records)
        assert sum(r.get("found") is True for r in records) == len(critic_calls)


def test_run_id_reaches_a_tool_called_from_a_worker_thread(_audit_log_in_tmp):
    """A timeout wrapper may run the tool in a thread, which drops context variables."""
    with audit_run("threaded-r0") as records:
        worker = threading.Thread(
            target=call_tool, args=("lookup_benchmark",),
            kwargs={"name": "GSM8K", "metric": "accuracy"},
        )
        worker.start()
        worker.join()
    assert [r["run_id"] for r in records] == ["threaded-r0"]


def test_unwritable_audit_log_fails_the_call(monkeypatch, tmp_path):
    folder = tmp_path / "dir_not_file"
    folder.mkdir()
    monkeypatch.setenv(audit.AUDIT_PATH_ENV, str(folder))  # a directory cannot be appended to
    with pytest.raises(OSError):
        call_tool("lookup_benchmark", name="GSM8K", metric="accuracy")


def test_eval_runner_rows_and_audit_lines_share_the_run_id(_audit_log_in_tmp, tmp_path):
    from eval.runner import run_one

    task = Task(id="audit-runner", topic="tool-use-mcp", input="Yao et al. (2023) propose ReAct.")
    row = run_one(task, "B", 0, FakeLLM(), "fake", str(tmp_path / "traces"))
    lines = read_audit(_audit_log_in_tmp)
    assert lines and {line["run_id"] for line in lines} == {row["run_id"]}
