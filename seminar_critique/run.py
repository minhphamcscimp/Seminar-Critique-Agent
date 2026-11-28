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
from .security.audit import audit_run
from .security.input_check import InvalidMaterial, check_material


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

    # Careless input (wrong file, empty text, PDF bytes) stops here, before any LLM call.
    try:
        task = Task.from_json(args.task)
        check_material(task.input)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        p.error(f"{args.task}: not a readable task JSON file ({type(exc).__name__})")
    except TypeError as exc:
        p.error(f"{args.task}: task JSON needs id, topic and input ({exc})")
    except InvalidMaterial as exc:
        p.error(f"{args.task}: {exc}")
    # Same run_id format as eval/runner.py, so audit lines point at this trace.
    with audit_run(f"{task.id}-{args.config}-r0"):
        result = run_pipeline(task, CONFIGS[args.config], get_client(args.llm))
    file = save_trace(result, args.out)
    tokens = result.usage.prompt_tokens + result.usage.completion_tokens
    print(
        f"config={result.config_name} steps={len(result.trace)} tokens={tokens} "
        f"cost_usd={result.usage.cost_usd:.6f} latency={result.usage.latency_s:.3f}s trace={file}"
    )


if __name__ == "__main__":
    main()
