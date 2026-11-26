"""Official evaluation run in one command (plan: CN-T2 29-30/11, on tag d3-freeze). Owner: Tam.

    git checkout d3-freeze
    python -m eval.official                # checks, then runner -> judge -> summarize -> error analysis
    python -m eval.official                # same command again continues after a stop (--resume)

Checks first: HEAD is the commit of tag d3-freeze, no tracked file is modified,
GEMINI_API_KEY is available. Then writes eval/results/run_info.md (date, commit, model,
prices) so Section 5 can cite how the numbers were produced. Commit eval/results/ after it.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from seminar_critique.llm import DEFAULT_GEMINI_MODEL
from seminar_critique.llm.client import _load_dotenv
from seminar_critique.llm.pricing import PRICE_DATE, PRICE_SOURCE, price_per_million

RESULTS = Path("eval/results")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False).stdout.strip()


def preflight(tag: str, allow_untagged: bool) -> list[str]:
    problems = []
    head = git("rev-parse", "HEAD")
    tagged = git("rev-parse", "--verify", "-q", f"refs/tags/{tag}^{{commit}}")
    if not allow_untagged and head != tagged:
        problems.append(f"HEAD {head[:10]} is not tag {tag} ({tagged[:10] or 'tag not found'}); "
                        f"run `git fetch --tags && git checkout {tag}`")
    if git("status", "--porcelain", "--untracked-files=no"):
        problems.append("tracked files are modified; the run must match the tagged code")
    _load_dotenv()
    if not os.getenv("GEMINI_API_KEY"):
        problems.append("GEMINI_API_KEY is not set (put it in .env)")
    return problems


def run(step: list[str]) -> None:
    print(f"\n=== python -m {' '.join(step)}", flush=True)
    code = subprocess.run([sys.executable, "-m", *step], check=False).returncode
    if code:
        sys.exit(f"step failed with exit code {code}; fix the cause and run the same command again")


def write_run_info(tag: str, repeats: int) -> None:
    model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    judge_model = os.getenv("GEMINI_JUDGE_MODEL", model)
    price_in, price_out = price_per_million(model)
    lines = [
        "# Official run information",
        "",
        f"- Finished (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"- Code: tag `{tag}`, commit `{git('rev-parse', 'HEAD')}`",
        f"- Model (all agents, configs A/B/C): `{model}`, temperature 0",
        f"- Judge model: `{judge_model}`, temperature 0",
        f"- Repeats: {repeats}; tasks: {len(list(Path('eval/tasks').glob('*.json')))}",
        f"- Prices: {price_in} / {price_out} USD per 1M input / output tokens "
        f"(paid tier, read on {PRICE_DATE}, {PRICE_SOURCE}); free tier used means a real bill of 0 USD",
        "- Commands: `python -m eval.official` = eval.runner --llm gemini --resume, "
        "eval.judge --llm gemini --resume, eval.summarize, eval.error_analysis",
        "",
    ]
    (RESULTS / "run_info.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tag", default="d3-freeze")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--allow-untagged", action="store_true", help="for a rehearsal only, not for the report")
    args = p.parse_args()

    problems = preflight(args.tag, args.allow_untagged)
    if problems:
        sys.exit("cannot start the official run:\n- " + "\n- ".join(problems))
    resume = ["--resume"] if (RESULTS / "results.csv").exists() and _is_d3_csv() else []
    run(["eval.runner", "--llm", "gemini", "--repeats", str(args.repeats), *resume])
    judge_resume = ["--resume"] if (RESULTS / "judge.csv").exists() else []
    run(["eval.judge", "--llm", "gemini", *judge_resume])
    run(["eval.summarize", "--repeats", str(args.repeats)])
    run(["eval.error_analysis"])
    write_run_info(args.tag, args.repeats)
    print("\nDone. Check summary.md, then commit eval/results/ (not traces/).")


def _is_d3_csv() -> bool:
    """The committed D2 results.csv has no run_id: start fresh instead of resuming it."""
    with (RESULTS / "results.csv").open(encoding="utf-8") as f:
        return f.readline().startswith("run_id,")


if __name__ == "__main__":
    main()
