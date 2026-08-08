"""
MVP ingestion script — proves the pipeline works end to end on two sample
essays before we point it at the full real corpus.
"""

from chunk import chunk_document
from schema import SourceDocument
from vector_store import add_chunks

SAMPLE_DOCS = [
    SourceDocument(
        canonical_title="Agentic Coordination Isn't New. It's 25 Years Old",
        primary_platform="blog",
        content_type="essay",
        published_date="2026-07-01",
        body=open("../sample_data/agentic-coordination.md").read(),
        syndicated_titles={"hackernoon": "Agentic Coordination Isn't New - It's 25 Years Old"},
        platform_urls={
            "blog": "https://vwinland.github.io/blog/agentic-coordination-isnt-new-its-25-years-old",
            "hackernoon": "https://hackernoon.com/agentic-coordination-isnt-new-its-25-years-old",
        },
        series="Actually Agentic",
        series_part=2,
    ),
    SourceDocument(
        canonical_title="Code Review Cannot Scale to the AI Era",
        primary_platform="blog",
        content_type="essay",
        published_date="2026-05-10",
        body=open("../sample_data/code-review-scale.md").read(),
        syndicated_titles={"hackernoon": "Here's Why Code Review Is Having Trouble Scaling to the AI Era"},
        platform_urls={
            "blog": "https://vwinland.github.io/blog/code-review-cannot-scale-to-the-ai-era",
            "hackernoon": "https://hackernoon.com/heres-why-code-review-is-having-trouble-scaling-to-the-ai-era",
        },
        series="Industrialization of Software Engineering",
    ),
]


def main():
    total_chunks = 0
    for doc in SAMPLE_DOCS:
        chunks = chunk_document(doc)
        add_chunks(chunks)
        total_chunks += len(chunks)
        print(f"Indexed '{doc.canonical_title}': {len(chunks)} chunks")

    print(f"\nDone. {total_chunks} total chunks indexed across {len(SAMPLE_DOCS)} documents.")


if __name__ == "__main__":
    main()
