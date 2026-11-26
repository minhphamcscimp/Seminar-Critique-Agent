# R5: why B scored below A on 3 tasks (D2)

Owner: Tam. Run 2026-11-26 on branch `feature/tam-d3` (before `d3-freeze`),
model `gemini-3.1-flash-lite`, temperature 0, 1 repeat, configs A and B only.

```
python -m eval.runner --llm gemini --tasks <the 3 task files> --configs A B --repeats 1 \
    --out eval/results/results_r5.csv --traces traces/r5
python -m eval.judge --llm gemini --results eval/results/results_r5.csv --out eval/results/judge_r5.csv
python -m eval.keypoint_trace --results eval/results/results_r5.csv --traces-dir traces/r5 --worse-than A --config B
```

Traces are copied to `docs/examples/r5/<config>_<task>_run0.json` (the `trace_path`
in the CSV points to `traces/r5/`, which is not committed).

## Result

The live re-run reproduces the D2 phrase scores exactly, but the LLM judge finds that
B covers every key point in all 3 tasks:

| Task | A phrase recall | B phrase recall | A judge | B judge |
|---|---|---|---|---|
| reflexion-memory | 0.75 | 0.25 | 1.00 | 1.00 |
| self-refine-feedback | 0.50 | 0.00 | 0.75 | 1.00 |
| toolformer-api-selection | 0.50 | 0.00 | 1.00 | 1.00 |

## Cause, one line per task

- **reflexion-memory** (`docs/examples/r5/B_reflexion-memory_run0.json`): B says
  "converts environment feedback into verbal, self-reflective text" and "verbal feedback
  instead of weight updates"; the phrases "task feedback" and "without updating model
  weights" never appear. The Summarizer already rewords them (lost from step 1).
- **self-refine-feedback** (`docs/examples/r5/B_self-refine-feedback_run0.json`): B
  writes "a single LLM generates, critiques, and refines its own output through multiple
  cycles" instead of "same LLM" / "iterative feedback". "supervised training data" is in
  the Summarizer output and dropped by the Critic.
- **toolformer-api-selection** (`docs/examples/r5/B_toolformer-api-selection_run0.json`):
  B writes "determine when and how to invoke external APIs" instead of "which APIs to
  call"; "arguments" is in the Summarizer output and dropped by the Critic.

## Conclusion for Vân

B does not lose the ideas; the three-agent pipeline paraphrases more than one direct call,
and the literal phrase scorer cannot see paraphrases. The D2 finding "B loses to A on 3
tasks" is a **measurement artefact**, not a pipeline fault, so no change to the agents is
needed before the freeze for this reason. Consequences:

1. Section 5 must use the judge score next to the phrase score; the phrase score alone
   understates B. Judge reliability is checked by the human sample (R6).
2. Secondary observation, not a defect: the Summarizer summarises the paper (problem,
   method, setup, results) and the final critique reviews the paper in general, while
   the task asks to critique one specific claim. Worth one sentence in the error analysis.

Sample size: 3 tasks, 1 repeat each. This explains these 3 tasks only.
