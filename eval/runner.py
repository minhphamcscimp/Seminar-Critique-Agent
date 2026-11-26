"""Experiment runner. Owner: Tam.

    python -m eval.runner --tasks eval/tasks --configs A B C --repeats 3

Runs every task with every config several times, saves each trace under traces/,
and writes one CSV row per run into eval/results/. Commit the CSV, not the traces,
so the numbers in the report can be reproduced from the repository. The scorer's
coverage values are deterministic phrase matches, not semantic correctness scores.

A run that raises an error is kept as a row with the `error` column filled and
`verdict = error`; it never counts as a success. `--resume` re-runs those rows.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from seminar_critique.configs import CONFIGS, resolve_models
from seminar_critique.llm import LLMClient, LLMResponse, OutOfQuotaError, get_client
from seminar_critique.orchestrator import run_pipeline
from seminar_critique.schemas import Config, Result, Task

from .scorer import PASS_THRESHOLD, score, verdict

# Column order of results.csv. `config` is the config id (A/B/C) and `run` the repeat
# index (0..repeats-1); `run_id` is unique per row and is also written in the trace.
FIELDS = [
    "run_id", "task_id", "topic", "difficulty", "config", "run", "model", "timestamp",
    "key_point_recall", "rubric_axis_coverage", "score", "verdict",
    "prompt_tokens", "completion_tokens", "tokens", "cost_usd", "latency_s",
    "reflection_iters", "reflection_changed", "error", "retries", "trace_path",
]
# Columns of the D2 file (results.csv before D3). Resume refuses to mix the two.
LEGACY_FIELDS = [
    "task_id", "config", "run", "key_point_recall", "rubric_axis_coverage",
    "prompt_tokens", "completion_tokens", "cost_usd", "latency_s",
]
RETRY_MARKER = "[llm] call failed"  # printed by seminar_critique.llm.client on each retry


def make_run_id(task_id: str, config: str, run: int) -> str:
    """Stable id for one (task, config, repeat); the same on resume and in the trace."""
    return f"{task_id}-{config}-r{run}"


class _PacedClient:
    def __init__(self, client: LLMClient, min_interval_s: float) -> None:
        self._client = client
        self._min_interval_s = min_interval_s
        self._last_call_started: float | None = None

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        if self._last_call_started is not None:
            elapsed = time.monotonic() - self._last_call_started
            delay = self._min_interval_s - elapsed
            if delay > 0:
                time.sleep(delay)
        self._last_call_started = time.monotonic()
        return self._client.complete(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )


class _RetryCounter:
    """Pass stdout through and count the retry lines the LLM client prints.

    The Gemini client retries inside a backoff decorator and only reports it with
    a print, so this is the one place the runner can see retries without changing
    the client.
    """

    def __init__(self, stream: Any) -> None:
        self._stream = stream
        self.count = 0

    def write(self, text: str) -> int:
        self.count += text.count(RETRY_MARKER)
        return self._stream.write(text)

    def flush(self) -> None:
        self._stream.flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def reflection_stats(result: Result) -> tuple[int, int]:
    """(number of reflection calls, 1 if reflection changed the final answer else 0)."""
    iters = sum(1 for step in result.trace if step.agent == "reflection")
    drafts = [step.output for step in result.trace if step.agent == "synthesizer"]
    changed = int(bool(drafts) and iters > 0 and _norm(drafts[-1]) != _norm(result.answer))
    return iters, changed


def model_label(cfg: Config) -> str:
    """Models the config really calls (A only calls the baseline agent)."""
    agents = ["baseline"] if not cfg.use_pipeline else [
        "summarizer", "critic", "synthesizer", *(["reflection"] if cfg.max_reflection_iters else [])
    ]
    return "+".join(sorted({cfg.models[a] for a in agents if a in cfg.models}))


def save_trace(result: Result | None, out_dir: str, task: Task, config: str, run: int,
               meta: dict[str, Any]) -> str:
    """Write traces/<config>/<task_id>_run<run>.json with run_id and run metadata."""
    path = Path(out_dir) / config
    path.mkdir(parents=True, exist_ok=True)
    file = path / f"{task.id}_run{run}.json"
    data: dict[str, Any] = dict(meta)
    if result is not None:
        data.update(result.to_dict())
    else:
        data.update({"task_id": task.id, "config_name": config, "answer": "", "trace": []})
    file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return file.as_posix()


def run_one(task: Task, name: str, run: int, llm: LLMClient, llm_name: str,
            traces_dir: str) -> dict[str, Any]:
    """Run one task/config/repeat and return its CSV row. Errors become a row too."""
    config = resolve_models(CONFIGS[name], llm_name)
    run_id = make_run_id(task.id, name, run)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    counter = _RetryCounter(sys.stdout)
    started = time.perf_counter()
    result: Result | None = None
    error = ""
    old_stdout, sys.stdout = sys.stdout, counter
    try:
        result = run_pipeline(task, config, llm)
    except OutOfQuotaError:
        raise
    except Exception as exc:  # noqa: BLE001 - every failure must be recorded, not hidden
        error = f"{type(exc).__name__}: {exc}".replace("\n", " ")[:300]
    finally:
        sys.stdout = old_stdout

    row: dict[str, Any] = {
        "run_id": run_id, "task_id": task.id, "topic": task.topic,
        "difficulty": task.difficulty, "config": name, "run": run,
        "model": model_label(config), "timestamp": timestamp,
        "error": error, "retries": counter.count,
    }
    if result is None:
        row.update({
            "key_point_recall": "", "rubric_axis_coverage": "", "score": "",
            "verdict": "error", "prompt_tokens": 0, "completion_tokens": 0, "tokens": 0,
            "cost_usd": 0.0, "latency_s": round(time.perf_counter() - started, 3),
            "reflection_iters": "", "reflection_changed": "",
        })
    else:
        s = score(task, result)
        iters, changed = reflection_stats(result)
        usage = result.usage
        row.update({
            "key_point_recall": s["key_point_recall"],
            "rubric_axis_coverage": s["rubric_axis_coverage"],
            "score": s["key_point_recall"],
            "verdict": verdict(s["key_point_recall"]),
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "tokens": usage.prompt_tokens + usage.completion_tokens,
            "cost_usd": usage.cost_usd,
            "latency_s": round(usage.latency_s, 3),
            "reflection_iters": iters if config.max_reflection_iters else "",
            "reflection_changed": changed if config.max_reflection_iters else "",
        })
    meta = {k: row[k] for k in ("run_id", "model", "timestamp", "error", "retries")}
    row["trace_path"] = save_trace(result, traces_dir, task, name, run, meta)
    return row


def _load_resume_rows(path: Path, tasks: list[Task], configs: list[str], repeats: int,
                      p: argparse.ArgumentParser) -> list[dict[str, str]]:
    """Rows to keep from an earlier run: valid, matching, and without an error."""
    with path.open(newline="", encoding="utf-8") as existing_file:
        reader = csv.DictReader(existing_file)
        if reader.fieldnames != FIELDS:
            p.error(f"cannot resume: {path} does not have the expected CSV columns")
        rows = list(reader)
    task_ids = {task.id for task in tasks}
    seen: set[tuple[str, str, int]] = set()
    kept: list[dict[str, str]] = []
    for line_number, row in enumerate(rows, start=2):
        try:
            key = (row["task_id"], row["config"], int(row["run"]))
        except (KeyError, TypeError, ValueError) as exc:
            p.error(f"cannot resume: invalid row {line_number} in {path}: {exc}")
        if key[0] not in task_ids or key[1] not in configs or not 0 <= key[2] < repeats:
            p.error(
                f"cannot resume: row {line_number} does not match the requested tasks, "
                "configs, and repeats"
            )
        if key in seen:
            p.error(f"cannot resume: duplicate task/config/run row at line {line_number}")
        seen.add(key)
        if not row["error"]:
            kept.append(row)
    return kept


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tasks", default="eval/tasks")
    p.add_argument("--configs", nargs="+", default=["A", "B", "C"], choices=sorted(CONFIGS))
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--llm", choices=["fake", "gemini"], default="fake")
    p.add_argument("--out", default="eval/results/results.csv")
    p.add_argument("--traces", default="traces")
    p.add_argument(
        "--resume",
        action="store_true",
        help="keep completed rows already in --out and run the rest (error rows are re-run)",
    )
    p.add_argument(
        "--gemini-call-interval",
        type=float,
        default=6.0,
        help="minimum seconds between Gemini API request starts (default: 6, about 10/min)",
    )
    args = p.parse_args()

    if args.repeats < 1:
        p.error("--repeats must be at least 1")
    if args.gemini_call_interval < 0:
        p.error("--gemini-call-interval must be non-negative")
    task_files = sorted(glob.glob(os.path.join(args.tasks, "*.json")))
    if not task_files:
        p.error(f"no task JSON files found in {args.tasks!r}")
    tasks = [Task.from_json(path) for path in task_files]
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    kept_rows: list[dict[str, str]] = []
    if args.resume and output_path.exists() and output_path.stat().st_size:
        kept_rows = _load_resume_rows(output_path, tasks, args.configs, args.repeats, p)
    completed_runs = {(r["task_id"], r["config"], int(r["run"])) for r in kept_rows}

    llm: LLMClient = get_client(args.llm)
    if args.llm == "gemini":
        llm = _PacedClient(llm, args.gemini_call_interval)

    total = len(tasks) * len(args.configs) * args.repeats
    # Rewrite the file with the kept rows first: error rows from the earlier run are
    # dropped here and run again below, so each task/config/run appears once.
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(kept_rows)
        f.flush()
        completed_tasks = 0
        completed_runs_count = len(completed_runs)
        error_count = 0
        interrupted = False
        current_run: tuple[str, str, int] | None = None
        try:
            for task in tasks:
                for name in args.configs:
                    for run in range(args.repeats):
                        key = (task.id, name, run)
                        if key in completed_runs:
                            continue
                        current_run = key
                        print(
                            f"starting run {completed_runs_count + 1}/{total}: "
                            f"{task.id} config {name} repeat {run + 1}/{args.repeats}",
                            flush=True,
                        )
                        call_started = time.perf_counter()
                        row = run_one(task, name, run, llm, args.llm, args.traces)
                        writer.writerow(row)
                        f.flush()
                        completed_runs.add(key)
                        completed_runs_count += 1
                        current_run = None
                        status = f"ERROR {row['error']}" if row["error"] else "ok"
                        error_count += bool(row["error"])
                        print(
                            f"completed {completed_runs_count}/{total} runs: "
                            f"{task.id} config {name} repeat {run + 1}/{args.repeats} "
                            f"({time.perf_counter() - call_started:.1f}s, {status})",
                            flush=True,
                        )
                if all(
                    (task.id, config, run) in completed_runs
                    for config in args.configs
                    for run in range(args.repeats)
                ):
                    completed_tasks += 1
                    print(f"completed task {completed_tasks}/{len(tasks)}: {task.id}", flush=True)
        except OutOfQuotaError as exc:
            p.exit(
                1,
                f"Gemini quota exhausted: {exc}. The current run was not saved; "
                f"completed rows remain in {output_path}. After quota resets, rerun "
                "the same command with --resume.\n",
            )
        except KeyboardInterrupt:
            interrupted = True
            active_run = (
                f" Current unreturned run: {current_run[0]} config {current_run[1]} "
                f"repeat {current_run[2] + 1}."
                if current_run
                else ""
            )
            print(
                f"interrupted; kept {completed_runs_count} completed run(s)."
                f"{active_run} Rerun with --resume to continue.",
                flush=True,
            )
    status = "stopped" if interrupted else "wrote"
    print(
        f"{status} {output_path} with {completed_runs_count} completed run(s), "
        f"{error_count} error(s) in this session (verdict pass = score >= {PASS_THRESHOLD})"
    )


if __name__ == "__main__":
    main()
