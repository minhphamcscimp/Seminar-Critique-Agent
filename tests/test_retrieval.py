"""Tests for retrieval. Owner: Minh. Offline: no network, no API key."""
import pytest

from seminar_critique.retrieval.chunker import (
    CHUNK_WORDS, OVERLAP_WORDS, chunk_paper, split_into_chunks,
)
from seminar_critique.retrieval.ingest import parse_papers_md, sections_from_text, title_on_first_page

SAMPLE = """
Large Language Models Cannot Self-Correct Reasoning Yet
Abstract
We study self-correction. """ + "word " * 30 + """
1 Introduction
""" + "intro " * 40 + """
2 Method
2.1 Intrinsic self-correction
""" + "method " * 40 + """
References
Some Author. Should not appear.
"""


def test_split_respects_size_and_overlap():
    words = [f"w{i}" for i in range(1000)]
    chunks = split_into_chunks(" ".join(words))
    assert all(len(c.split()) <= CHUNK_WORDS for c in chunks)
    first, second = chunks[0].split(), chunks[1].split()
    assert first[-OVERLAP_WORDS:] == second[:OVERLAP_WORDS]
    assert chunks[-1].split()[-1] == "w999"  # nothing is lost at the end


def test_sections_found_and_references_dropped():
    sections = dict(sections_from_text(SAMPLE))
    assert "Abstract" in sections
    assert "Section 1 Introduction" in sections
    assert "Section 2.1 Intrinsic self-correction" in sections
    assert "Should not appear" not in " ".join(sections.values())


def test_chunk_metadata_is_complete_and_ids_unique():
    paper = {"id": "huang2024", "topic": "self-improvement-reflection",
             "cite": "Huang et al. 2024", "title": "x", "arxiv": "2310.01798"}
    chunks = chunk_paper(paper, sections_from_text(SAMPLE))
    assert chunks
    assert len({c["id"] for c in chunks}) == len(chunks)
    for c in chunks:
        assert c["paper"] == "Huang et al. 2024" and c["section"] and c["text"]


def test_papers_table_parses():
    rows = parse_papers_md()
    assert len(rows) >= 4
    assert {"id", "topic", "cite", "title", "arxiv"} <= set(rows[0])
    assert len({r["id"] for r in rows}) == len(rows)


def test_pdf_roundtrip(tmp_path):
    pymupdf = pytest.importorskip("pymupdf")
    from seminar_critique.retrieval.ingest import pdf_to_text
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72
    for line in ["My Test Paper Title", "Abstract", "short abstract text here", "1 Introduction", "body of the intro", "References"]:
        page.insert_text((72, y), line)
        y += 20
    path = tmp_path / "t.pdf"
    doc.save(path)
    text, first = pdf_to_text(path)
    assert title_on_first_page("My Test Paper Title", first)
    assert "Section 1 Introduction" in dict(sections_from_text(text))


NOISY = """
Large Language Models Cannot Self-Correct Reasoning Yet
1 Work done at Google. 2 UC Berkeley
Abstract
""" + "abstract " * 30 + """
1 INTRODUCTION
""" + "intro " * 40 + """
2 BACKGROUND AND RELATED WORK
""" + "background " * 40 + """
4 Llama 70 12
3 Method
""" + "method " * 40 + """
3.1 Setup
""" + "setup " * 40 + """
References
"""


def test_footnotes_and_table_rows_are_not_headings():
    names = [n for n, _ in sections_from_text(NOISY)]
    assert names == [
        "Abstract", "Section 1 INTRODUCTION", "Section 2 BACKGROUND AND RELATED WORK",
        "Section 3 Method", "Section 3.1 Setup",
    ]


def test_running_header_and_page_numbers_removed():
    from seminar_critique.retrieval.ingest import strip_page_noise
    pages = [
        "Published as a conference paper at ICLR 2024\ntext one\n1",
        "Published as a conference paper at ICLR 2024\n2 Published as a conference paper at ICLR 2024\ntext two\n2",
        "Published as a conference paper at ICLR 2024\ntext three\n3",
    ]
    out = " ".join(strip_page_noise(pages))
    assert "Published as a conference" not in out
    assert "text one" in out and "text three" in out
    assert not any(line.strip() in {"1", "2", "3"} for line in out.split())


def test_bold_marks_decide_headings():
    from seminar_critique.retrieval.ingest import BOLD_MARK
    b = BOLD_MARK.strip() + " "
    text = "\n".join([
        b + "Abstract", "abstract " * 30,
        b + "1 Introduction", "intro " * 30,
        "7 Standard Prompting",            # table label, not bold -> not a heading
        "more intro " * 20,
        b + "2 Method", "method " * 30,
        "References",
    ])
    names = [n for n, _ in sections_from_text(text)]
    assert names == ["Abstract", "Section 1 Introduction", "Section 2 Method"]


def test_pdf_bold_headings(tmp_path):
    pymupdf = pytest.importorskip("pymupdf")
    from seminar_critique.retrieval.ingest import pdf_to_text
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72
    for text, font in [("My Test Paper Title", "hebo"), ("Abstract", "hebo"), ("short abstract text", "helv"),
                       ("1 Introduction", "hebo"), ("body of the intro", "helv"),
                       ("7 Standard Prompting", "helv"), ("2 Method", "hebo"), ("method text", "helv"),
                       ("References", "hebo")]:
        page.insert_text((72, y), text, fontname=font)
        y += 20
    path = tmp_path / "bold.pdf"
    doc.save(path)
    text, _ = pdf_to_text(path)
    names = [n for n, _ in sections_from_text(text)]
    assert names == ["Abstract", "Section 1 Introduction", "Section 2 Method"]


# ---- retriever, graph, stats (use the committed data/chunks.jsonl) ----
from seminar_critique.retrieval import retrieve  # noqa: E402
from seminar_critique.retrieval.retriever import get_index, retrieve_with  # noqa: E402
from seminar_critique.retrieval.stats import compute  # noqa: E402

REFLECTION = "self-improvement-reflection"
TOOLS = "tool-use-mcp"


def test_retrieve_returns_k_real_chunks():
    chunks = retrieve("self-correction without external feedback", REFLECTION, 5)
    assert len(chunks) == 5
    assert all(c.paper and c.section and c.text and c.score > 0 for c in chunks)
    assert "Huang et al. 2024" in {c.paper for c in chunks}   # the paper that makes this claim


def test_retrieve_stays_inside_topic():
    ix = get_index()
    tool_papers = {ix.chunks[i]["paper"] for i in ix.by_topic[TOOLS]}
    chunks = retrieve("language models that call APIs and tools", TOOLS, 5)
    assert {c.paper for c in chunks} <= tool_papers


def test_unknown_topic_and_empty_query_still_return_chunks():
    assert len(retrieve("zzzz qqqq", REFLECTION, 3)) == 3     # no match
    assert len(retrieve("self-correction", "no-such-topic", 3)) == 3


def test_graph_expansion_changes_ranking_and_scores_sorted():
    q = "does the baseline compare fairly with self-consistency"
    plain = retrieve_with(q, REFLECTION, 5, expand=False)
    graph = retrieve_with(q, REFLECTION, 5, expand=True)
    assert [c.score for c in graph] == sorted((c.score for c in graph), reverse=True)
    assert [c.id for c in plain] != [c.id for c in graph]


def test_stats_match_data():
    s = compute()
    assert s["papers"] == len({c["paper_id"] for c in get_index().chunks})
    assert s["graph"]["nodes"] == s["papers"] + s["chunks"]
    assert s["graph"]["edges_by_kind"]["adjacent"] > 0 and s["graph"]["edges_by_kind"]["similar"] > 0


def test_falls_back_when_bold_gives_too_few_sections():
    from seminar_critique.retrieval.ingest import BOLD_MARK
    b = BOLD_MARK.strip() + " "
    body = "\n".join(f"{n} {name}\n" + "word " * 40 for n, name in
                     [(1, "Introduction"), (2, "Method"), (3, "Results"), (4, "Discussion"), (5, "Conclusions")])
    text = b + "Abstract\n" + "abstract " * 30 + "\n" + body + "\nReferences"   # numbered headings not bold
    names = [n for n, _ in sections_from_text(text)]
    assert "Section 2 Method" in names and len(names) >= 5


def test_pdf_number_and_title_in_separate_spans(tmp_path):
    pymupdf = pytest.importorskip("pymupdf")
    from seminar_critique.retrieval.ingest import pdf_to_text
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72
    rows = [("Abstract", None), ("abstract text " * 6, None), ("1", "INTRODUCTION"), ("intro text " * 6, None),
            ("2", "METHOD"), ("method text " * 6, None), ("3", "RESULTS"), ("result text " * 6, None),
            ("4", "DISCUSSION"), ("discussion text " * 6, None), ("5", "CONCLUSION"), ("end text " * 6, None),
            ("References", None)]
    for left, right in rows:
        if right:
            page.insert_text((72, y), left, fontname="hebo")
            page.insert_text((100, y), right, fontname="hebo")
        else:
            bold = left in ("Abstract", "References")
            page.insert_text((72, y), left, fontname="hebo" if bold else "helv")
        y += 20
    path = tmp_path / "split.pdf"
    doc.save(path)
    text, _ = pdf_to_text(path)
    names = [n for n, _ in sections_from_text(text)]
    assert names == ["Abstract", "Section 1 INTRODUCTION", "Section 2 METHOD", "Section 3 RESULTS",
                     "Section 4 DISCUSSION", "Section 5 CONCLUSION"]


def test_table_values_and_footnotes_are_not_headings():
    from seminar_critique.retrieval.ingest import BOLD_MARK
    text = "\n".join([
        "Abstract", "abstract " * 30,
        "1 Introduction", "intro " * 30,
        "1.0 Proportion of Solved Environments",                         # axis label
        "3.13 Claude (0-shot)",                                           # table value
        "2 We discard all examples where M does not generate the",       # footnote sentence
        "2 Method", "method " * 30,
        "2.1 Setup", "setup " * 30,
        "3 Results", "results " * 30,
        "4 Discussion", "discussion " * 30,
        "5 Conclusion", "end " * 30,
        "References",
    ])
    names = [n for n, _ in sections_from_text(text)]
    assert names == ["Abstract", "Section 1 Introduction", "Section 2 Method", "Section 2.1 Setup",
                     "Section 3 Results", "Section 4 Discussion", "Section 5 Conclusion"]


def test_garbled_lines_dropped_but_headings_kept():
    from seminar_critique.retrieval.ingest import drop_garbled_lines
    text = "\n".join([
        "2QWKHFDELQHW\\RXVHHDYDVHLWHPXVLQJDWDEOH",
        "This is a normal sentence about the method and the results.",
        "3 Reflexion: reinforcement via verbal reflection",
    ])
    out, n = drop_garbled_lines(text)
    assert n == 1 and "normal sentence" in out and "Reflexion" in out and "QWKH" not in out


def test_garbled_heading_is_rejected_and_references_not_counted():
    from seminar_critique.retrieval.ingest import drop_garbled_lines
    text = "\n".join([
        "Abstract", "this is the abstract of the paper " * 8,
        "1 Introduction", "this is the intro of the paper " * 8,
        "2 EV 2QWKHFDELQHW\\RXVHHDYDVH",
        "4 XHVWLRQ $V",
        "2 Method", "this is the method of the paper " * 8,
        "3 Results", "these are the results of the paper " * 8,
        "4 Discussion", "this is the discussion of the paper " * 8,
        "References",
        "Madaan Aman Tandon Niket Gupta Prakhar Hallinan Skyler",   # reference list, no common word
    ])
    names = [n for n, _ in sections_from_text(text)]
    assert not any("QWKH" in n or "XHVW" in n for n in names)
    assert drop_garbled_lines(text)[1] == 0


def test_garbled_headings_with_symbols_or_very_long_words_rejected():
    text = "\n".join([
        "Abstract", "this is the abstract of the paper " * 8,
        "1 Introduction", "this is the intro of the paper " * 8,
        "2 EV 1RWKLQJKDSSHQV>@",
        "2 EV <RXSLFNXSWKHKHSSHUVKDNHUIURPWKHFRXQWHUWRS",
        "2 Method", "this is the method of the paper " * 8,
        "3 Results", "these are the results of the paper " * 8,
        "4 Discussion", "this is the discussion of the paper " * 8,
        "References",
    ])
    names = [n for n, _ in sections_from_text(text)]
    assert names == ["Abstract", "Section 1 Introduction", "Section 2 Method", "Section 3 Results", "Section 4 Discussion"]


def test_max_per_paper_keeps_one_paper_from_taking_all_slots():
    from collections import Counter
    q = "How does a language model decide which API to call"
    capped = retrieve_with(q, TOOLS, 5)
    assert max(Counter(c.paper for c in capped).values()) <= 3
    assert len({c.paper for c in capped}) >= 2
    uncapped = retrieve_with(q, TOOLS, 5, max_per_paper=None)
    assert len(uncapped) == 5


def test_heading_with_control_characters_rejected():
    # ReAct (yao2023): a figure label with a broken font became "Section 2 EV\x03\x16 \x03)URQW..."
    text = "\n".join([
        "Abstract", "this is the abstract of the paper " * 8,
        "1 Introduction", "this is the intro of the paper " * 8,
        "2 EV\x03\x16 \x03)URQW\x035RZ\x03LV\x03D \x03",
        "2 Method", "this is the method of the paper " * 8,
        "3 Results", "these are the results of the paper " * 8,
        "References",
    ])
    names = [n for n, _ in sections_from_text(text)]
    assert names == ["Abstract", "Section 1 Introduction", "Section 2 Method", "Section 3 Results"]


# ---- every eval task (D3: run on all tasks in eval/tasks/, including new ones) ----
from seminar_critique.retrieval.check_tasks import check_task, load_tasks, target_papers  # noqa: E402

TASKS = load_tasks()
MIN_HIT_RATE = 0.8   # misses are allowed (report examples), a drop below this is a regression


@pytest.mark.parametrize("task", TASKS, ids=[t["id"] for t in TASKS])
def test_every_task_gets_k_chunks_with_source(task):
    ix = get_index()
    topic_papers = {ix.chunks[i]["paper"] for i in ix.by_topic[task["topic"]]}
    chunks = retrieve(task["input"][:200], task["topic"], 5)   # same query as the orchestrator
    assert len(chunks) == 5
    assert all(c.paper and c.section and c.text for c in chunks)
    assert {c.paper for c in chunks} <= topic_papers


@pytest.mark.parametrize("task", TASKS, ids=[t["id"] for t in TASKS])
def test_every_task_names_the_paper_under_critique(task):
    # The check needs "Surname et al." of a corpus paper in the task input.
    assert target_papers(task), f"{task['id']}: input does not cite a paper of topic {task['topic']}"


def test_paper_under_critique_is_retrieved_for_most_tasks():
    rows = [check_task(t) for t in TASKS if target_papers(t)]
    hits = sum(r["graph"]["hit"] for r in rows)
    assert hits / len(rows) >= MIN_HIT_RATE, [r["task_id"] for r in rows if not r["graph"]["hit"]]


def test_all_caps_title_after_bare_number_is_a_heading_even_if_not_bold():
    # ReAct (ICLR small caps): "2" and "REAC T: SYNERGIZING REASONING + ACTING" are separate, non-bold lines.
    from seminar_critique.retrieval.ingest import BOLD_MARK, drop_garbled_lines
    b = BOLD_MARK.strip() + " "
    text = "\n".join([
        b + "Abstract", "this is the abstract of the paper " * 8,
        "1", b + "INTRODUCTION", "this is the intro of the paper " * 8,
        "2", "REAC T: SYNERGIZING REASONING + ACTING", "this is the method of the paper " * 8,
        "3", "KNOWLEDGE-INTENSIVE REASONING TASKS", "these are the tasks of the paper " * 8,
        b + "3.1", b + "SETUP", "this is the setup of the paper " * 8,
        "References",
    ])
    kept, _ = drop_garbled_lines(text)
    names = [n for n, _ in sections_from_text(kept)]
    assert "Section 2 REAC T: SYNERGIZING REASONING + ACTING" in names
    assert "Section 3 KNOWLEDGE-INTENSIVE REASONING TASKS" in names


def test_lowercase_line_after_bare_number_is_not_a_heading():
    text = "\n".join([
        "Abstract", "this is the abstract of the paper " * 8,
        "1 Introduction", "this is the intro of the paper " * 8,
        "2", "the next line is a sentence that wraps after a number",
        "2 Method", "this is the method of the paper " * 8,
        "References",
    ])
    names = [n for n, _ in sections_from_text(text)]
    assert names == ["Abstract", "Section 1 Introduction", "Section 2 Method"]


def test_table_rows_and_figure_axes_are_not_headings():
    # Huang 2024: "5 / GPT-4" table row; ToolLLM: "1 2 3 / APIs & API" figure axis;
    # Self-Debug: "5.8 Wrong COUNT columns" table value after 5.2.3. Real headings must survive.
    text = "\n".join([
        "ABSTRACT", "this is the abstract of the paper " * 8,
        "1", "INTRODUCTION", "this is the intro of the paper " * 8,
        "2", "BACKGROUND AND RELATED WORK", "this is the background of the paper " * 8,
        "2.1", "SETUP", "this is the setup of the paper " * 8,
        "2.2", "RESULTS", "these are the results of the paper " * 8,
        "2.2.1", "ERROR TYPES", "these are the error types of the paper " * 8,
        "5", "GPT-4", "75.9", "1", "2", "3", "APIs & API",
        "2.8", "Wrong COUNT columns", "more results of the paper " * 8,
        "3", "MULTI-AGENT DEBATE DOES NOT OUTPERFORM SELF-CONSISTENCY", "this is the debate part " * 8,
        "References",
    ])
    names = [n for n, _ in sections_from_text(text)]
    assert names == ["Abstract", "Section 1 INTRODUCTION", "Section 2 BACKGROUND AND RELATED WORK",
                     "Section 2.1 SETUP", "Section 2.2 RESULTS", "Section 2.2.1 ERROR TYPES",
                     "Section 3 MULTI-AGENT DEBATE DOES NOT OUTPERFORM SELF-CONSISTENCY"]
