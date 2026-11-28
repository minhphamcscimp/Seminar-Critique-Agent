# Seminar Critique Agent

Multi-agent seminar critique tool using GraphRAG, aligned with the instructor's rubric.
CO5151 (Advanced Agentic AI), HCMUT, Group 7.

The tool helps students prepare a structured critique of a seminar paper along five axes:
assumptions, baseline fairness, data reliability, generalizability, reproducibility.

## Architecture (target, matches the D1 proposal)

```
material -> [retrieval: GraphRAG] -> Summarizer -> Critic (+ benchmark tool) -> Synthesizer
                                                                   |
                                      Reflection loop (max 2 iterations, external feedback)
```

Experiment configurations (see `seminar_critique/configs.py`):

| Config | What it does |
|---|---|
| A | One LLM call, no pipeline (simple baseline) |
| B | 3 agents with retrieval and the benchmark tool, no reflection |
| C | B plus the reflection loop |

## Status

| Part | Status |
|---|---|
| Skeleton, interfaces, contract tests | done (contract tests pass, FakeLLM kept for offline tests) |
| Real LLM client | real: GeminiClient with temperature, per-call model, token usage, latency and cost from price env vars (seminar_critique/llm/) |
| Retrieval (GraphRAG) | real: BM25 + graph expansion, 10 papers, 2 topics (retrieval/stats.json) |
| Tools and permissions | real: read-only benchmark lookup, 31 sourced records from 8 papers, permission allowlist, one audit line per tool call; evidence for 23 of 25 eval tasks (the 2 Kamoi survey tasks have no own table) ([details](seminar_critique/tools/README.md)) |
| Eval set and runner | real: runner and scorer, 9 tasks x 3 configs x 3 repeats = 81 runs (eval/results/results.csv, summary.md); scores are phrase-match proxies |
| Threat model and attacks | documented; sanitization, prompt boundaries, input check implemented; 16 attack cases with harness (`python -m seminar_critique.security.run_attacks`), offline run done, live Gemini run on `d3-freeze` pending ([details](seminar_critique/security/threat_model.md)) |

Update this table as parts become real. Be exact: "stub" means it does not do the real work yet.

## Layout

```
seminar_critique/
  schemas.py        shared data contracts
  llm/              LLM client (FakeLLM and GeminiClient)
  agents/           summarizer, critic, synthesizer, reflection
  orchestrator.py   pipeline and reflection loop
  configs.py        configurations A, B, C
  retrieval/        GraphRAG retrieval
  tools/            tool registry with allowlist, benchmark lookup
  security/         threat model, untrusted-content handling, audit log, attack cases + harness
  run.py            run one task, save the trace
eval/               tasks, runner, scorer, results
tests/              contract tests
third_party/MAD/    code and data from the MAD paper (not ours, see below)
```

## Quick start

Requirements: Python 3.11 or newer (checked on 3.13.18 Linux and 3.14.5 Windows), internet only
for the live Gemini run. Install takes about 1-2 minutes (`pymupdf` pulls in `onnxruntime` and `numpy`).

```
python -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cp .env.example .env                 # Windows: Copy-Item .env.example .env, then put your key in .env
python -m pytest
```

Use `python -m pip` and `python -m pytest` (not `pip` / `pytest`): some Windows machines with an
Application Control policy block the `.exe` launchers inside `.venv`.

Three ways to run, from cheapest to most expensive:

| What | Command | API key | Cost | Writes |
|---|---|---|---|---|
| Demo, offline (FakeLLM) | `python -m seminar_critique.run --task eval/tasks/example_task.json --config C` | no | 0 | `traces/C/` |
| Re-read the saved results (no run) | `python -m eval.summarize` | no | 0 | `eval/results/summary.md` (same table as committed) |
| Pipeline check, offline (FakeLLM) | `python -m eval.runner --repeats 1 --out eval/results/results_fake.csv` | no | 0 | the file given in `--out` |
| Demo, live | `python -m seminar_critique.run --task eval/tasks/example_task.json --config C --llm gemini` | yes | < 0.01 USD | `traces/C/` |
| Full evaluation, live | `python -m eval.runner --llm gemini --repeats 3` then `python -m eval.summarize` | yes | see report Section 5 | `eval/results/results.csv`, `summary.md` |

**Warning:** `python -m eval.runner` without `--out` writes `eval/results/results.csv`, the file the
report numbers come from. An offline run (the default `--llm fake`) would overwrite the real results
with FakeLLM numbers, so always pass `--out` for offline runs. If it happens: `git checkout -- eval/results/`.

Run `summarize` as a module (`python -m eval.summarize`); `python eval/summarize.py` fails with
`ModuleNotFoundError: seminar_critique`.

Team workflow: see [CONTRIBUTING.md](CONTRIBUTING.md).

## Third-party code and attribution

`third_party/MAD/` is the code and data of *Encouraging Divergent Thinking in Large Language
Models through Multi-Agent Debate* (Liang et al., 2023,
[Skytliang/Multi-Agents-Debate](https://github.com/Skytliang/Multi-Agents-Debate)),
licensed under GPL-3.0. It is kept as a reference for the retry logic and the debate pattern.
Results and data inside `third_party/` are **not** results of this project.

## Reproducibility

Numbers in the report come from `eval/results/results.csv`, produced by
`python -m eval.runner --llm gemini --repeats 3` and summarised by `python -m eval.summarize`.
The report states the repository URL and the exact commit hash (tag `final`).

- **Live run vs saved results.** Re-running live calls Gemini again: answers, cost and latency
  change from run to run. The committed CSV and traces are the record of the run in the report;
  re-reading them (`python -m eval.summarize`) reproduces the tables exactly, but it is not
  evidence that the system runs. The offline FakeLLM runs show that the pipeline runs end to end.
- **Rate limit.** The runner waits at least 6 s between Gemini calls (`--gemini-call-interval`).
  If a run stops, continue it with `--resume`.
- **Retrieval data.** `data/chunks.jsonl` is committed, so retrieval needs no download.
  To rebuild it from the arXiv PDFs (optional, needs internet):
  `python -m seminar_critique.retrieval.ingest --out data/chunks_new.jsonl`, then
  `python -m seminar_critique.retrieval.compare_chunks data/chunks.jsonl data/chunks_new.jsonl`.
  arXiv may serve a newer version of a paper, so a rebuild can differ from the committed file.
- **Retrieval numbers.** `python -m seminar_critique.retrieval.stats` writes `retrieval/stats.json`;
  `python -m seminar_critique.retrieval.check_tasks --out seminar_critique/retrieval/task_check.json`
  checks, for every task in `eval/tasks/`, that the top-5 contains the paper under critique.
- **Manual steps.** Getting a Gemini API key and putting it in `.env` cannot be automated.
- **Checked on:** see `docs/repro_check.md` (date, OS, Python version, commands, problems found).
