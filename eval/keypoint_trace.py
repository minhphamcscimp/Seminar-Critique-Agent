"""Where in the pipeline does a key point get lost? (R5, error analysis). Owner: Tam.

    python -m eval.keypoint_trace traces/B/self-refine-feedback_run0.json
    python -m eval.keypoint_trace --worse-than A --config B --out eval/results/keypoint_loss.md

For one trace: for every key point of its task, show whether the phrase appears in
the task input, in the retrieved material sent to the Summarizer, and in the output
of each agent step (summarizer, critic, synthesizer, reflection). The first step
whose output no longer contains a point that an earlier step had is where it was lost.

With --worse-than, it reads results.csv, finds tasks where --config scores below the
other config (mean over repeats), and writes this table for repeat 0 of each.
Uses the same literal phrase matching as eval/scorer.py, so it explains the proxy
score, not semantic quality.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from seminar_critique.schemas import Task

from .judge import load_tasks
from .scorer import _coverage, _tokens


def _has(phrase: str, text: str) -> bool:
    return _coverage([phrase], _tokens(text)) == 1.0


def explain(trace: dict, task: Task) -> list[str]:
    steps = trace.get("trace", [])
    columns = ["input"] + [s["agent"] for s in steps] + ["final"]
    texts = [task.input] + [s["output"] for s in steps] + [trace.get("answer", "")]
    lines = [
        f"### {trace.get('task_id')} config {trace.get('config_name')} "
        f"({trace.get('run_id', 'no run_id')})",
        "",
        "| Key point | " + " | ".join(columns) + " | Lost at |",
        "| --- | " + " | ".join(["---"] * len(columns)) + " | --- |",
    ]
    for kp in task.key_points:
        marks = [_has(kp, t) for t in texts]
        lost = ""
        for i in range(1, len(marks)):
            if any(marks[1:i]) and not marks[i] and columns[i] != "final":
                lost = columns[i]
                break
        if not any(marks[1:]):
            lost = "never produced"
        elif not marks[-1] and not lost:
            lost = "final"
        lines.append(f"| {kp} | " + " | ".join("yes" if m else "-" for m in marks) + f" | {lost} |")
    return lines + [""]


def worse_tasks(results: Path, config: str, other: str) -> list[tuple[str, float, float]]:
    scores: dict[tuple[str, str], list[float]] = defaultdict(list)
    with results.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row.get("error"):
                scores[(row["task_id"], row["config"])].append(float(row["key_point_recall"]))
    out = []
    for task_id in sorted({t for t, _ in scores}):
        a, b = scores.get((task_id, config)), scores.get((task_id, other))
        if a and b:
            ma, mb = sum(a) / len(a), sum(b) / len(b)
            if ma < mb:
                out.append((task_id, ma, mb))
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("traces", nargs="*", help="trace JSON files")
    p.add_argument("--tasks", default="eval/tasks")
    p.add_argument("--results", default="eval/results/results.csv")
    p.add_argument("--traces-dir", default="traces")
    p.add_argument("--config", default="B")
    p.add_argument("--worse-than", default=None, help="other config, e.g. A")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    tasks = load_tasks(args.tasks)
    lines: list[str] = ["# Key points per pipeline step", ""]
    files = [Path(t) for t in args.traces]
    if args.worse_than:
        worse = worse_tasks(Path(args.results), args.config, args.worse_than)
        lines += [f"Tasks where {args.config} scores below {args.worse_than} (mean key-point recall):", ""]
        lines += [f"- {t}: {args.config} {a:.2f} vs {args.worse_than} {b:.2f}" for t, a, b in worse]
        lines += [""]
        files += [Path(args.traces_dir) / args.config / f"{t}_run0.json" for t, _, _ in worse]
    if not files:
        p.error("give trace files or --worse-than")
    for path in files:
        if not path.exists():
            lines += [f"### {path.as_posix()}", "", "trace file not found (traces/ is not committed; re-run the task)", ""]
            continue
        trace = json.loads(path.read_text(encoding="utf-8"))
        task = tasks.get(trace.get("task_id", ""))
        if task is None:
            lines += [f"### {path}", "", "task not found in eval/tasks", ""]
            continue
        lines += [f"Trace: `{path.as_posix()}`", ""] + explain(trace, task)
    text = "\n".join(lines)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
