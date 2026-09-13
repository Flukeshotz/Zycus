"""
Clause Library loader (architecture.md §3 #6, §7.3, D-11).

Only text stored here is ever inserted into a document verbatim (D-51) — the
Clause Analyst may draft its own language when nothing matches, but that is
always labeled ai_drafted, never library.

search() is the deterministic keyword matcher shared by two later callers:
the search_clause_library tool in the live Clause Analyst's research loop
(P3, D-58) and FakeLLM's offline clause matching (P2, D-46) — one
implementation, so offline and live behavior can't quietly drift apart.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

LIBRARY_PATH = Path(__file__).resolve().parent.parent / "data" / "clause_library.yaml"


class ClauseLibraryEntry(BaseModel):
    id: str
    keywords: list[str]
    satisfies: list[str]
    text: str


_CACHE: list[ClauseLibraryEntry] | None = None


def get_library() -> list[ClauseLibraryEntry]:
    global _CACHE
    if _CACHE is None:
        with LIBRARY_PATH.open() as f:
            raw = yaml.safe_load(f)
        _CACHE = [ClauseLibraryEntry.model_validate(item) for item in raw]
    return _CACHE


def get_entry(entry_id: str) -> ClauseLibraryEntry | None:
    for entry in get_library():
        if entry.id == entry_id:
            return entry
    return None


def search(query: str, limit: int = 3) -> list[ClauseLibraryEntry]:
    """Score each entry by how many of its keywords appear in the query text."""
    q = query.lower()
    scored = [
        (sum(1 for kw in entry.keywords if kw.lower() in q), entry)
        for entry in get_library()
    ]
    scored = [(score, entry) for score, entry in scored if score > 0]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in scored[:limit]]
