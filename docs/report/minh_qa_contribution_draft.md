# Minh: Q&A, contribution and AI-use (draft)

Draft for Minh's own deliverables (same layout as `tam_slides_qa_contribution_draft.md`).
Numbers come from `main` at `1378533` (27/11); recheck them on tag `d3-freeze` / `final`.
Slides: see the team slide deck (Memory + GraphRAG part, 1.5 minutes).

## 1. Likely questions and answers (with evidence)

| Question | Answer | Evidence |
|---|---|---|
| Why no episodic memory? | Each task is an independent critique. Memory across runs would leak answers between the 3 repeats, so SD would no longer measure run-to-run noise. Agents have no write path, so injected text cannot persist. | `orchestrator.py` (stateless calls), report Section 3 R3 |
| What does GraphRAG add over plain BM25? | At paper level nothing on our set: both find the paper under critique for 25/25 tasks. The graph changes 1-4 of the 5 chunks per task (mean 2.6), moves the target up in 1 task and down in 2. We did not ablate the graph in A/B/C, so its effect on critique quality is not measured. | `retrieval/task_check.json`, `retrieve_with(..., expand=False)` |
| How big is the knowledge base, how is it indexed? | 10 papers, 2 topics, 299 chunks of <= 250 words (40 overlap). BM25 (k1 = 1.5, b = 0.75) + 1-step expansion over 762 edges (adjacent, similar, cites); max 3 chunks per paper. | `retrieval/stats.json` |
| Give one retrieval failure. | `huang-intrinsic-self-correction`: 3 of 5 chunks come from the Kamoi survey; Huang's Section 3 results are not retrieved. Lexical match on "self-correction". | `retrieval/task_check.json` |
| How do you know the chunks are right? | Rebuilt from the arXiv PDFs on 2 machines: the D2 parser reproduces 9/10 papers exactly. The rebuild found wrong section labels in 5 papers (Huang had table rows as headings), fixed and tested. 3 papers still lose section numbers. | `docs/repro_check.md`, `tests/test_retrieval.py`, PR #15 |
| Can the instructor reproduce the system? | Clean checkout on Windows (Python 3.14.5) and Linux (3.13.18): install, 1 demo command, tables rebuilt exactly by `python -m eval.summarize`. Dependencies pinned. | README, `docs/repro_check.md` |
| Are you allowed to store paper text? | 6 papers are CC BY 4.0; 2 use the arXiv non-exclusive license; 2 unconfirmed. [Team decision on repo visibility.] | report Section 8 |
| Is retrieved text trusted? | No: every chunk passes `sanitize_untrusted` before the Summarizer (threat model entry point 2). | `agents/summarizer.py` |

## 2. Contribution row (form section 5)

| Member | Responsibility | Real outputs | Evidence | Proposed share |
|---|---|---|---|---|
| Minh | Repo set-up and management; GraphRAG retrieval (`retrieval/`, `data/`); reproducibility (README, pinned deps, clean checkout); team slide template (Vân assembles the final deck); report Section 3 R3 and Section 8 | Repo skeleton and contracts; ingest, chunker, graph, BM25 + graph retriever, stats; per-task retrieval check (25/25); section-label fix and corpus rebuild; README quick start / reproducibility; `docs/repro_check.md`; R3 + Ethics drafts; team slide template + 2 Memory/GraphRAG slides | PR #1, #2 (D2), #15, #17 (D3); commits `8db398b`, `7387ec1`, `f333151`, `53f0fc0`, `1e5254e`, `593ab7f`, `52301c2`, `b71b024`, `ca61de4` | [TBD, agreed by the group] |

## 3. AI-use statement (Minh) - to complete honestly

- **Tool:** Claude (Anthropic), Claude Opus 5.5, used through Claude Cowork, Nov 2026.
  [Add any tool used in D1/D2 if applicable.]
- **Used for:** step-by-step git/PowerShell guidance; writing and testing `check_tasks.py`,
  `compare_chunks.py` and the section-parsing fixes in `ingest.py` (with tests); a clean
  checkout on Linux; rewriting README quick start and reproducibility; looking up the arXiv
  licenses; drafting report Section 3 R3 and Section 8, the Q&A above and the slides.
  D3 commits written with AI help carry a `Co-Authored-By: Claude` line.
- **What Minh checked personally:** [keep only what is true, e.g. ran `python -m pytest` on
  his own machine after each change (118, then 170 passed); ran the clean checkout and the
  corpus rebuild on Windows and read the old/new section lists before replacing the chunks;
  checked the R3 numbers against `stats.json` and `task_check.json`; read the section labels
  of Huang et al. 2024 against the PDF].
