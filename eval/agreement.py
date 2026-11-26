"""Human rating sample and judge reliability (R6). Owner: Tam.

Step 1, after the official run and eval.judge:

    python -m eval.agreement sample --raters tam tin

picks 15 cases (5 tasks x configs A, B, C, repeat 0, so every task has a B/C pair),
spread over both topics, and writes to eval/human/:
    cases.md            the 15 answers to read, in shuffled order, WITHOUT the config
    sheet_<rater>.csv   one line per (case, key point); the rater fills `covered` with 1 or 0
    key.csv             case_id -> run_id / config (do not open before rating)

Each rater fills their own sheet independently. Step 2:

    python -m eval.agreement score --raters tam tin

computes percent agreement and Cohen's kappa on the key-point labels and on the
case verdicts (pass = coverage >= 0.5), for rater vs rater and each rater vs the
judge, and writes eval/results/agreement.md.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

from seminar_critique.schemas import Task

from .judge import load_tasks
from .scorer import verdict

HUMAN_DIR = Path("eval/human")
SAMPLE_CONFIGS = ("A", "B", "C")


# ---------------------------------------------------------------- statistics
def percent_agreement(a: list, b: list) -> float:
    if len(a) != len(b) or not a:
        raise ValueError("label lists must have the same non-zero length")
    return sum(x == y for x, y in zip(a, b)) / len(a)


def cohen_kappa(a: list, b: list) -> float | None:
    """Cohen's kappa for two raters; None when chance agreement is 1 (all one label)."""
    po = percent_agreement(a, b)
    labels = set(a) | set(b)
    n = len(a)
    pe = sum((a.count(lab) / n) * (b.count(lab) / n) for lab in labels)
    if pe == 1:
        return None
    return (po - pe) / (1 - pe)


# ---------------------------------------------------------------- sampling
def choose_cases(rows: list[dict[str, str]], tasks: dict[str, Task], n_tasks: int = 5,
                 seed: int = 7) -> list[dict[str, str]]:
    """Pick n_tasks tasks (alternating topics) whose A/B/C repeat-0 runs all exist without error."""
    by_task: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for r in rows:
        if r["run"] == "0" and not r["error"] and r["config"] in SAMPLE_CONFIGS:
            by_task[r["task_id"]][r["config"]] = r
    eligible = sorted(t for t, cfgs in by_task.items() if set(cfgs) == set(SAMPLE_CONFIGS))
    rng = random.Random(seed)
    by_topic: dict[str, list[str]] = defaultdict(list)
    for t in eligible:
        by_topic[tasks[t].topic].append(t)
    for ids in by_topic.values():
        rng.shuffle(ids)
    picked: list[str] = []
    topics = sorted(by_topic)
    while len(picked) < n_tasks and any(by_topic.values()):
        for topic in topics:
            if by_topic[topic] and len(picked) < n_tasks:
                picked.append(by_topic[topic].pop())
    if len(picked) < n_tasks:
        raise ValueError(f"only {len(picked)} tasks have error-free A/B/C runs; need {n_tasks}")
    cases = [by_task[t][c] for t in picked for c in SAMPLE_CONFIGS]
    rng.shuffle(cases)
    return cases


def write_sample(cases: list[dict[str, str]], tasks: dict[str, Task], raters: list[str],
                 out_dir: Path = HUMAN_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    md = ["# Cases to rate (configs hidden)", "",
          "For each case and key point, write 1 in your sheet if the critique clearly makes "
          "the point (paraphrase counts), else 0. Rate alone; do not open key.csv.", ""]
    key_rows, sheet_rows = [], []
    for i, row in enumerate(cases, start=1):
        case_id = f"case{i:02d}"
        task = tasks[row["task_id"]]
        answer = json.loads(Path(row["trace_path"]).read_text(encoding="utf-8")).get("answer", "")
        md += [f"## {case_id}", "", f"**Task:** {task.input}", "", "**Key points:**", ""]
        md += [f"{j}. {kp}" for j, kp in enumerate(task.key_points, start=1)]
        md += ["", "**Critique:**", "", answer.strip(), "", "---", ""]
        key_rows.append({"case_id": case_id, "run_id": row["run_id"], "task_id": row["task_id"],
                         "config": row["config"]})
        for j, kp in enumerate(task.key_points, start=1):
            sheet_rows.append({"case_id": case_id, "point": j, "key_point": kp, "covered": ""})
    (out_dir / "cases.md").write_text("\n".join(md), encoding="utf-8")
    _write_csv(out_dir / "key.csv", ["case_id", "run_id", "task_id", "config"], key_rows)
    for rater in raters:
        _write_csv(out_dir / f"sheet_{rater}.csv", ["case_id", "point", "key_point", "covered"], sheet_rows)


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------- scoring
def read_sheet(path: Path) -> dict[tuple[str, int], int]:
    labels: dict[tuple[str, int], int] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            value = row["covered"].strip()
            if value not in ("0", "1"):
                raise ValueError(f"{path}:{line}: 'covered' must be 0 or 1, got {value!r}")
            labels[(row["case_id"], int(row["point"]))] = int(value)
    return labels


def judge_labels(key_path: Path, judge_path: Path) -> dict[tuple[str, int], int]:
    with key_path.open(newline="", encoding="utf-8") as f:
        case_of = {r["run_id"]: r["case_id"] for r in csv.DictReader(f)}
    labels: dict[tuple[str, int], int] = {}
    with judge_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            case = case_of.get(row["run_id"])
            if case and not row["error"]:
                for j, ch in enumerate(row["point_labels"], start=1):
                    labels[(case, j)] = int(ch)
    return labels


def case_verdicts(labels: dict[tuple[str, int], int]) -> dict[str, str]:
    per_case: dict[str, list[int]] = defaultdict(list)
    for (case, _), v in labels.items():
        per_case[case].append(v)
    return {case: verdict(sum(v) / len(v)) for case, v in per_case.items()}


def compare(name_a: str, a: dict, name_b: str, b: dict) -> list[str]:
    keys = sorted(set(a) & set(b))
    if not keys:
        return [f"| {name_a} vs {name_b} | 0 | n/a | n/a |"]
    la, lb = [a[k] for k in keys], [b[k] for k in keys]
    kappa = cohen_kappa(la, lb)
    return [f"| {name_a} vs {name_b} | {len(keys)} | {percent_agreement(la, lb):.2f} | "
            f"{'n/a' if kappa is None else f'{kappa:.2f}'} |"]


def render_agreement(sources: dict[str, dict[tuple[str, int], int]]) -> str:
    names = list(sources)
    pairs = [(x, y) for i, x in enumerate(names) for y in names[i + 1:]]
    lines = ["# Judge reliability (R6)", "",
             "Generated by `python -m eval.agreement score`. Kappa = Cohen's kappa.", "",
             "## Key-point labels", "", "| Pair | Labels | Agreement | Kappa |", "| --- | --- | --- | --- |"]
    for x, y in pairs:
        lines += compare(x, sources[x], y, sources[y])
    verdicts = {n: case_verdicts(s) for n, s in sources.items()}
    lines += ["", "## Case verdicts (pass = coverage >= 0.5)", "",
              "| Pair | Cases | Agreement | Kappa |", "| --- | --- | --- | --- |"]
    for x, y in pairs:
        lines += compare(x, verdicts[x], y, verdicts[y])
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--results", default="eval/results/results.csv")
    s.add_argument("--tasks", default="eval/tasks")
    s.add_argument("--raters", nargs="+", default=["tam", "tin"])
    s.add_argument("--n-tasks", type=int, default=5)
    s.add_argument("--seed", type=int, default=7)
    c = sub.add_parser("score")
    c.add_argument("--raters", nargs="+", default=["tam", "tin"])
    c.add_argument("--judge", default="eval/results/judge.csv")
    c.add_argument("--out", default="eval/results/agreement.md")
    args = p.parse_args()

    if args.cmd == "sample":
        tasks = load_tasks(args.tasks)
        with open(args.results, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        cases = choose_cases(rows, tasks, args.n_tasks, args.seed)
        write_sample(cases, tasks, args.raters)
        print(f"wrote {len(cases)} cases to {HUMAN_DIR}/ for raters: {', '.join(args.raters)}")
    else:
        sources = {r: read_sheet(HUMAN_DIR / f"sheet_{r}.csv") for r in args.raters}
        judge_path = Path(args.judge)
        if judge_path.exists():
            sources["judge"] = judge_labels(HUMAN_DIR / "key.csv", judge_path)
        text = render_agreement(sources)
        Path(args.out).write_text(text, encoding="utf-8")
        print(text, end="")
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
