"""
Paragraph-based chunking, MVP version.

Design note for the write-up: paragraph chunking is the simplest strategy
and a reasonable starting point, but it has a real weakness — a paragraph
that's one sentence long becomes a weak, low-context chunk, and a very long
paragraph can dilute a chunk's focus across too many ideas.

Once the pipeline is working end to end, worth revisiting: merge short
paragraphs with neighbors, or split by a target token count instead of
paragraph boundaries. That's a good "v1 vs v2" comparison for the essay.
"""

import re
import uuid

from schema import Chunk, SourceDocument

MIN_CHUNK_CHARS = 200  # merge paragraphs shorter than this into neighbors


def split_into_paragraphs(text: str) -> list[str]:
    """Split markdown/plain text on blank lines, drop empty results."""
    raw_paragraphs = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in raw_paragraphs if p.strip()]


def merge_short_paragraphs(paragraphs: list[str]) -> list[str]:
    """Merge paragraphs under MIN_CHUNK_CHARS into the following paragraph,
    so short lines (like a lone heading or a one-line quote) don't become
    their own weak, context-poor chunk."""
    merged = []
    buffer = ""
    for p in paragraphs:
        buffer = f"{buffer}\n\n{p}".strip() if buffer else p
        if len(buffer) >= MIN_CHUNK_CHARS:
            merged.append(buffer)
            buffer = ""
    if buffer:
        # leftover short tail: attach to previous chunk rather than dropping it
        if merged:
            merged[-1] = f"{merged[-1]}\n\n{buffer}"
        else:
            merged.append(buffer)
    return merged


def chunk_document(doc: SourceDocument) -> list[Chunk]:
    paragraphs = split_into_paragraphs(doc.body)
    merged = merge_short_paragraphs(paragraphs)

    chunks = []
    for para in merged:
        chunks.append(
            Chunk(
                chunk_id=str(uuid.uuid4()),
                text=para,
                canonical_title=doc.canonical_title,
                primary_platform=doc.primary_platform,
                content_type=doc.content_type,
                published_date=doc.published_date,
                platform_urls=doc.platform_urls,
                series=doc.series,
                co_authors=doc.co_authors,
            )
        )
    return chunks
