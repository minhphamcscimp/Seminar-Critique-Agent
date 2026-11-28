# Tools and permissions — Tin / Report Section 3 (R2) and Section 6

| Tool | Purpose | Status | Permission | Enforcement |
|---|---|---|---|---|
| `lookup_benchmark(name, metric)` | Give the Critic and the Reflection agent a published benchmark score with method and provenance | Real, local JSON, 31 records from 8 papers | `READ_ONLY` | Fixed `BENCHMARKS_PATH`, `open("r")`, no path argument; records validated on every call (`tools/benchmark_lookup.py::lookup_benchmark`) |
| Unregistered tools, tools marked write or code execution | Outside the project scope | Blocked | Denied | `tools/__init__.py::call_tool` raises `PermissionError` before invoking the function and writes a `blocked` audit line |

`seminar_critique/tools/__init__.py::call_tool` is the only tool entry point.
`TOOL_REGISTRY` contains only the benchmark lookup; `ALLOWED_PERMISSIONS` contains
only `READ_ONLY`. Every tool is read-only, so there is no write action that would need
human approval: the system never writes files, sends messages or calls a network
service on the student's behalf. The registered function loads `data/benchmarks.json`
relative to its own module, independent of the working directory. It reads no
secrets, calls no network services and opens no write mode. The registry is a code
policy, not a sandbox; developers remain responsible for registering only
implementations that actually respect their permission label.

```python
from seminar_critique.tools import call_tool

out = call_tool("lookup_benchmark", name="gsm8k", metric="ACCURACY")
assert out["result"]["value"] == 78.2
assert "Table 2" in out["result"]["source"]
```

`call_tool` returns `{tool, args, result}`. A hit includes `found`, `paper`,
`benchmark`, `metric`, `method`, `value`, and `source`; a miss includes
`found: false` and `source: null`. Matching is exact after stripping surrounding
whitespace and case-folding both arguments. Unknown metrics are not silently
substituted. File and schema errors propagate rather than becoming a fabricated result.

## Audit log (D3)

Every call through `call_tool`, allowed or blocked, writes exactly one JSON line
(`seminar_critique/security/audit.py`):

```json
{"timestamp": "2026-11-28T02:27:26.130+00:00", "run_id": "huang-intrinsic-self-correction-C-r0",
 "agent": "orchestrator", "tool": "lookup_benchmark", "args": {"name": "GSM8K", "metric": "accuracy"},
 "permission": "read_only", "decision": "allowed", "reason": "registered, permission read_only is allowlisted",
 "outcome": "ok", "found": true}
```

- File: `traces/audit.jsonl` (not committed) or the path in `SEMINAR_AUDIT_LOG`; the
  attack harness writes `<out>/audit.jsonl` next to its case logs.
- `run_id` comes from `audit_run(run_id)`. `eval/runner.py` and `seminar_critique/run.py`
  use the same id as the `results.csv` row / trace file (`<task_id>-<config>-r<run>`);
  the attack harness uses `attack-<case>-<config>`.
- `agent` is `orchestrator`: Python code in the orchestrator picks and calls the tool
  for the Critic and Reflection agents. No LLM output is executed as a tool call.
- Blocked calls are logged before `PermissionError` is raised. A call the tool itself
  refuses (bad arguments, broken data file) is logged as `allowed` with
  `outcome: error: <type>`. Arguments are cut to 300 characters.
- If the line cannot be written, the call fails (fail closed).

## Handle missing evidence and blocked tools

A missing pair means there is no matching published evidence in the local file;
it must not be interpreted as a score of zero. Check `found` before reading
`value` or citing `source`:

```python
out = call_tool("lookup_benchmark", name="unknown-benchmark", metric="accuracy")
result = out["result"]
if result["found"]:
    print(result["value"], result["source"])
else:
    print("No matching published result; no score available.")
```

A blocked tool raises `PermissionError` instead of returning a lookup result.
Report that error to the caller; do not retry by changing the allowlist:

```python
try:
    call_tool("delete_everything")
except PermissionError as error:
    print(f"Tool call blocked: {error}")
```

Missing files and malformed benchmark data are operational errors, distinct from
a valid lookup miss. Preserve those exceptions so the dataset can be repaired.

## Published data (R1, checked 2026-11-28)

Every record names the paper id (`data/papers.md`), the table, row and column, the
metric as the paper defines it, and the pinned arXiv version URL. Values were checked
against the arXiv HTML table and the extracted PDF text (`data/chunks.jsonl`). All
values use a 0–100 scale. These are published external results, not measurements of
our own system; different models/tasks/settings are not directly comparable.

| Paper | Tables / method | Records |
|---|---|---|
| `gou2024` [CRITIC, v4](https://arxiv.org/html/2305.11738v4) | Tables 1-2, CRITIC with gpt-3.5-turbo, non-oracle row | AmbigNQ, TriviaQA, HotpotQA `exact_match`/`f1`; GSM8K, SVAMP, TabMWP `accuracy` (9) |
| `yao2023` [ReAct, v3](https://arxiv.org/html/2210.03629v3) | Tables 1, 3, 4, PaLM-540B | FEVER `accuracy`; ALFWorld `success_rate` (average over prompts); WebShop `score`, `success_rate` (4) |
| `shinn2023` [Reflexion, v4](https://arxiv.org/html/2303.11366v4) | Table 1, Reflexion (GPT-4) Pass@1 | HumanEval, MBPP, LeetcodeHardGym `pass_at_1` (3) |
| `madaan2023` [Self-Refine, v2](https://arxiv.org/html/2303.17651v2) | Table 1, GPT-4 + Self-Refine | Sentiment Reversal `win_rate` (GPT-4-pref), Code Optimization `success_rate` (% optimized), Constrained Generation `score` (coverage) (3) |
| `chen2024` [Self-Debug, v2](https://arxiv.org/html/2304.05128v2) | Tables 1(a), 2(b), Codex + explanation | Spider `accuracy`; TransCoder `pass_at_1` (2) |
| `schick2023` [Toolformer, v1](https://arxiv.org/html/2302.04761v1) | Tables 3, 4, 5, 7, Toolformer (GPT-J 6.7B) | LAMA T-REx, ASDiv, Natural Questions, Dateset `accuracy` (lenient criteria, see `source`) (4) |
| `patil2023` [Gorilla, v1](https://arxiv.org/html/2305.15334v1) | Table 1, Gorilla (0-shot) | APIBench-TorchHub, -HuggingFace, -TensorHub `accuracy` (AST match); APIBench-TorchHub `hallucination` (4) |
| `qin2024` [ToolLLM, v2](https://arxiv.org/html/2307.16789v2) | Table 4, ToolLLaMA-DFSDT, oracle APIs | ToolBench `pass_rate`, `win_rate` (2) |
| `huang2024` | no own record: the orchestrator gives Huang tasks the CRITIC GSM8K/HotpotQA records the paper discusses | 0 |
| `kamoi2024` | **no record by design**: a survey with no results table of its own; its numbers are quoted from other papers | 0 |

Choices worth knowing: Self-Refine's Dialogue Response row was left out because the
paper names two different judges for it (Sec 3.2 vs Appendix M). Self-Debug's MBPP
row was left out so that a Reflexion task does not receive another method's MBPP
record (one record per benchmark/metric pair). ToolLLM numbers are from v2; v1 reported
61.0 pass / 68.3 win under an earlier setup. Gorilla's HuggingFace baselines were
scored more leniently than Gorilla (paper Sec 4.1), noted in `source`.

**Coverage:** 23/25 eval tasks (92%) receive at least one `found: true` record
(`python -m eval.task_table`, `tests/test_r1_coverage.py`); the 2 missing tasks are
the Kamoi survey tasks. Huang and ReAct tasks share the CRITIC HotpotQA/GSM8K records
(one record per benchmark/metric pair).

The contract selects one published method per benchmark/metric. Duplicates for the
requested pair raise `ValueError`; adding a method selector requires team agreement on
the shared interface.

## Integration with the orchestrator (Van)

- `orchestrator.PAPER_BENCHMARKS` maps an author pattern in the task input to benchmark
  names; `METRIC_ORDER` lists the metric names to try. New records need both.
- `agents.base.call_agent` appends `UNTRUSTED_CONTENT_POLICY` to every system message.
- Critic and Reflection sanitize the JSON rendering of tool evidence. The raw structured
  result remains in `TraceStep.tool_calls` for debugging and auditing.
- Attack cases and their results: [`../security/attacks/cases.json`](../security/attacks/cases.json),
  `python -m seminar_critique.security.run_attacks`, see
  [the threat model](../security/threat_model.md).

Validation: `python -m pytest`; CLI smoke check:
`python -m seminar_critique.run --task eval/tasks/example_task.json --config C`.
