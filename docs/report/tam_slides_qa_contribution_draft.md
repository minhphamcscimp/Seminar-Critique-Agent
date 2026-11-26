# Tam: slides, Q&A, contribution and AI-use (draft)

Draft for Tam's own deliverables. Numbers marked [TBD] come from `eval/results/summary.md`
after the official run; numbers marked *(trial)* are from the 26/11 live runs.

## 1. Slides (2-3, Tam's 6-minute part: evaluation, ablation, cost/latency, changes, limits)

**Slide 1: How we evaluate.**
- 25 tasks, 2 topics, 10 papers (each >= 2 tasks); 3 configs x 3 repeats = 225 runs.
- A = 1 call; B = 3 agents + GraphRAG + benchmark tool; C = B + reflection (external evidence only).
- Two scores: phrase match (deterministic) and LLM judge (semantic), judge checked against 2 humans on 15 cases.

**Slide 2: Results.** Table: success rate, score mean +/- SD, judge score, cost/task, latency/task
per config [TBD]. One sentence: "B vs A: [TBD]; C vs B: [TBD]. Differences within one SD
are not claimed."

**Slide 3: What we learned / limits.**
- Phrase scoring understated B: on the 3 D2 tasks where B "lost" to A, the judge found
  every key point in B (B paraphrases) *(trial, 3 tasks)*.
- Reflection changed the answer in [TBD x/75] C runs; costs [TBD] more tokens.
- Cost: about 0.0013 USD and 51 s per critique with C *(trial, 1 task)*; for 32 students x
  1 critique/week: about [TBD] USD and [TBD] min per week (estimate).
- Limits: small sample, 2 topics, one model family, judge = same family.

## 2. Likely questions and answers (with evidence)

| Question | Answer | Evidence |
|---|---|---|
| Why is C not better than B? | Reflection may only use external evidence; the tool returns records for few tasks, and the loop stops when the evidence changes nothing. Measured: [TBD] C runs changed the answer. | `summary.md` Reflection (R4) table, `eval/results/r5_analysis.md` |
| Why trust the LLM judge? | It only checks the listed key points, blind to the config; agreement with two humans on 15 cases: kappa [TBD]. | `eval/judge.md`, `eval/results/agreement.md` |
| Why did B score below A in D2? | Phrase-match artefact: B paraphrases; judge says B covers all key points on those 3 tasks. | `eval/results/r5_analysis.md`, `docs/examples/r5/` |
| Is the difference significant? | We report mean +/- SD and paired per-task differences; we make no claim when the difference is within one SD. | `summary.md` Paired differences |
| Where do the tasks come from? | Written from cited sections of the 10 corpus papers (field `source`); [TBD: checked against the seminar handout]. | `eval/tasks/*.json`, `eval/TASKS.md` |
| Could the model have memorised the papers? | Possible; A (no retrieval) is the control, and tasks ask to critique a claim, not to recall. | Section 5.8 |
| How long and how much for the whole class? | Measured per critique, scaled to 32 students/week (estimate, marked as such). | `run_info.md`, Section 5.9 |
| Why temperature 0 and only 3 repeats? | Same setting for all configs; repeats measure run-to-run noise ("SD over repeats"). | `summary.md` |
| Can the results be reproduced? | `python -m eval.summarize` rebuilds the tables from the committed CSVs; `python -m eval.official` re-runs live on the tag. | `eval/README.md` |

## 3. Contribution row (form section 5)

| Member | Responsibility | Real outputs | Evidence | Proposed share |
|---|---|---|---|---|
| Tam | Evaluation (`eval/`), report Sections 5 and 7 | 25-task set; runner with error/retry/R4/R1 columns; summary with SD and paired differences; LLM judge; human-agreement tooling; R5 analysis; error analysis; official run | commits on `feature/tam-d3`, PR [TBD], `eval/results/` | [TBD, agreed by the group] |

## 4. AI-use statement (Tam) - to complete honestly

- **Tool:** Claude (Anthropic), used through Claude Code, Nov 2026.
- **Used for:** writing and testing code in `eval/` (runner, summarize, judge, agreement,
  error analysis, official run), drafting the 16 new tasks from paper chunks, running the
  live trial and R5 analysis, drafting Sections 5 and 7.
- **What Tam checked personally:** [TBD: e.g. read each task against its cited paper
  section; reran the tests; read the R5 traces; checked the numbers in the report against
  `results.csv`]. Write only what was actually checked.
