"""
Local vector store, backed by Chroma with a local sentence-transformers
embedding model.

Why local embeddings instead of a hosted API (OpenAI/Voyage):
this corpus is roughly 30-40 documents. A hosted embedding API is built for
scale we don't need here, adds an API key dependency, and costs money for
zero real benefit at this size. `all-MiniLM-L6-v2` is small, fast, free,
and runs offline. Worth writing about: matching infra to actual scale
instead of defaulting to "the cloud API everyone uses."
"""

from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from schema import Chunk

# Anchored to this file's location, not the caller's working directory. A
# bare relative path here resolves against os.getcwd(), and callers don't
# share one cwd convention: ingest scripts and query/ask.py are run from
# their own directory ("cd ingest && python3 ...", per each script's own
# docstring), but Streamlit Cloud runs `streamlit run app/app.py` from the
# repo root. A relative "../store/chroma_db" resolves correctly for the
# former and lands outside the repo entirely for the latter — Chroma then
# silently creates a fresh, empty collection there instead of erroring.
DB_PATH = str(Path(__file__).resolve().parent.parent / "store" / "chroma_db")
COLLECTION_NAME = "essay_archive"


def get_collection():
    client = chromadb.PersistentClient(path=DB_PATH)
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
    )
    return collection


def add_chunks(chunks: list[Chunk]):
    collection = get_collection()
    collection.add(
        ids=[c.chunk_id for c in chunks],
        documents=[c.text for c in chunks],
        metadatas=[c.to_metadata_dict() for c in chunks],
    )
    return len(chunks)


def query(question: str, k: int = 5):
    collection = get_collection()
    results = collection.query(query_texts=[question], n_results=k)
    return results
