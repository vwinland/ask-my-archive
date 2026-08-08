"""
SANDBOX SMOKE TEST ONLY.

Validates: SourceDocument -> chunk_document -> Chroma storage with
flattened metadata -> query -> results carry the right metadata back.

Uses the TF-IDF stub (see test_embedding_stub.py) because this sandbox
can't reach huggingface.co to download the real embedding model. Retrieval
quality here is NOT representative of the real system — this only proves
the wiring, not the search quality.
"""

import shutil

import chromadb
from chunk import chunk_document
from schema import SourceDocument
from sklearn.feature_extraction.text import TfidfVectorizer
from test_embedding_stub import TfidfStubEmbeddingFunction

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

TEST_QUERY = "What has Vanna written about how AI changes code review?"


def main():
    # fresh DB each run for a clean smoke test
    shutil.rmtree("../store/chroma_db_smoketest", ignore_errors=True)

    all_chunks = []
    for doc in SAMPLE_DOCS:
        chunks = chunk_document(doc)
        all_chunks.extend(chunks)
        print(f"Chunked '{doc.canonical_title}': {len(chunks)} chunks")

    # fit TF-IDF on doc chunks + the test query, so the query is in-vocabulary
    corpus_texts = [c.text for c in all_chunks] + [TEST_QUERY]
    vectorizer = TfidfVectorizer(max_features=256)
    vectorizer.fit(corpus_texts)
    embed_fn = TfidfStubEmbeddingFunction(vectorizer)

    client = chromadb.PersistentClient(path="../store/chroma_db_smoketest")
    collection = client.get_or_create_collection(name="smoketest", embedding_function=embed_fn)

    collection.add(
        ids=[c.chunk_id for c in all_chunks],
        documents=[c.text for c in all_chunks],
        metadatas=[c.to_metadata_dict() for c in all_chunks],
    )
    print(f"\nIndexed {len(all_chunks)} chunks into Chroma.")

    print(f"\nQuery: {TEST_QUERY!r}")
    results = collection.query(query_texts=[TEST_QUERY], n_results=2)

    print("\nTop results:")
    for i, (doc_text, meta, dist) in enumerate(
        zip(results["documents"][0], results["metadatas"][0], results["distances"][0])
    ):
        print(f"\n[{i+1}] distance={dist:.4f}")
        print(f"    title: {meta['canonical_title']}")
        print(f"    platform: {meta['primary_platform']}  series: {meta['series'] or '(none)'}")
        print(f"    blog url: {meta['url_blog']}")
        print(f"    text: {doc_text[:120]}...")

    print("\nSmoke test passed: chunking, metadata, storage, and retrieval are wired correctly.")


if __name__ == "__main__":
    main()
