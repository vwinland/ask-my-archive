"""
Query pipeline: retrieve top-k chunks from the vector store, ground a
generated answer in them, and report which sources it actually cited.

Generation is pluggable between Claude (hosted, costs money) and a local
Ollama model (free, runs on your machine) via --backend. Retrieval,
prompt-building, and citation parsing are all backend-agnostic — only
generate_answer() and its two private helpers know which API they're
talking to.

Design note for the write-up: whether to filter out low-relevance chunks
before they hit the prompt, or always hand the model whatever top-k returns
and trust it to say "not enough information." This version does the latter.
On a ~30-40 document corpus there's no labeled relevance set to calibrate a
distance cutoff against, so a hardcoded threshold would be a guess dressed up
as a number. Telling the model explicitly to admit when the excerpts don't
cover the question is a more legible failure mode, and cheap to verify (see
the near-miss question in the test list below) — including whether a smaller
local model follows that instruction as reliably as Claude does.

Run from within this directory:
    python3 ask.py "your question"                      # ollama, llama3.1
    python3 ask.py "your question" --backend claude
    python3 ask.py "your question" --backend ollama --model mistral

Setup for the ollama backend: brew install ollama && ollama pull llama3.1,
then `ollama serve` (may already be running after install).
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "ingest"))

import anthropic
from vector_store import get_collection

CLAUDE_MODEL = "claude-opus-5"
OLLAMA_MODEL = "llama3.1"
TOP_K = 5
DEFAULT_QUESTION = "What has Vanna written about how AI changes code review?"

CITED_RE = re.compile(r"CITED:\s*(.+)", re.IGNORECASE | re.DOTALL)


class RefusalError(Exception):
    pass


def retrieve(question: str, k: int = TOP_K) -> list[dict]:
    collection = get_collection()
    results = collection.query(query_texts=[question], n_results=k)

    excerpts = []
    for text, meta, distance in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        url = meta["url_blog"] or meta["url_hackernoon"] or meta["url_medium"] or meta["url_ibm_think"]
        excerpts.append(
            {
                "title": meta["canonical_title"],
                "url": url,
                "text": text,
                "distance": distance,
            }
        )
    return excerpts


def build_prompt(question: str, excerpts: list[dict]) -> str:
    excerpt_blocks = "\n\n".join(
        f'[{i + 1}] From "{e["title"]}" ({e["url"]}):\n{e["text"]}'
        for i, e in enumerate(excerpts)
    )
    return f"""You are answering questions about Vanna Winland's published writing, using only the excerpts below. If the excerpts don't contain enough information to answer, say so directly instead of guessing.

Excerpts:
{excerpt_blocks}

Question: {question}

Answer using only the excerpts above. Cite which essay(s) each part of your answer comes from.

After your answer, on a new line by itself, write "CITED:" followed by a comma-separated list of the excerpt numbers you actually drew from to answer (e.g. "CITED: 1, 3"). If you could not answer from the excerpts, write "CITED: none".
"""


def generate_answer(prompt: str, backend: str, model: str) -> str:
    if backend == "claude":
        return _generate_claude(prompt, model)
    if backend == "ollama":
        return _generate_ollama(prompt, model)
    raise ValueError(f"Unknown backend: {backend!r} (expected 'claude' or 'ollama')")


def _generate_claude(prompt: str, model: str) -> str:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        raise RefusalError("Claude declined to answer this request.")
    return "".join(block.text for block in response.content if block.type == "text")


def _generate_ollama(prompt: str, model: str) -> str:
    try:
        import ollama
    except ImportError as e:
        raise RuntimeError("The `ollama` package isn't installed. Run: pip install ollama") from e

    try:
        response = ollama.generate(model=model, prompt=prompt, stream=False)
    except Exception as e:
        raise RuntimeError(
            f"Could not get a response from Ollama (model={model!r}). Make sure the "
            f"server is running (`ollama serve`) and the model is pulled (`ollama pull {model}`)."
        ) from e
    return response["response"]


def parse_cited_indices(full_text: str) -> list[int]:
    match = CITED_RE.search(full_text)
    if not match:
        return []
    raw = match.group(1).strip().splitlines()[0]
    if raw.lower().startswith("none"):
        return []
    indices = []
    for piece in raw.split(","):
        piece = piece.strip().rstrip(".")
        if piece.isdigit():
            indices.append(int(piece))
    return indices


def ask(question: str, backend: str = "ollama", model: str | None = None, k: int = TOP_K) -> None:
    resolved_model = model or (CLAUDE_MODEL if backend == "claude" else OLLAMA_MODEL)

    excerpts = retrieve(question, k)
    prompt = build_prompt(question, excerpts)

    print(f"Question: {question}")
    print(f"Backend: {backend} ({resolved_model})\n")

    try:
        full_text = generate_answer(prompt, backend, resolved_model)
    except RefusalError as e:
        print(str(e))
        return

    answer = full_text.partition("CITED:")[0].strip()
    cited_indices = parse_cited_indices(full_text)

    print(f"Answer:\n{answer}\n")

    seen = set()
    sources = []
    for i in cited_indices:
        if 1 <= i <= len(excerpts):
            e = excerpts[i - 1]
            key = (e["title"], e["url"])
            if key not in seen:
                seen.add(key)
                sources.append(e)

    print("Sources:")
    if sources:
        for e in sources:
            print(f"  - {e['title']} ({e['url']})")
    else:
        print("  (none cited)")


def parse_args():
    parser = argparse.ArgumentParser(description="Ask a question grounded in the essay archive.")
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    parser.add_argument("--backend", choices=["claude", "ollama"], default="ollama")
    parser.add_argument("--model", default=None, help="Override the model for the chosen backend")
    parser.add_argument("-k", type=int, default=TOP_K, help="Number of chunks to retrieve")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    ask(args.question, backend=args.backend, model=args.model, k=args.k)
