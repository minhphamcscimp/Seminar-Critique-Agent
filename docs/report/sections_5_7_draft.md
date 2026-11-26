# Draft: Section 5 Evaluation and Section 7 Limitations (Tam)

Status: **draft before the official run.** Method text is final unless the team changes
the configs (R3). Every `[TBD: ...]` is filled from `eval/results/summary.md`,
`judge.csv`, `agreement.md` after the run on `d3-freeze`. Target length: 1.75 + 0.4 pages.
Numbers marked *D2* are from the committed D2 run (9 tasks) and only motivate the design.

---

## 5 Evaluation

### 5.1 Questions

- **Q1 (system vs baseline).** Does the multi-agent pipeline with retrieval and the
  benchmark tool (B) produce critiques that cover more of the expected points than one
  LLM call (A), and at what extra cost and latency?
- **Q2 (reflection).** Does a reflection loop that may only use external evidence (C)
  change or improve B's critiques?
- **Q3 (measurement).** Does the automatic score agree with human judgment?

### 5.2 Task set

25 critique tasks over the two topics kept from D2: 13 *self-improvement-reflection*,
12 *tool-use-mcp*, covering all 10 papers of the corpus (each by 2-3 tasks).
Each task gives an over-reaching claim about one paper and 3-5 key points a good
critique should make, taken from a cited section of that paper (field `source`);
difficulty: [TBD: n easy / n medium / n hard]. Retrieval returns a chunk of the paper
under critique in the top-5 for 25/25 tasks. Tasks were written by the team from the
papers [TBD: and checked against the "Key defense points" of the seminar handout].

### 5.3 Configurations and hypotheses

| Config | Changes vs previous | Calls per task |
|---|---|---|
| A | one LLM call, no pipeline | 1 |
| B | Summarizer -> Critic -> Synthesizer, with GraphRAG retrieval and the read-only benchmark tool | 3 |
| C | B + reflection loop, at most 2 iterations, external evidence only, early stop on "no change" | 3-5 |

Same model ([TBD: gemini-3.1-flash-lite]), temperature 0, same 25 tasks, 3 repeats.

- **H1 (A vs B):** B has higher key-point coverage than A. A and B differ in three
  components at once (agent split, retrieval, tool), so H1 tests the *system*, not one
  component. [TBD if the team adds a B-without-retrieval ablation; otherwise say so here.]
- **H2 (B vs C):** C differs from B only in the reflection loop. H2: C changes the
  answer in a measurable share of runs and does not lower coverage.

### 5.4 Metrics

- **Success rate:** share of runs with verdict *pass* (at least half of the key points
  covered). Runs that end in an error count as failures.
- **Score:** key-point recall by literal phrase match (deterministic), mean and SD
  over runs; SD over the 3 repeats shows run-to-run noise.
- **LLM judge:** semantic key-point coverage by [TBD: model], blind to the config;
  prompt in Appendix [TBD] and `eval/judge.md`.
- **Cost / latency per task:** tokens x paid-tier price of 2026-10-24 (free tier was
  used, real bill 0 USD); wall-clock seconds per run.
- **Reflection effect (R4):** reflection calls per C run and share of C runs where the
  final answer differs from the Synthesizer draft.

### 5.5 Results

Table [TBD]: main results (`summary.md`, template of form section 2).

| Config | Success rate | Score (mean +/- SD) | Judge score | Tokens / task | Cost / task (USD) | Latency / task (s) | Errors / retries |
|---|---|---|---|---|---|---|---|
| A | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |
| B | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |
| C | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |

Paired per-task differences: B-A [TBD +/- SD, better/equal/worse], C-B [TBD].
Rule: we do not claim an improvement when the mean difference is within its SD.
*D2 reference:* B-A = 0.037 +/- 0.429 over 9 tasks (5 better, 1 equal, 3 worse) and
C = B on all 9 tasks: neither difference was evidence of improvement.

Reflection (R4): C made [TBD] reflection calls per run on average and changed the
final answer in [TBD x/75] runs.

### 5.6 Judge reliability (R6)

15 cases (5 tasks x A/B/C, so every task has a B/C pair) labelled independently by
two team members, per key point. Agreement (Cohen's kappa): human-human [TBD],
human-judge [TBD] / [TBD] (`agreement.md`). [TBD: does the judge see a B/C difference?]

### 5.7 Error analysis

[TBD: >= 10 traces with low score or errors read by hand.] Categories, counts and shares:

| Category | Count | Share | Example (task_id, trace) |
|---|---|---|---|
| Key point lost between agents (found by Summarizer/Critic, dropped later) | [TBD] | | |
| Key point never produced | [TBD] | | |
| Paraphrase missed by the phrase scorer (judge says covered) | [TBD] | | |
| Pipeline error (timeout, empty or broken output) | [TBD] | | |

`python -m eval.keypoint_trace` shows, per key point, which agent step first lost it.
*D2:* B scored below A on `self-refine-feedback`, `toolformer-api-selection`
(0.0 vs 0.5) and `reflexion-memory` (0.25 vs 0.75). A live re-run (26/11) reproduced these
phrase scores, but the judge found B covers all key points in all three (A: 1.0, 0.75, 1.0):
B paraphrases ("when and how to invoke external APIs" for "which APIs to call"), which the
phrase scorer cannot match (`eval/results/r5_analysis.md`). The phrase score therefore
understates the pipeline; we report both scores.

### 5.8 Contamination

All 10 papers (2022-2024) are older than the model's training cutoff, so the model may
know them. The tasks ask for critique of a stated claim rather than recall, and
A (no retrieval) is the control for what the model knows on its own; we cannot rule
out that memorised critiques inflate all configs equally.

### 5.9 Operational limits (AT)

Measured: C costs [TBD] USD and [TBD] s per critique. For 32 students x 1 critique per
week, that is about [TBD = 32 x cost] USD and [TBD = 32 x latency / 60] minutes of
sequential run time per week (estimate, assuming the same input length and the rate
limit of 10 requests/minute). With the free-tier limit of [TBD] requests per day,
[TBD] critiques fit in one day.

---

## 7 Limitations

**Design.** Two topics and 10 papers only (narrowed from 4 topics in the proposal);
one model family; reflection may only use benchmark-tool evidence, which exists for
[TBD] of 25 tasks; key points were written by the team.

**Measurement.** 25 tasks x 3 repeats is a small sample: differences within one SD are
not claimed. The phrase scorer misses paraphrases; the judge is the same model family
as the system (self-preference) and only checks the listed key points; human agreement
was measured on 15 cases. Temperature 0 makes repeats almost identical, so the SD over
repeats underestimates the variance across tasks. Costs are converted at paid-tier
prices; latency depends on the API's load and our 6 s pacing.

**Not verified.** Whether students write better critiques with the tool (only one
walkthrough, Section 6); behaviour on papers outside the corpus; other models.
We do not generalise beyond these 25 tasks.
