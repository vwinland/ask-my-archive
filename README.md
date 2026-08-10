# Ask My Archive

A retrieval-augmented Q&A tool over my own published writing. Ask it a question, it retrieves the relevant excerpts from my blog, HackerNoon, and IBM Think, and answers grounded in what I actually wrote, with citations back to the source.

I built this to get hands-on with the parts of AI application development I'd only written about before: chunking, embeddings, retrieval, and grounded generation.

Full write-up: [I built a RAG tool over my own writing. Here's what I learned.](https://vwinland.github.io/blog/build-log-ask-my-archive/)

Live app: [Ask My Archive on Streamlit](https://ask-my-archive-gkuq5o8tdvnc7cs3wwpcth.streamlit.app/)

## What's actually built

- **Metadata schema** handling syndication across four platforms (blog, HackerNoon, Medium, IBM Think), so the same essay published under different titles on different sites resolves to one canonical entry instead of duplicate, conflicting chunks
- **Paragraph-based chunking** with short-paragraph merging
- **Local embeddings** (`all-MiniLM-L6-v2`), chosen deliberately over a hosted embedding API since the corpus is too small to need one
- **Chroma vector store**, local and persistent
- **Swappable generation backend** — Claude API, a local Ollama model, or Hugging Face's free Serverless Inference API, same retrieval and citation-parsing logic underneath. The deployed app runs on Hugging Face (free, no billing risk); Claude and Ollama stay available as CLI flags for local testing and comparison
- **Streamlit chat interface**, deployed publicly, backed by the same `ask()` pipeline the CLI uses
- **HackerNoon-inspired pixel styling** — dark theme, blocky borders, icons from HackerNoon's Pixel Icon Library (CC BY 4.0, credited in-app footer)
- **Citation-grounded prompting**, tested against the failure mode that actually matters for a tool like this: does it correctly say "I don't know" instead of guessing, when the corpus doesn't cover the question

16 blog posts fully indexed and tested end to end (392 chunks). 27 IBM Think pieces and a tutorials repo identified and mapped, not yet ingested.

## What I'd add for production

This is the retrieval and generation core, built and tested. It is not a production system, and I want to be specific about the gap rather than either overclaiming or underselling it:

- **An evaluation harness.** I validated retrieval against three manual test questions. Production needs a labeled set of questions with known-correct sources, run automatically on every pipeline change.
- **Monitoring.** I read the outputs by hand. Production needs logging on every query, with flags on declines and high-distance retrievals, reviewed regularly to catch corpus gaps or drift.
- **Access control.** My corpus is all public writing, so this hasn't mattered yet. A business RAG system usually needs retrieval to respect who's asking, not just what's semantically closest.
- **Continuous ingestion.** I ran indexing once, by hand. Production needs a pipeline that detects new or updated source documents automatically.
- **Cost tracking at volume.** Three test questions cost nine cents. That's invisible at this scale and a real line item at production query volume.

## Stack

Python, Chroma, sentence-transformers, Streamlit, Anthropic API, Ollama, Hugging Face Inference API.

## Status

Actively being extended. Chat interface is built and deployed (Streamlit, Hugging Face backend). Next: ingest IBM Think and the tutorials repo.