"""
Upgrades the 12 IBM Think tutorial documents' body text with the cleaner
source markdown/notebook from the IBM/ibmdotcom-tutorials GitHub repo, in
place of the scraped-webpage body load_ibm_think.py used by default.

Must run AFTER load_ibm_think.py: it works by finding each tutorial's
existing chunks in the collection (by canonical_title) to recover their
metadata, deleting them, and re-adding freshly chunked versions with the
repo body swapped in -- title/URL/date/co_authors/content_type are
untouched. Tutorials with no repo match keep load_ibm_think.py's
live-page-scraped body as-is, per spec, so this script just leaves those
chunks alone.

Repo paths below were found via vwinland's portfolio (Tutorials.jsx links
each tutorial to its source in her own fork of this repo) and then
verified directly against the upstream IBM/ibmdotcom-tutorials repo -- all
12 paths exist there unchanged, so no fuzzy title-matching was needed to
locate them. A defensive fallback (by filename-to-directory-name
similarity) is still used for the few tutorials whose path is a directory
rather than a single file, since those directories hold more than one .md
file (the actual write-up plus example/output files) and only one is the
real tutorial.

Run from within this directory, after load_ibm_think.py:
    python3 load_ibm_tutorials.py
"""

import difflib
import json
import re
import subprocess
from pathlib import Path

from chunk import chunk_document
from schema import SourceDocument
from vector_store import add_chunks, get_collection

TUTORIALS_REPO_URL = "https://github.com/IBM/ibmdotcom-tutorials.git"
TUTORIALS_REPO_DIR = Path("_sources/ibmdotcom-tutorials")

# title -> path within the repo, verified to exist upstream (see module
# docstring). Directory paths (no file extension) hold more than one file;
# _resolve_source_file() below picks the real tutorial out of the
# directory rather than an example/output file.
TUTORIAL_REPO_PATHS = {
    "Use role prompting with IBM watsonx and Granite":
        "tutorials/04-prompt-engineering/role-prompting-tutorial.ipynb",
    "Perform zero-shot classification with a foundation model":
        "tutorials/04-prompt-engineering/zero-shot-classification.ipynb",
    "Multiagent collaboration for customer call analysis (CrewAI + watsonx.ai)":
        "tutorials/03-multi-agent-systems/multiagent-collaboration-customer-call-analysis.md",
    "Use ChatDev ChatChain for agent communication on IBM watsonx.ai":
        "tutorials/03-multi-agent-systems/chatdev_watsonx_tutorial_",
    "Multi-agent PRD automation with MetaGPT, Ollama and DeepSeek":
        "tutorials/03-multi-agent-systems/metagpt_tutorial",
    "Using ACP for AI agent interoperability: Building multi-agent workflows":
        "tutorials/03-multi-agent-systems/acp_tutorial",
    "Use the A2A protocol for AI agent communication":
        "tutorials/03-multi-agent-systems/a2a_tutorial",
    "AgentOps: Monitor and govern AI agents with IBM Telemetry by using watsonx Orchestrate":
        "tutorials/12-observability-and-monitoring/wxo_agentops",
    "Abstractive text summarization tutorial":
        "tutorials/09-text-processing-and-nlp/abstractive-text-summarization.ipynb",
    "How to summarize text with Python NLP and extractive text summarization":
        "tutorials/09-text-processing-and-nlp/python_text_summarization.ipynb",
    "AI documentation with IBM Bob":
        "tutorials/16-ibm-bob/ai-docs-ibm-bob",
    "Build an AI agent for text classification with Python and watsonx Orchestrate":
        "tutorials/02-agents-and-orchestration/wxo-text-classification",
}


def sync_tutorials_repo():
    if TUTORIALS_REPO_DIR.exists():
        subprocess.run(["git", "-C", str(TUTORIALS_REPO_DIR), "pull", "--ff-only"], check=True)
    else:
        TUTORIALS_REPO_DIR.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", TUTORIALS_REPO_URL, str(TUTORIALS_REPO_DIR)],
            check=True,
        )


def _resolve_source_file(rel_path: str) -> Path | None:
    full = TUTORIALS_REPO_DIR / rel_path
    if full.is_file():
        return full
    if not full.is_dir():
        return None

    candidates = [p for p in full.iterdir() if p.is_file() and p.suffix in (".md", ".ipynb")]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    dir_key = re.sub(r"[^a-z0-9]", "", full.name.lower())

    def score(p: Path) -> float:
        file_key = re.sub(r"[^a-z0-9]", "", p.stem.lower())
        return difflib.SequenceMatcher(None, dir_key, file_key).ratio()

    return max(candidates, key=score)


def _parse_notebook(path: Path) -> str:
    """Markdown and code cells only -- outputs are run logs, not content,
    and would pollute retrieval with noise (progress bars, stack traces,
    truncated dataframe reprs, etc.)."""
    notebook = json.loads(path.read_text())
    parts = []
    for cell in notebook.get("cells", []):
        source = "".join(cell.get("source", []))
        if not source.strip():
            continue
        if cell.get("cell_type") == "markdown":
            parts.append(source.strip())
        elif cell.get("cell_type") == "code":
            parts.append(f"```python\n{source.strip()}\n```")
    return "\n\n".join(parts)


def find_tutorial_body(title: str) -> str | None:
    rel_path = TUTORIAL_REPO_PATHS.get(title)
    if rel_path is None:
        return None
    source_file = _resolve_source_file(rel_path)
    if source_file is None:
        return None
    if source_file.suffix == ".ipynb":
        return _parse_notebook(source_file)
    return source_file.read_text()


def _existing_doc_metadata(collection, title: str) -> dict | None:
    """Recover a tutorial's metadata from its already-indexed chunks
    (added by load_ibm_think.py), so this script doesn't need to re-fetch
    the live IBM Think page just to rebuild the same SourceDocument shell
    with a different body."""
    results = collection.get(where={"canonical_title": title}, limit=1)
    if not results["ids"]:
        return None
    meta = results["metadatas"][0]
    co_authors = [n.strip() for n in meta["co_authors"].split(",") if n.strip()]
    return {
        "content_type": meta["content_type"],
        "published_date": meta["published_date"],
        "platform_urls": {"ibm_think": meta["url_ibm_think"]},
        "co_authors": co_authors,
    }


def main():
    sync_tutorials_repo()
    collection = get_collection()

    matched, skipped = 0, 0
    for title in TUTORIAL_REPO_PATHS:
        body = find_tutorial_body(title)
        if body is None:
            print(f"No repo source found for '{title}', leaving live-page body in place.")
            skipped += 1
            continue

        meta = _existing_doc_metadata(collection, title)
        if meta is None:
            print(f"'{title}' not found in the collection yet -- run load_ibm_think.py first. Skipping.")
            skipped += 1
            continue

        collection.delete(where={"canonical_title": title})
        doc = SourceDocument(
            canonical_title=title,
            primary_platform="ibm_think",
            content_type=meta["content_type"],
            published_date=meta["published_date"],
            body=body,
            platform_urls=meta["platform_urls"],
            co_authors=meta["co_authors"],
        )
        chunks = chunk_document(doc)
        add_chunks(chunks)
        print(f"Replaced '{title}' with repo-sourced body: {len(chunks)} chunks")
        matched += 1

    print(f"\nDone. {matched} tutorials upgraded to repo source, {skipped} left as-is or skipped.")


if __name__ == "__main__":
    main()
