# Tin: slides, Q&A, contribution and AI-use (draft)

Same layout as `minh_qa_contribution_draft.md`. Facts are from `feature/tin-d3` (28/11);
recheck on `d3-freeze` / `final` and fill `[TBD]` from the Gemini attack run.

## 1. Slides (3 slides, 3.5 minutes incl. live attack demo)

1. **Tools and permissions.** One tool, read-only, 31 published records from 8 papers,
   evidence for 23/25 tasks. Gate: unregistered or non-READ_ONLY tool -> blocked before it
   runs. One audit line per call, same `run_id` as the trace.
2. **Threat model + attack suite.** 3 entry points (material, retrieved chunks, tool
   results) + tool gate; 16 cases, 9 direct / 7 indirect; result table [TBD]; the one
   known gap (AT-14 forged value) stated plainly.
3. **Live demo (one stable case).** Candidate: AT-06 (blocked `write_file`, deterministic,
   no API needed) or AT-02/AT-10 if Gemini resists them in all runs [TBD]. Show the command,
   the `blocked` audit line, and the case log with its `run_id`.

## 2. Likely questions and answers (with evidence)

| Question | Answer | Evidence |
|---|---|---|
| Why is there no human approval step? | Every tool is read-only; the system never writes, sends or buys anything. A write tool would be blocked by the gate before it runs. | `tools/__init__.py::call_tool`, AT-06/07, Section 3 R2 |
| Does wrapping in `<untrusted>` stop prompt injection? | No. It stops delimiter breakout (AT-02/03/11 checks) and tells the model the text is data; whether the model obeys is measured: [TBD k/13 model-level cases succeeded on Gemini]. | `security/results/d3-freeze/summary.md` |
| Which attack succeeded? | AT-14: a forged but plausible number with a real citation passes validation and reaches the Critic. Only human review of the pinned table catches it. [TBD + Gemini successes] | `AT-14.json`, Section 6.4 |
| How do you know the checks are not always true? | Tests run AT-02/03/11 against the pre-D3 sanitizer (no escaping, no look-alike mapping): the harness reports them as succeeded. | `tests/test_attacks.py` |
| How do you link an attack to its trace? | Each case log, its trace file and its audit lines share `run_id = attack-<case>-<config>`. | `security/run_attacks.py::run_case` |
| Where do the benchmark numbers come from? Are they right? | Each record names paper, table, row, column, metric definition and arXiv version; values were checked against the arXiv HTML tables. Kamoi is a survey with no own table, so no record. | `data/benchmarks.json`, `tools/README.md` |
| Why does the Huang task get CRITIC numbers? | Huang et al. discuss CRITIC's GSM8K/HotpotQA results; the tool keeps one record per benchmark/metric pair. | `orchestrator.PAPER_BENCHMARKS` |
| What happens with an empty or wrong file? | CLI stops before any LLM call with a clear message (scenario 2). | `security/scenarios.md`, `security/input_check.py` |
| What did the walkthrough change? | [TBD after the walkthrough 01-02/12] | `security/scenarios.md` |

## 3. Contribution row (form section 5)

| Member | Responsibility | Real outputs | Evidence | Proposed share |
|---|---|---|---|---|
| Tin | Tools and permissions (`tools/`), security (`security/`), attack evaluation, related work; report Sections 2, 3 R2, 6 | D2: read-only benchmark tool, permission registry, sanitizer, threat model. D3: R1 records (13 -> 31, 23/25 tasks), audit log, 16 attack cases + harness, look-alike bracket fix, input check, 3 user scenarios, attack run on `d3-freeze` [TBD], walkthrough [TBD] | D3 commits `cabc681`, `012a6c5`, `88284cc`, `691ac68`, `bdba0ee`, `778175f`, `10b823f`; PR [TBD]; `security/results/d3-freeze/` [TBD] | [TBD, agreed by the group] |

## 4. AI-use statement (Tin) - to complete honestly

- **Tool:** Claude (Anthropic), Claude Opus 5.5, in Claude Code (desktop app), Nov 2026.
  [Add any tool used in D1/D2 if applicable.]
- **Used for:** writing the audit log, attack cases, harness, input check and their
  tests; looking up benchmark numbers in the arXiv HTML tables of the corpus papers;
  drafting docs and report Sections 2, 3 R2 and 6. D3 commits written with AI help carry a
  `Co-Authored-By: Claude` line.
- **What Tin checked personally:** [keep only what is true, e.g. ran `python -m pytest`
  (203 passed) and the offline attack run on his machine; opened each arXiv table and
  compared the record values; read the three `[VERIFY]` related-work papers; ran the
  Gemini attack run on `d3-freeze` and read the case logs of every succeeded case].
