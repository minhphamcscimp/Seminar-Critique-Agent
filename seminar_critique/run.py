"""Run one task with one config and save the trace.

    python -m seminar_critique.run --task eval/tasks/example_task.json --config C
    python -m seminar_critique.run --task eval/tasks/example_task.json --config A --llm gemini

Uses the offline FakeLLM by default, so it works without any API key.
With --llm gemini the key is read from GEMINI_API_KEY (.env is loaded automatically).
The trace JSON is what the report shows as the "real trace" (Part 2).
"""
from __future__ import annotations

import argparse
import json
import os

from .configs import CONFIGS
from .llm import get_client
from .orchestrator import run_pipeline
from .schemas import Task
from .trace_log import emit, log_session, make_run_id, write_jsonl


def save_trace(result, out_dir: str, run_id: int = 0) -> str:
    path = os.path.join(out_dir, result.config_name)
    os.makedirs(path, exist_ok=True)
    file = os.path.join(path, f"{result.task_id}_run{run_id}.json")
    with open(file, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
    return file


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True)
    p.add_argument("--config", choices=sorted(CONFIGS), default="C")
    p.add_argument("--llm", choices=["fake", "gemini"], default="fake")
    p.add_argument("--out", default="traces")
    args = p.parse_args()

    task = Task.from_json(args.task)
    with log_session(make_run_id(task.id, args.config, 0)) as log:
        try:
            result = run_pipeline(task, CONFIGS[args.config], get_client(args.llm))
        except Exception as exc:
            emit("error", error=type(exc).__name__, detail=str(exc))
            write_jsonl(log, args.out, args.config)
            raise
        jsonl_path = write_jsonl(log, args.out, args.config)
    file = save_trace(result, args.out)
    tokens = result.usage.prompt_tokens + result.usage.completion_tokens
    print(
        f"config={result.config_name} steps={len(result.trace)} tokens={tokens} "
        f"cost_usd={result.usage.cost_usd:.6f} latency={result.usage.latency_s:.3f}s trace={file} jsonl={jsonl_path}"
    )


if __name__ == "__main__":
    main()
