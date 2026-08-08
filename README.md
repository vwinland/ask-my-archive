# Ask My Archive

A RAG tool over Vanna Winland's published writing (personal blog, HackerNoon,
Medium, IBM Think explainers/tutorials).

## Status

Architecture validated end to end in a sandboxed dev environment (chunking,
metadata schema, Chroma storage, retrieval all confirmed working — see
`ingest/smoke_test.py`). Not yet run with the real embedding model, since
that sandbox couldn't reach huggingface.co. This will work normally with
regular internet access.

## Structure

- `ingest/schema.py` — metadata schema (syndication, content type, series, co-authors)
- `ingest/chunk.py` — paragraph-based chunker
- `ingest/vector_store.py` — Chroma + sentence-transformers (the real embedding setup — use this)
- `ingest/ingest_sample.py` — example ingestion script on 2 sample essays
- `sample_data/` — 2 sample essays for testing
- `ingest/test_embedding_stub.py`, `ingest/smoke_test.py` — sandbox-only test stubs, not for real use, safe to delete

## First run, locally

```
pip install -r requirements.txt
cd ingest
python3 ingest_sample.py
```

This downloads the `all-MiniLM-L6-v2` embedding model the first time (small,
one-time download) and indexes the 2 sample essays into `store/chroma_db`.

## Next steps

1. Confirm `ingest_sample.py` runs cleanly with the real embedding model
2. Write loaders for each real source: blog markdown, HackerNoon/Medium
   (matched via the syndication table already built), IBM Think explainers,
   and the ibmdotcom-tutorials repo (markdown + notebook cells)
3. Build the query pipeline: retrieve top-k chunks -> pass to Claude with a
   prompt that only answers from retrieved chunks and cites the source
4. Build a minimal chat UI
