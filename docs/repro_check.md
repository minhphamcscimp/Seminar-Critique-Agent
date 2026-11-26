# Reproducibility check (clean checkout)

Owner: Minh. Each entry = clone into an empty folder, new virtual environment, follow the README only.
The final entry (on tag `final`) is the one the report refers to.

## 2026-11-26, branch `feature/minh-d3`, commit `1e5254e` (pinned requirements)

| | Run 1 | Run 2 |
|---|---|---|
| Machine / OS | Windows (laptop), PowerShell | Linux container |
| Python | 3.14.5 | 3.13.18 |
| Install (`python -m pip install -r requirements.txt`) | 65 s, some wheels from pip cache | 11 s |
| `python -m pytest` | 95 passed, 1 warning | 95 passed |
| Demo `python -m seminar_critique.run --task eval/tasks/example_task.json --config C` (FakeLLM) | OK: steps=5, cost_usd=0, trace `traces/C/example-01_run0.json` | OK |
| `python -m eval.summarize` on the committed `results.csv` | `summary.md` regenerated, no diff | no diff |
| Live run (Gemini) | not run (offline check only) | not run |

Problems found and fixes:

1. **Windows Application Control blocks `pip.exe` in `.venv`** ("An Application Control policy has
   blocked this file"). Fix: call `python -m pip`, `python -m pytest`. Written in the README.
2. **`python eval/summarize.py` fails** with `ModuleNotFoundError: seminar_critique`. Fix: run it as a
   module, `python -m eval.summarize`. Written in the README.
3. **The README Quick start overwrote the real results.** `python -m eval.runner --repeats 3` defaults
   to FakeLLM and writes `eval/results/results.csv`. Fix: README now passes
   `--out eval/results/results_fake.csv` for offline runs (file ignored by git) and warns about it.
4. **Quick start had no venv / `.env` / Python version step.** Added.
5. Not a failure: only the 7 direct dependencies are pinned; sub-dependencies resolved to slightly
   newer versions on the new venv (for example `anyio` 4.16.0 vs 4.15.1). Tests still pass.

pytest warning on Python 3.14 only: `backoff` uses `asyncio.iscoroutinefunction`, deprecated and
removed in Python 3.16. No effect on 3.11-3.15.

## 2026-11-26, rebuilding `data/chunks.jsonl` from the arXiv PDFs

`python -m seminar_critique.retrieval.ingest --no-download --out data/chunks_new.jsonl`, then
`python -m seminar_critique.retrieval.compare_chunks data/chunks.jsonl data/chunks_new.jsonl`,
on Windows (Python 3.14.5) and Linux (Python 3.13.18) with the same 10 PDFs.

- With the D2 ingest code, 9 of 10 papers rebuild to exactly the committed chunks. Only ReAct (yao2023)
  differed, because of the control-character guard added the same day. Both machines gave the same output,
  and two runs on Linux gave byte-identical files.
- The comparison showed wrong section labels from the D2 parser in 5 papers. They were fixed in `ingest.py`
  and `data/chunks.jsonl` was rebuilt (299 chunks before and after):

| Paper | D2 label problem | Cause | After the fix |
|---|---|---|---|
| huang2024 | Sections 3-5 missing; fake "5 GPT-4", "6 Self-Consistency", "7 Standard Prompting (ours)" | table rows taken as headings; numbering then blocked the real 4 and 5 | Sections 1-7 as in the paper |
| yao2023 | "Section 2 EV\x03)URQW..." (broken font), Section 3 missing | figure text taken as heading; small-caps titles not bold; 19-letter hyphenated word rejected | Sections 1-6 with 3.1-3.3 |
| qin2024 | "Section 3 APIs & API" | figure axis "1 2 3" taken as heading numbers | Section 3 EXPERIMENTS |
| gou2024 | 4.2 missing | small-caps title not bold | 4.2 MATHEMATICAL PROGRAM SYNTHESIS |
| chen2024 | fake "5.8 Wrong COUNT columns" | table value after 5.2.3 | removed |

Still open (known limitation): shinn2023, schick2023 and patil2023 print their section numbers in a way
the text extraction loses, so only named sections (Introduction, Related Work, Limitations, Conclusion)
are found; kamoi2024 keeps only some subsections. A parser based on the PDF outline (`get_toc()`, present
in 8 of the 10 PDFs) would fix this.

## Final check on tag `final` (to do 04-05/12)

| | Result |
|---|---|
| Date / OS / Python | |
| Commit (`git rev-parse final`) | |
| Install time | |
| `python -m pytest` | |
| Demo 1 task live (`--llm gemini`) | |
| `python -m eval.summarize` reproduces `summary.md` | |
| Problems and fixes | |
