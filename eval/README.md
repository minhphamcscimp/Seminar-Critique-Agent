# Evaluation

Owner: Tam. Scoring rules and the LLM judge are described in [judge.md](judge.md).

## Task set (`eval/tasks/`, D3)

25 tasks, one JSON file each: 13 for `self-improvement-reflection`, 12 for
`tool-use-mcp`. Every paper of the corpus (`data/papers.md`) is critiqued by at least
2 tasks (Huang, ReAct, Toolformer, Gorilla and ToolLLM by 3). Fields:

| Field | Meaning |
|---|---|
| `id`, `topic`, `input`, `rubric_axes`, `key_points` | shared contract (`seminar_critique/schemas.py`) |
| `paper` | paper id from `data/papers.md` |
| `difficulty` | `easy` (restates the paper's own claim), `medium` (needs a limitation the paper states), `hard` (needs reasoning about evaluation design: oracle settings, baselines, judges) |
| `source` | paper section (and chunk ids in `data/chunks.jsonl`) the key points come from |

Each task asks for a critique of an over-reaching claim about one paper; the 3-5
key points are the findings a good critique should make, taken from the cited section.
**They are not copied from the instructor's `seminar-topics.pdf`** (not in the repo):
check them against its "Key defense points" and "Required" lists before the report.
`example-01` (the demo task) was rewritten in D3 to the oracle-label angle, because in
D2 it repeated `huang-intrinsic-self-correction`.

All 25 tasks pass the retrieval check: the top-5 of `retrieve()` contains a chunk of the
paper under critique (`python -m seminar_critique.retrieval.check_tasks`, 26/11).

## Commands

| What | Command | Writes |
|---|---|---|
| Pipeline check, offline | `python -m eval.runner --repeats 1 --out eval/results/results_fake.csv` | that file, `traces/` |
| **Official run, all steps** (on `d3-freeze`) | `python -m eval.official` | everything below + `results/run_info.md` |
| Official run, runner only | `python -m eval.runner --llm gemini --repeats 3` | `results/results.csv`, `traces/` |
| LLM judge | `python -m eval.judge --llm gemini` | `results/judge.csv` |
| Tables | `python -m eval.summarize` | `results/summary.md` |
| Human rating sample | `python -m eval.agreement sample` | `eval/human/` |
| Judge reliability | `python -m eval.agreement score` | `results/agreement.md` |
| Where key points get lost | `python -m eval.keypoint_trace --worse-than A --config B` | stdout or `--out` |
| Error analysis (Section 5.7) | `python -m eval.error_analysis` | `results/error_analysis.md` |
| Task list for the team | `python -m eval.task_table` | `eval/TASKS.md` |

`runner`, `judge` continue after a stop with `--resume` (pass the same options);
`eval.official` checks that HEAD is tag `d3-freeze`, the tree is clean and the key is set,
then resumes by itself when run again.
Without `--out`, the runner overwrites `results/results.csv`: always pass `--out` for
offline runs. Gemini calls are paced at about 10 per minute (`--gemini-call-interval`);
on quota exhaustion the runner stops, keeps completed rows and exits with an error.

**Budget (measured 26/11 with 1 live task, `example-01`, A+B+C):** 104 s wall-clock
including the 6 s pacing, 0.0022 USD for the three configs (A 7 s, B 42 s, C 51 s).
25 tasks x 3 repeats x (A 1 + B 3 + C up to 5 calls) = up to 675 pipeline calls:
about **2.2 h** and about 0.17 USD at paid-tier prices. The judge adds 225 calls
(about 25 min, about 0.03 USD). Start the official run early on 29/11.

## results.csv columns (D3)

| Column | Meaning |
|---|---|
| `run_id` | `<task_id>-<config>-r<repeat>`, also written in the trace JSON |
| `task_id`, `topic`, `difficulty` | from the task file |
| `config`, `run` | config id (A/B/C) and repeat index (0..2) |
| `model`, `timestamp` | model(s) the config called, UTC start time |
| `key_point_recall`, `rubric_axis_coverage` | phrase-match proxies (`scorer.py`) |
| `score`, `verdict` | `score` = key-point recall; `pass` if >= 0.5, `fail`, or `error` |
| `prompt_tokens`, `completion_tokens`, `tokens`, `cost_usd`, `latency_s` | whole run |
| `reflection_iters`, `reflection_changed` | config C only (R4): reflection calls, and 1 if the final answer differs from the Synthesizer draft |
| `tool_found` | configs with the tool (B, C): benchmark records returned with `found: true` (R1) |
| `error`, `retries` | exception text if the run failed; LLM retries counted from the client's retry log |
| `trace_path` | trace file of this run |

A failed run is kept with `verdict = error`; it counts as a failure in the success
rate and is excluded from the other means. `--resume` re-runs error rows.

`summary.md` reports per config: success rate, score mean and SD, SD over repeats,
errors, retries, tokens/cost/latency per task; the reflection effect; paired per-task
differences (B-A, C-B, C-A); the judge table when `judge.csv` exists; and a per-task table.

## Provenance of the committed results/results.csv (D2)

The committed file is still the D2 run (9 tasks, old column set; `summarize` reads both
formats). The 81 rows (9 tasks x 3 configs x 3 repeats) come from two runs with the same
model and temperature 0. After PR #11 fixed the benchmark lookup, configs B and C were
re-run (3 repeats) for the 4 tasks whose pipeline changed (example-01,
huang-evaluation-fairness, huang-intrinsic-self-correction, react-interleaving).
Those 24 rows replaced the old ones; the other 57 rows are unchanged. Token counts and
key-point recall repeat exactly across the 3 repeats, only latency varies. In D2,
`example-01` had the old input (same claim as huang-intrinsic-self-correction).
The D3 official run on `d3-freeze` will replace this file.

## Limits of the metrics

`key_point_recall` and `rubric_axis_coverage` are deterministic phrase-coverage proxies:
text is Unicode-normalized, case-folded, and matched by word sequence. They do not
establish semantic correctness, and paraphrases are missed. The LLM judge checks the
same key points semantically; its agreement with two human raters is measured on 15
cases (R6). Report the sample size with every claim.
