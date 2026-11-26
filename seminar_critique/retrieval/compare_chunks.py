"""Compare two chunk files before replacing data/chunks.jsonl. Owner: Minh.

    python -m seminar_critique.retrieval.ingest --out data/chunks_new.jsonl
    python -m seminar_critique.retrieval.compare_chunks data/chunks.jsonl data/chunks_new.jsonl

Prints how many chunks were added, removed, relabelled (section changed) or re-cut (text changed).
Only replace data/chunks.jsonl when the changes are the ones you expect, because every
change in the chunks changes what configs B and C see (and so the eval numbers).
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from .chunker import read_jsonl


def compare(old: list[dict], new: list[dict]) -> dict:
    a, b = {c["id"]: c for c in old}, {c["id"]: c for c in new}
    common = a.keys() & b.keys()
    return {
        "old_chunks": len(a),
        "new_chunks": len(b),
        "added": sorted(b.keys() - a.keys()),
        "removed": sorted(a.keys() - b.keys()),
        "relabelled": sorted(i for i in common if a[i]["section"] != b[i]["section"]),
        "text_changed": sorted(i for i in common if a[i]["text"] != b[i]["text"]),
    }


def _sections(rows: list[dict], paper_id: str) -> list[str]:
    """Section labels of one paper in reading order, each once."""
    return list(dict.fromkeys(c["section"] for c in rows if c["paper_id"] == paper_id))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("old", type=Path)
    ap.add_argument("new", type=Path)
    args = ap.parse_args()
    old, new = read_jsonl(args.old), read_jsonl(args.new)
    d = compare(old, new)
    print(f"chunks: {d['old_chunks']} -> {d['new_chunks']}")
    for key in ("added", "removed", "relabelled", "text_changed"):
        per_paper = Counter(i.rsplit("-", 1)[0] for i in d[key])
        print(f"{key:<13} {len(d[key]):>4}  {dict(per_paper) or ''}")
    b = {c["id"]: c for c in new}
    a = {c["id"]: c for c in old}
    for i in d["relabelled"][:10]:
        print(f"  {i}: {a[i]['section']!r} -> {b[i]['section']!r}")
    changed = sorted({i.rsplit("-", 1)[0] for k in ("added", "removed", "relabelled", "text_changed") for i in d[k]})
    for pid in changed:
        print(f"\n{pid} sections")
        print("  old:", " | ".join(_sections(old, pid)))
        print("  new:", " | ".join(_sections(new, pid)))
    if not changed:
        print("IDENTICAL content: ingest reproduces the committed chunks")


if __name__ == "__main__":
    main()
