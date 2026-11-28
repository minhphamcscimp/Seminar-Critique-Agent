"""R1 (D3): the benchmark tool must give external evidence for most eval tasks."""
from pathlib import Path

from seminar_critique.orchestrator import _lookup_benchmarks
from seminar_critique.schemas import Task

TASK_DIR = Path(__file__).resolve().parents[1] / "eval" / "tasks"
TASKS = [Task.from_json(str(path)) for path in sorted(TASK_DIR.glob("*.json"))]
# Survey without a results table of its own: no record, by design (see tools/README.md).
NO_OWN_TABLE = {"kamoi2024"}


def _found(task: Task) -> list[dict]:
    return [c["result"] for c in _lookup_benchmarks(task) if c["result"].get("found")]


def test_at_least_half_of_the_tasks_get_benchmark_evidence():
    covered = [t.id for t in TASKS if _found(t)]
    assert len(TASKS) >= 24
    assert len(covered) / len(TASKS) >= 0.5


def test_every_task_of_a_paper_with_a_results_table_gets_evidence():
    missing = [t.id for t in TASKS if t.paper not in NO_OWN_TABLE and not _found(t)]
    assert missing == []


def test_new_papers_get_their_own_records_not_another_papers():
    # Huang et al. and ReAct share HotpotQA/GSM8K with CRITIC (one record per pair).
    shared = {"huang2024", "yao2023"}
    for task in TASKS:
        if task.paper in shared or task.paper in NO_OWN_TABLE:
            continue
        assert {r["paper"] for r in _found(task)} == {task.paper}, task.id
