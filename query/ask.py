"""
Query pipeline: retrieve top-k chunks from the vector store, ground a
generated answer in them, and report which sources it actually cited.

Generation is pluggable across three backends via --backend: Claude (hosted,
costs money), a local Ollama model (free, runs on your machine), and
Hugging Face's free Serverless Inference API (free, hosted, no billing risk
since there's no payment method attached to a free HF token). Retrieval,
prompt-building, and citation parsing are all backend-agnostic — only
generate_answer() and its three private helpers know which API they're
talking to.

The core logic is the ask() function, which takes a question and returns an
AskResult with no side effects (no printing) — this is what app/app.py
imports directly, so the Streamlit app and the CLI share the exact same
retrieve -> prompt -> generate -> parse pipeline. Everything below
`if __name__ == "__main__":` is a thin CLI wrapper around that same function.

Design note for the write-up: whether to filter out low-relevance chunks
before they hit the prompt, or always hand the model whatever top-k returns
and trust it to say "not enough information." This version does the latter.
On a ~30-40 document corpus there's no labeled relevance set to calibrate a
distance cutoff against, so a hardcoded threshold would be a guess dressed up
as a number. Telling the model explicitly to admit when the excerpts don't
cover the question is a more legible failure mode, and cheap to verify (see
the near-miss question in comparison_results.md) — including whether a
smaller local or free-tier model follows that instruction as reliably as
Claude does.

Run from within this directory:
    python3 ask.py "your question"                        # ollama, llama3.1
    python3 ask.py "your question" --backend claude
    python3 ask.py "your question" --backend huggingface
    python3 ask.py "your question" --backend ollama --model mistral

Setup for the ollama backend: brew install ollama && ollama pull llama3.1,
then `ollama serve` (may already be running after install).

Setup for the huggingface backend: a free token from huggingface.co/settings/tokens,
set as the HF_TOKEN environment variable (or st.secrets["HF_TOKEN"] in the
deployed Streamlit app — app.py bridges that into the HF_TOKEN env var so
this module never needs to know about Streamlit).
"""

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "ingest"))

import anthropic
from vector_store import get_collection

CLAUDE_MODEL = "claude-opus-5"
OLLAMA_MODEL = "llama3.1"
HF_MODEL = "Qwen/Qwen2.5-7B-Instruct"
DEFAULT_MODELS = {"claude": CLAUDE_MODEL, "ollama": OLLAMA_MODEL, "huggingface": HF_MODEL}

TOP_K = 5
DEFAULT_QUESTION = "What has Vanna written about how AI changes code review?"

CITED_RE = re.compile(r"CITED:\s*(.+)", re.IGNORECASE | re.DOTALL)


class GenerationError(Exception):
    """A generation failure with a message that's safe to show a user directly
    (rate limit, cold start, declined request) — as opposed to an unhandled
    exception, which is a bug and should surface with its real traceback.

    debug_detail carries the real underlying exception (type + message) so
    callers can surface it somewhere a human will actually see it — the
    Streamlit app puts it in a collapsed expander, since digging through a
    hosting provider's log viewer by hand is slow and error-prone."""

    def __init__(self, message: str, debug_detail: str | None = None):
        super().__init__(message)
        self.debug_detail = debug_detail


class RefusalError(GenerationError):
    pass


@dataclass
class AskResult:
    question: str
    backend: str
    model: str
    answer: str = ""
    sources: list[dict] = field(default_factory=list)
    error: str | None = None
    debug_detail: str | None = None


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
    if backend == "huggingface":
        return _generate_huggingface(prompt, model)
    raise ValueError(f"Unknown backend: {backend!r} (expected 'claude', 'ollama', or 'huggingface')")


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
        raise GenerationError(
            "The `ollama` package isn't installed. Run: pip install ollama",
            debug_detail=f"{type(e).__name__}: {e}",
        ) from e

    try:
        response = ollama.generate(model=model, prompt=prompt, stream=False)
    except Exception as e:
        raise GenerationError(
            f"Could not get a response from Ollama (model={model!r}). Make sure the "
            f"server is running (`ollama serve`) and the model is pulled (`ollama pull {model}`).",
            debug_detail=f"{type(e).__name__}: {e}",
        ) from e
    return response["response"]


def _generate_huggingface(prompt: str, model: str) -> str:
    try:
        from huggingface_hub import InferenceClient
    except ImportError as e:
        raise GenerationError(
            "The `huggingface_hub` package isn't installed. Run: pip install huggingface_hub",
            debug_detail=f"{type(e).__name__}: {e}",
        ) from e

    token = os.environ.get("HF_TOKEN")
    client = InferenceClient(model=model, token=token)
    try:
        response = client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
    except Exception as e:
        # The UI only ever shows a friendly message (rate limits and cold starts
        # are normal on the free tier), but attach the real cause as debug_detail
        # so it can be surfaced somewhere a human will actually see it — every
        # HF failure otherwise looks identical from the outside.
        raise GenerationError(
            "Hugging Face's free inference API is unavailable right now (this is usually "
            "a rate limit or a model cold start). Please try again in a moment.",
            debug_detail=f"{type(e).__name__}: {e}",
        ) from e
    return response.choices[0].message.content


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


def _dedupe_sources(excerpts: list[dict], cited_indices: list[int]) -> list[dict]:
    seen = set()
    sources = []
    for i in cited_indices:
        if 1 <= i <= len(excerpts):
            e = excerpts[i - 1]
            key = (e["title"], e["url"])
            if key not in seen:
                seen.add(key)
                sources.append({"title": e["title"], "url": e["url"]})
    return sources


def ask(question: str, backend: str = "huggingface", model: str | None = None, k: int = TOP_K) -> AskResult:
    """Retrieve, build the prompt, generate, and parse citations. Pure function,
    no printing — the CLI and the Streamlit app both call this directly."""
    resolved_model = model or DEFAULT_MODELS[backend]

    excerpts = retrieve(question, k)
    prompt = build_prompt(question, excerpts)

    try:
        full_text = generate_answer(prompt, backend, resolved_model)
    except GenerationError as e:
        return AskResult(
            question=question,
            backend=backend,
            model=resolved_model,
            error=str(e),
            debug_detail=e.debug_detail,
        )

    answer = full_text.partition("CITED:")[0].strip()
    cited_indices = parse_cited_indices(full_text)
    sources = _dedupe_sources(excerpts, cited_indices)

    return AskResult(
        question=question, backend=backend, model=resolved_model, answer=answer, sources=sources
    )


def _print_result(result: AskResult) -> None:
    print(f"Question: {result.question}")
    print(f"Backend: {result.backend} ({result.model})\n")

    if result.error:
        print(result.error)
        if result.debug_detail:
            print(f"Debug: {result.debug_detail}")
        return

    print(f"Answer:\n{result.answer}\n")
    print("Sources:")
    if result.sources:
        for s in result.sources:
            print(f"  - {s['title']} ({s['url']})")
    else:
        print("  (none cited)")


def parse_args():
    parser = argparse.ArgumentParser(description="Ask a question grounded in the essay archive.")
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    parser.add_argument("--backend", choices=["claude", "ollama", "huggingface"], default="ollama")
    parser.add_argument("--model", default=None, help="Override the model for the chosen backend")
    parser.add_argument("-k", type=int, default=TOP_K, help="Number of chunks to retrieve")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = ask(args.question, backend=args.backend, model=args.model, k=args.k)
    _print_result(result)
