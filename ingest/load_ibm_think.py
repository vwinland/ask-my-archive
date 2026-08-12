"""
Real loader for IBM Think articles and tutorials (14 + 12 pieces listed on
vwinland's portfolio, plus one piece that isn't listed there at all -- see
EXTRA_PIECES).

The article/tutorial inventory itself is never hardcoded: it's parsed at
runtime from the portfolio repo's own Articles.jsx/Tutorials.jsx source --
the same data vwinland.github.io/articles and /tutorials render from React
state -- so this loader always reflects whatever's currently listed there.
Those pages are client-rendered SPAs with no server HTML to scrape, and the
portfolio repo is already this pipeline's source of truth for the blog
corpus (see load_blog.py); reading its own page-source arrays is more
robust than driving a headless browser just to read back what that same
source already states directly.

Per-document metadata (published date, content-type category, and any
co-author byline) and body text are NOT taken from the portfolio -- they
come from each piece's live IBM Think page, since that's the canonical,
current source for all of it (see fetch_ibm_think_page()). This matters in
practice: IBM's own content-type taxonomy doesn't always agree with which
portfolio page a piece is filed under. "What is LLM reinforcement
learning?" is listed on the Articles page, but its live page is tagged
`Content Type / Tutorial`. The portfolio-page default below is only a
fallback for the handful of pages missing that taxonomy field entirely.

Co-authorship turned out to be far more common than expected -- about a
third of these pieces credit a second (or third) name in the page's
`<meta name="author">` tag, not just the two pieces called out when this
loader was scoped. All of them are captured here since the rule ("check
the byline, populate co_authors if a second name appears") is applied to
every page, not just the two originally flagged.

This loader is additive: unlike load_blog.py, it does not reset the
collection, since it's meant to run after load_blog.py has already
populated the blog corpus. Tutorial pieces get a live-page-scraped body by
default here; load_ibm_tutorials.py runs after this script and upgrades
the 12 tutorial documents' bodies to the cleaner GitHub-repo source where a
match exists, keeping this script's title/URL/metadata untouched.

Run from within this directory, after load_blog.py:
    python3 load_ibm_think.py
"""

import re

import requests
from bs4 import BeautifulSoup

from chunk import chunk_document
from load_blog import BLOG_REPO_DIR, sync_blog_repo
from schema import SourceDocument
from vector_store import add_chunks

PORTFOLIO_ARTICLES_JSX = BLOG_REPO_DIR / "src" / "pages" / "Articles.jsx"
PORTFOLIO_TUTORIALS_JSX = BLOG_REPO_DIR / "src" / "pages" / "Tutorials.jsx"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Not listed on the portfolio site at all -- found via the IBM Think author
# page (ibm.com/think/author/vanna-winland) instead. Title/URL had to be
# looked up by hand since there's no portfolio entry to parse; everything
# else about it (date, category, co-authors, body) still comes from its
# live page like every other piece.
EXTRA_PIECES = [
    {
        "title": "Modernizing Kafka Data Streaming with Confluent",
        "url": "https://www.ibm.com/think/tutorials/modernizing-kafka-data-streaming-confluent",
    },
]

# IBM's own on-page taxonomy is the default source of truth for
# content_type (see fetch_ibm_think_page()), but it's occasionally wrong.
# "What is LLM reinforcement learning?" is tagged Content Type / Tutorial
# on ibm.com, confirmed incorrect -- it's an explainer, matching how it's
# actually filed on the portfolio's Articles page.
CONTENT_TYPE_OVERRIDES = {
    "What is LLM reinforcement learning?": "explainer",
}

CONTENT_TYPE_MAP = {
    "explainer": "explainer",
    "tutorial": "tutorial",
    "insights": "insight",
    "insight": "insight",
}

JS_OBJECT_RE = re.compile(r"\{(.*?)\n    \},?", re.DOTALL)
BODY_BLOCK_TAGS = ("p", "li", "h2", "h3", "h4", "blockquote")


def _parse_js_array(js_source: str, array_var: str) -> list[dict]:
    """Extract {title, url} pairs from a `const <array_var> = [ {...}, ... ]`
    literal without a JS parser -- both files' objects are one field per
    line with double-quoted string values, so per-object regex is reliable
    here and avoids adding a JS-parsing dependency for two files whose
    shape we already control (they're in our own portfolio repo)."""
    match = re.search(rf"const {array_var} = \[(.*?)\n\];", js_source, re.DOTALL)
    if not match:
        raise ValueError(f"couldn't find `const {array_var} = [...]` in the source")

    entries = []
    for obj in JS_OBJECT_RE.findall(match.group(1)):
        title_m = re.search(r'title:\s*"((?:[^"\\]|\\.)*)"', obj)
        url_m = re.search(r'url:\s*"((?:[^"\\]|\\.)*)"', obj)
        if not title_m or not url_m:
            continue
        entries.append({"title": title_m.group(1), "url": url_m.group(1)})
    return entries


def load_inventory() -> list[dict]:
    """The full 27-piece inventory: title, url, and which portfolio page it
    came from (used only as a content_type fallback for the handful of
    pages missing IBM's own taxonomy label)."""
    articles = _parse_js_array(PORTFOLIO_ARTICLES_JSX.read_text(), "articles")
    tutorials = _parse_js_array(PORTFOLIO_TUTORIALS_JSX.read_text(), "tutorials")

    inventory = []
    for a in articles:
        inventory.append({**a, "default_content_type": "explainer"})
    for t in tutorials:
        inventory.append({**t, "default_content_type": "tutorial"})
    for e in EXTRA_PIECES:
        inventory.append({**e, "default_content_type": "tutorial"})
    return inventory


def _extract_body(soup: BeautifulSoup) -> str:
    """IBM Think renders article prose inside one or more div.cms-richtext
    blocks -- confirmed across explainer, tutorial, and insight page
    templates. Everything else on the page (global nav, newsletter signup,
    related-content rails) lives outside them."""
    paragraphs = []
    for block in soup.select("div.cms-richtext"):
        if block.find("form") or block.find("input"):
            continue
        for el in block.find_all(BODY_BLOCK_TAGS):
            if el.find_parent(BODY_BLOCK_TAGS):
                continue  # already covered by an ancestor block tag
            text = " ".join(el.get_text(" ", strip=True).split())
            if text:
                paragraphs.append(("- " if el.name == "li" else "") + text)
    return "\n\n".join(paragraphs)


def fetch_ibm_think_page(url: str) -> dict:
    """Fetch one live IBM Think page and pull everything needed from it:
    published date, content-type taxonomy label, co-author byline, and
    body text. All four are read fresh per page rather than assumed."""
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    date_tag = soup.find("meta", attrs={"name": "dcterms.date"})
    published_date = date_tag["content"][:10] if date_tag and date_tag.get("content") else ""

    type_tag = soup.find("meta", attrs={"name": "ibm.search.facet.field_hierarchy_04"})
    content_type = None
    if type_tag and type_tag.get("content"):
        label = type_tag["content"].rsplit("/", 1)[-1].strip().lower()
        content_type = CONTENT_TYPE_MAP.get(label)

    author_tag = soup.find("meta", attrs={"name": "author"})
    co_authors = []
    if author_tag and author_tag.get("content"):
        names = [" ".join(n.split()) for n in author_tag["content"].split(",")]
        co_authors = [n for n in names if n and n.lower() != "vanna winland"]

    return {
        "published_date": published_date,
        "content_type": content_type,
        "co_authors": co_authors,
        "body": _extract_body(soup),
    }


def load_ibm_think_documents() -> list[SourceDocument]:
    docs = []
    for entry in load_inventory():
        page = fetch_ibm_think_page(entry["url"])
        docs.append(
            SourceDocument(
                canonical_title=entry["title"],
                primary_platform="ibm_think",
                content_type=CONTENT_TYPE_OVERRIDES.get(
                    entry["title"], page["content_type"] or entry["default_content_type"]
                ),
                published_date=page["published_date"],
                body=page["body"],
                platform_urls={"ibm_think": entry["url"]},
                co_authors=page["co_authors"],
            )
        )
    return docs


def main():
    sync_blog_repo()  # portfolio repo -- shared clone with load_blog.py
    docs = load_ibm_think_documents()

    total_chunks = 0
    for doc in docs:
        chunks = chunk_document(doc)
        add_chunks(chunks)
        total_chunks += len(chunks)
        co = f" (with {', '.join(doc.co_authors)})" if doc.co_authors else ""
        print(f"Indexed '{doc.canonical_title}' ({doc.content_type}){co}: {len(chunks)} chunks")

    print(f"\nDone. {total_chunks} total chunks indexed across {len(docs)} documents.")


if __name__ == "__main__":
    main()
