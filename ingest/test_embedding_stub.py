"""
TESTING STUB ONLY. Not for real use.

This sandbox's network doesn't allow reaching huggingface.co, which is
where the real sentence-transformers model downloads from. This stub uses
TF-IDF instead, purely so we can prove the rest of the pipeline (chunking,
storage, metadata, retrieval) is wired correctly.

TF-IDF is a bag-of-words method — it matches on shared vocabulary, not
meaning. It will NOT give good semantic search results. Once you're running
this locally with normal internet access, delete this file and use
vector_store.py's real SentenceTransformerEmbeddingFunction instead.
"""

from chromadb import Documents, EmbeddingFunction, Embeddings
from sklearn.feature_extraction.text import TfidfVectorizer


class TfidfStubEmbeddingFunction(EmbeddingFunction):
    """Vectorizer must be fit once, up front, on the full known vocabulary
    (docs + likely queries), since Chroma calls this function separately
    for indexing and for querying. Passed a pre-fit vectorizer instead of
    fitting lazily, so index-time and query-time vectors stay comparable."""

    def __init__(self, vectorizer: TfidfVectorizer):
        self.vectorizer = vectorizer

    def __call__(self, input: Documents) -> Embeddings:
        vectors = self.vectorizer.transform(input).toarray()
        return vectors.tolist()
