"""Summarize the evaluation CSV by configuration.

    python -m eval.summarize
    python -m eval.summarize --input eval/results/results.csv --output eval/results/summary.md

One command turns results.csv (and judge.csv when it exists) into summary.md:
per config the success rate, score mean and SD, cost/latency per task, errors and
retries, reflection effect (R4), paired differences between configs, and a per-task
table. Coverage columns are literal phrase-match proxies; they do not establish
semantic correctness. Reads both the D3 CSV (eval/runner.py FIELDS) and the older
D2 CSV, which has no verdict/error/reflection columns.
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from seminar_critique.configs import CONFIGS
from seminar_critique.llm.pricing import PRICE_DATE, PRICE_SOURCE

from .scorer import PASS_THRESHOLD, verdict

NUMERIC = (
    "key_point_recall", "rubric_axis_coverage",
    "prompt_tokens", "completion_tokens", "cost_usd", "latency_s",
)
REQUIRED_FIELDS = {"task_id", "config", "run", *NUMERIC}
PAIRS = (("A", "B"), ("B", "C"), ("A", "C"))

Row = dict[str, Any]


# ---------------------------------------------------------------- reading
def _number(value: Any, column: str, where: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{where}: invalid number in {column!r}: {value!r}") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{where}: {column!r} must be finite and non-negative")
    return number


def _normalize(row: Row, where: str = "row") -> Row:
    """Typed copy of one CSV row. Error rows keep None for the quality metrics."""
    error = str(row.get("error") or "")
    out: Row = {
        "task_id": str(row["task_id"]),
        "config": str(row.get("config", "")),
        "run": str(row["run"]),
        "run_id": str(row.get("run_id") or ""),
        "model": str(row.get("model") or ""),
        "timestamp": str(row.get("timestamp") or ""),
        "error": error,
        "retries": int(_number(row.get("retries") or 0, "retries", where)),
    }
    for column in NUMERIC:
        value = row.get(column)
        if error and value in ("", None):
            out[column] = None
        else:
            out[column] = _number(value, column, where)
    recall = out["key_point_recall"]
    out["score"] = recall if row.get("score") in ("", None) else _number(row["score"], "score", where)
    if error:
        out["score"], out["verdict"] = None, "error"
    else:
        out["verdict"] = str(row.get("verdict") or verdict(out["score"]))
    for column in ("reflection_iters", "reflection_changed", "tool_found"):
        value = row.get(column)
        out[column] = None if value in ("", None) else _number(value, column, where)
    return out


def _read_results(path: Path) -> dict[str, list[Row]]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        missing = REQUIRED_FIELDS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} is missing CSV columns: {', '.join(sorted(missing))}")
        rows_by_config: dict[str, list[Row]] = defaultdict(list)
        for line_number, row in enumerate(reader, start=2):
            config = row["config"]
            if config not in CONFIGS:
                raise ValueError(f"{path}:{line_number}: unknown config {config!r}")
            rows_by_config[config].append(_normalize(row, f"{path}:{line_number}"))
    if not rows_by_config:
        raise ValueError(f"{path} contains no evaluation rows")
    return rows_by_config


def _read_judge(path: Path) -> dict[str, Row]:
    """run_id -> judge row (see eval/judge.py)."""
    with path.open(newline="", encoding="utf-8") as csv_file:
        return {row["run_id"]: row for row in csv.DictReader(csv_file)}


# ---------------------------------------------------------------- statistics
def _mean(values: Iterable[float]) -> float | None:
    values = list(values)
    return statistics.fmean(values) if values else None


def _sd(values: Iterable[float]) -> float | None:
    """Sample standard deviation; None with fewer than 2 values."""
    values = list(values)
    return statistics.stdev(values) if len(values) >= 2 else None


def _fmt(value: float | None, digits: int = 3) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _mean_sd(values: list[float], digits: int = 3) -> str:
    mean, sd = _mean(values), _sd(values)
    if mean is None:
        return "n/a"
    return _fmt(mean, digits) if sd is None else f"{_fmt(mean, digits)} +/- {_fmt(sd, digits)}"


def _complete_task_ids(rows_by_config: dict[str, list[Row]], expected_repeats: int) -> tuple[set[str], set[str]]:
    task_runs: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for config, rows in rows_by_config.items():
        for row in rows:
            task_runs[str(row["task_id"])][config].add(str(row["run"]))

    # A task is complete when it has every repeat for every config that appears in the
    # CSV (not every config in CONFIGS: a new ablation config must not hide A/B/C).
    required = set(rows_by_config)
    expected_runs = {str(run) for run in range(expected_repeats)}
    complete = {
        task_id for task_id, configs in task_runs.items()
        if set(configs) == required and all(runs == expected_runs for runs in configs.values())
    }
    return complete, set(task_runs) - complete


def _task_means(rows: list[Row], key: str = "score") -> dict[str, float]:
    by_task: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row[key] is not None:
            by_task[row["task_id"]].append(row[key])
    return {task: statistics.fmean(values) for task, values in by_task.items()}


def _repeat_means(rows: list[Row]) -> list[float]:
    """Mean score of each repeat (over tasks): spread here is run-to-run noise."""
    by_run: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row["score"] is not None:
            by_run[row["run"]].append(row["score"])
    return [statistics.fmean(v) for _, v in sorted(by_run.items())]


# ---------------------------------------------------------------- rendering
def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
        *("| " + " | ".join(r) + " |" for r in rows),
    ]


def _main_table(rows_by_config: dict[str, list[Row]]) -> list[str]:
    header = [
        "Config", "Tasks", "Runs", "Errors", "Retries", "Success rate",
        "Score (mean +/- SD over runs)", "SD over repeats", "Rubric-axis coverage",
        "Tokens / task", "Cost / task (USD)", "Latency / task (s)",
    ]
    body = []
    for config, rows in rows_by_config.items():
        ok = [r for r in rows if not r["error"]]
        body.append([
            config,
            str(len({r["task_id"] for r in rows})),
            str(len(rows)),
            str(len(rows) - len(ok)),
            str(sum(r["retries"] for r in rows)),
            _fmt(sum(r["verdict"] == "pass" for r in rows) / len(rows)),
            _mean_sd([r["score"] for r in ok]),
            _fmt(_sd(_repeat_means(ok))),
            _mean_sd([r["rubric_axis_coverage"] for r in ok]),
            _mean_sd([r["prompt_tokens"] + r["completion_tokens"] for r in ok], 0),
            _mean_sd([r["cost_usd"] for r in ok], 5),
            _mean_sd([r["latency_s"] for r in ok], 1),
        ])
    return _table(header, body)


def _reflection_lines(rows_by_config: dict[str, list[Row]]) -> list[str]:
    lines = ["## Reflection (R4)", ""]
    body = []
    for config, rows in rows_by_config.items():
        if not CONFIGS[config].max_reflection_iters:
            continue
        recorded = [r for r in rows if not r["error"] and r["reflection_iters"] is not None]
        if not recorded:
            body.append([config, "0", "not recorded", "not recorded", "not recorded"])
            continue
        changed = sum(r["reflection_changed"] == 1 for r in recorded)
        stopped_first = sum(r["reflection_iters"] <= 1 for r in recorded)
        body.append([
            config, str(len(recorded)),
            _mean_sd([r["reflection_iters"] for r in recorded], 2),
            f"{changed}/{len(recorded)} ({changed / len(recorded):.0%})",
            f"{stopped_first}/{len(recorded)}",
        ])
    if not body:
        return []
    lines += _table(
        ["Config", "Runs", "Reflection calls (mean +/- SD)", "Runs where reflection changed the answer",
         "Runs with at most 1 reflection call"],
        body,
    )
    lines += ["", "\"Changed\" = the final answer differs from the Synthesizer draft (whitespace and case ignored).", ""]
    return lines


def _tool_lines(rows_by_config: dict[str, list[Row]]) -> list[str]:
    """R1: how often the benchmark tool returned evidence (found=true)."""
    body = []
    for config, rows in rows_by_config.items():
        recorded = [r for r in rows if not r["error"] and r["tool_found"] is not None]
        if not CONFIGS[config].use_tools or not recorded:
            continue
        tasks_with = {r["task_id"] for r in recorded if r["tool_found"] > 0}
        all_tasks = {r["task_id"] for r in recorded}
        body.append([config, f"{len(tasks_with)}/{len(all_tasks)} ({len(tasks_with) / len(all_tasks):.0%})",
                     _mean_sd([r["tool_found"] for r in recorded], 2)])
    if not body:
        return []
    return ["## Benchmark tool evidence (R1)", ""] + _table(
        ["Config", "Tasks with >= 1 record found", "Records found per run (mean +/- SD)"], body) + [""]


def _paired_lines(rows_by_config: dict[str, list[Row]]) -> list[str]:
    lines = [
        "## Paired differences (score, per task)",
        "",
        "Difference = mean score of the second config minus the first, per task, then averaged over tasks. "
        "A difference smaller than its SD is not evidence of improvement.",
        "",
    ]
    body = []
    for first, second in PAIRS:
        if first not in rows_by_config or second not in rows_by_config:
            continue
        a, b = _task_means(rows_by_config[first]), _task_means(rows_by_config[second])
        diffs = [b[t] - a[t] for t in sorted(set(a) & set(b))]
        if not diffs:
            continue
        wins = sum(d > 0 for d in diffs)
        losses = sum(d < 0 for d in diffs)
        body.append([
            f"{second} - {first}", str(len(diffs)), _mean_sd(diffs),
            f"{wins} / {len(diffs) - wins - losses} / {losses}",
        ])
    if not body:
        return []
    return lines + _table(["Comparison", "Tasks", "Mean diff +/- SD", "Better / equal / worse"], body) + [""]


def _per_task_lines(rows_by_config: dict[str, list[Row]]) -> list[str]:
    configs = list(rows_by_config)
    means = {c: _task_means(rows_by_config[c]) for c in configs}
    errors: dict[tuple[str, str], int] = defaultdict(int)
    for c, rows in rows_by_config.items():
        for r in rows:
            errors[(r["task_id"], c)] += bool(r["error"])
    tasks = sorted({t for c in configs for t in means[c]} | {t for t, _ in errors})
    body = []
    for t in tasks:
        cells = []
        for c in configs:
            cell = _fmt(means[c].get(t))
            if errors[(t, c)]:
                cell += f" ({errors[(t, c)]} err)"
            cells.append(cell)
        body.append([t, *cells])
    return ["## Score per task (mean over repeats)", ""] + _table(["Task", *configs], body) + [""]


def _judge_lines(rows_by_config: dict[str, list[Row]], judge: dict[str, Row]) -> list[str]:
    lines = [
        "## LLM judge (semantic key-point coverage, see eval/judge.md)",
        "",
    ]
    body = []
    for config, rows in rows_by_config.items():
        judged = [judge[r["run_id"]] for r in rows if r["run_id"] in judge]
        ok = [j for j in judged if not j.get("error")]
        if not judged:
            continue
        scores = [float(j["judge_score"]) for j in ok]
        passes = sum(j.get("judge_verdict") == "pass" for j in ok)
        body.append([
            config, str(len(judged)), str(len(judged) - len(ok)),
            _fmt(passes / len(rows)), _mean_sd(scores),
        ])
    if not body:
        return []
    lines += _table(["Config", "Runs judged", "Judge errors", "Judge success rate", "Judge score (mean +/- SD)"], body)
    return lines + ["", f"Judge success rate counts runs not judged or with a pipeline error as failures.", ""]


def _render(
    rows_by_config: dict[str, list[Row]],
    expected_repeats: int = 3,
    judge: dict[str, Row] | None = None,
) -> str:
    if expected_repeats < 1:
        raise ValueError("expected_repeats must be at least 1")
    rows_by_config = {
        config: [_normalize(r) for r in rows] for config, rows in rows_by_config.items()
    }
    complete_task_ids, incomplete_task_ids = _complete_task_ids(rows_by_config, expected_repeats)
    lines = [
        "# Evaluation summary",
        "",
        "Generated by `python -m eval.summarize` from `results.csv`. Means are over runs "
        "(one run = one task, one config, one repeat); SD is the sample standard deviation. "
        "Coverage metrics are literal phrase-match proxies, not semantic correctness judgments.",
        "",
    ]
    if not complete_task_ids:
        lines += [
            "**No complete task available; metrics are withheld.** Each included task "
            "must have every repeat for every configuration in the CSV.",
            "",
        ]
        if incomplete_task_ids:
            lines += [f"Incomplete tasks excluded: {', '.join(sorted(incomplete_task_ids))}.", ""]
        return "\n".join(lines) + "\n"

    if len(complete_task_ids) < 5:
        lines += [
            f"**Warning:** only {len(complete_task_ids)} complete task(s) are included; "
            "the project plan requires at least 5 for reporting.",
            "",
        ]
    if incomplete_task_ids:
        lines += [f"Incomplete tasks excluded: {', '.join(sorted(incomplete_task_ids))}.", ""]

    included = {
        config: [r for r in rows_by_config.get(config, []) if r["task_id"] in complete_task_ids]
        for config in CONFIGS
    }
    included = {c: rows for c, rows in included.items() if rows}

    lines += _main_table(included)
    lines += [
        "",
        f"Success = verdict `pass`: key-point recall >= {PASS_THRESHOLD}. Error runs count as failures "
        "in the success rate and are left out of every other mean. Score = key-point recall. "
        "\"SD over repeats\" is the SD of the per-repeat mean score (run-to-run noise); "
        "\"Tokens / Cost / Latency per task\" are per run of one task.",
        "",
    ]
    lines += _reflection_lines(included)
    lines += _tool_lines(included)
    lines += _paired_lines(included)
    if judge:
        lines += _judge_lines(included, judge)
    lines += _per_task_lines(included)

    all_rows = [r for rows in included.values() for r in rows]
    models = sorted({r["model"] for r in all_rows if r["model"]})
    stamps = sorted(r["timestamp"] for r in all_rows if r["timestamp"])
    lines += [
        "## Run information",
        "",
        f"- Models: {', '.join(models) if models else 'not recorded in this CSV'}.",
        f"- Run dates (UTC): {stamps[0]} to {stamps[-1]}." if stamps else "- Run dates: not recorded in this CSV.",
        f"- Cost = prompt and completion tokens × price per 1M tokens from `seminar_critique/llm/pricing.py` "
        f"(paid-tier prices read on {PRICE_DATE}, {PRICE_SOURCE}). On the free tier the real bill is 0 USD.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="eval/results/results.csv")
    parser.add_argument("--output", default="eval/results/summary.md")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--judge", default="eval/results/judge.csv",
        help="judge CSV from eval/judge.py; skipped when the file does not exist",
    )
    args = parser.parse_args()

    judge_path = Path(args.judge)
    judge = _read_judge(judge_path) if args.judge and judge_path.exists() else None
    summary = _render(_read_results(Path(args.input)), expected_repeats=args.repeats, judge=judge)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(summary, encoding="utf-8")
    print(summary, end="")
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
