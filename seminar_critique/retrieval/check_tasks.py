"""Check retrieve() on every eval task. Owner: Minh.

For each task in eval/tasks/*.json:
    - run retrieve() with the SAME query the orchestrator uses (first 200 characters
      of task.input, see orchestrator.run_pipeline),
    - find the paper under critique from the "Surname et al." mention in task.input,
    - report whether the top-k contains at least one chunk of that paper, and at which rank,
      for BM25 + graph (what configs B and C use) and for BM25 only (ablation).

    python -m seminar_critique.retrieval.check_tasks
    python -m seminar_critique.retrieval.check_tasks -k 5 --out seminar_critique/retrieval/task_check.json

Misses are not errors: they are the "wrong retrieval" examples for report Section 3 (R3).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .retriever import DEFAULT_K, get_index, retrieve_with

TASKS_DIR = Path(__file__).resolve().parents[2] / "eval" / "tasks"
QUERY_CHARS = 200  # keep equal to the slice in orchestrator.run_pipeline


def load_tasks(tasks_dir: Path = TASKS_DIR) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(tasks_dir.glob("*.json"))]


def papers_by_topic() -> dict[str, dict[str, str]]:
    """topic -> {paper_id: cite label}, read from the index (so it matches data/chunks.jsonl)."""
    out: dict[str, dict[str, str]] = {}
    for c in get_index().chunks:
        out.setdefault(c["topic"], {})[c["paper_id"]] = c["paper"]
    return out


def target_papers(task: dict) -> list[str]:
    """Paper ids of the topic whose first-author surname appears as 'Surname et al' in the input."""
    found = []
    for pid, cite in papers_by_topic().get(task["topic"], {}).items():
        surname = cite.split()[0]
        if re.search(rf"\b{re.escape(surname)}\s+et\s+al", task["input"]):
            found.append(pid)
    return found


def check_task(task: dict, k: int = DEFAULT_K) -> dict:
    query = task["input"][:QUERY_CHARS]
    targets = target_papers(task)
    ix = get_index()
    pid_of = {c["id"]: c["paper_id"] for c in ix.chunks}
    row = {"task_id": task["id"], "topic": task["topic"], "target": targets, "query_chars": len(query)}
    for name, expand in (("graph", True), ("bm25", False)):
        chunks = retrieve_with(query, task["topic"], k, expand=expand)
        ranks = [i for i, c in enumerate(chunks, 1) if pid_of.get(c.id) in targets]
        row[name] = {
            "hit": bool(ranks),
            "first_rank": ranks[0] if ranks else None,
            "target_chunks": len(ranks),
            "top_k": [{"id": c.id, "paper": c.paper, "section": c.section, "score": c.score} for c in chunks],
        }
    return row


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", type=int, default=DEFAULT_K)
    ap.add_argument("--out", type=Path, help="also write the full result as JSON")
    args = ap.parse_args()

    rows = [check_task(t, args.k) for t in load_tasks()]
    print(f"| task | target paper | graph: hit (rank) | bm25: hit (rank) |\n|---|---|---|---|")
    for r in rows:
        fmt = lambda d: f"{'yes' if d['hit'] else 'NO'} ({d['first_rank'] or '-'})"  # noqa: E731
        print(f"| {r['task_id']} | {', '.join(r['target']) or 'NOT FOUND'} | {fmt(r['graph'])} | {fmt(r['bm25'])} |")
    known = [r for r in rows if r["target"]]
    for name in ("graph", "bm25"):
        hits = sum(r[name]["hit"] for r in known)
        print(f"{name}: {hits}/{len(known)} tasks have >=1 chunk of the paper under critique in top-{args.k}")
    if len(known) < len(rows):
        print(f"WARNING: {len(rows) - len(known)} task(s) do not name the paper as 'Surname et al.'")
    if args.out:
        args.out.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
