"""
Real loader for the blog corpus (public/blog/*.md in vwinland/vanna-portfolio).

Clones/updates the blog source repo, parses each post's frontmatter + body,
builds a SourceDocument per post, and runs it through the existing
chunk -> embed -> store pipeline (chunk.py, vector_store.py).

Blog frontmatter is the canonical source for title/date/tags/series - it
doesn't know about syndication, so syndicated titles/URLs for platforms
like HackerNoon are tracked separately below (see SYNDICATION), the same
way ingest_sample.py already did for the two sample essays.
"""

import re
import subprocess
from pathlib import Path

import yaml
from chunk import chunk_document
from schema import SourceDocument
from vector_store import DB_PATH, COLLECTION_NAME, add_chunks

BLOG_REPO_URL = "https://github.com/vwinland/vanna-portfolio.git"
BLOG_REPO_DIR = Path("_sources/vanna-portfolio")
BLOG_POSTS_DIR = BLOG_REPO_DIR / "public" / "blog"
BLOG_BASE_URL = "https://vwinland.github.io/blog"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)

# Personal essays vs. technical/cultural essays - everything else on the
# blog defaults to content_type "essay".
PERSONAL_ESSAY_SLUGS = {"arrivals", "the-thoughts-that-count"}

# Unpublished drafts that must never be ingested, even if they show up in
# a future clone of the repo.
EXCLUDED_SLUGS = {"who-keeps-the-hour", "software-eats-the-front-desk"}
EXCLUDED_TITLES = {"who keeps the hour", "software eats the front desk"}

# Known syndication: blog is canonical, these platforms republished the
# piece under their own title/URL. HackerNoon titles are verified against
# Vanna's HackerNoon stats export (vanna-w-stories-stats.csv); URLs are
# pulled directly from the live HackerNoon author page DOM rather than
# assumed from a slugified title, since HackerNoon slugs don't always
# match a clean title-slugify. Medium URLs are given directly in the
# export (both Medium pieces keep their original blog title, so no title
# override is needed for that platform).
SYNDICATION = {
    "agentic-coordination-isnt-new-its-25-years-old": {
        "hackernoon": {
            "title": "Agentic Coordination Isn't New - It's 25 Years Old",
            "url": "https://hackernoon.com/agentic-coordination-isnt-new-its-25-years-old",
        }
    },
    "if-ai-is-coming-for-your-job-why-cant-anyone-tell-you-how-to-use-it": {
        "hackernoon": {
            "title": "AI Is Coming For Your Job, Yet No One Can Tell You How to Use It",
            "url": "https://hackernoon.com/ai-is-coming-for-your-job-yet-no-one-can-tell-you-how-to-use-it",
        }
    },
    "you-dont-need-to-buy-uncensored-ai-on-a-flash-drive": {
        "hackernoon": {
            "title": "Don't Buy an Uncensored AI on a Flash Drive: What You Can Do Instead",
            "url": "https://hackernoon.com/dont-buy-an-uncensored-ai-on-a-flash-drive-what-you-can-do-instead",
        }
    },
    "what-is-an-agent-actually": {
        "hackernoon": {
            "title": "What Is an Agent, Actually?",
            "url": "https://hackernoon.com/what-is-an-agent-actually",
        }
    },
    "code-review-cannot-scale-to-the-ai-era": {
        "hackernoon": {
            "title": "Here's Why Code Review Is Having Trouble Scaling to the AI Era",
            "url": "https://hackernoon.com/heres-why-code-review-is-having-trouble-scaling-to-the-ai-era",
        }
    },
    "vibe-coding-has-a-governance-problem": {
        "hackernoon": {
            "title": "The Governance Gap in AI-Generated Software",
            "url": "https://hackernoon.com/the-governance-gap-in-ai-generated-software",
        }
    },
    "romanticism-has-a-new-villain": {
        "hackernoon": {
            "title": "A24's AI Backlash Is an Old Creative Argument in New Clothes",
            "url": "https://hackernoon.com/a24s-ai-backlash-is-an-old-creative-argument-in-new-clothes",
        }
    },
    "legacy-migration-may-become-ais-largest-empire": {
        "hackernoon": {
            "title": "Legacy Migration May Become AI's Largest Enterprise Market",
            "url": "https://hackernoon.com/legacy-migration-may-become-ais-largest-enterprise-market",
        }
    },
    "platform-engineering-is-the-new-factory-floor": {
        "hackernoon": {
            "title": "Golden Paths, IDPs, and the Governance Layer of AI Development",
            "url": "https://hackernoon.com/golden-paths-idps-and-the-governance-layer-of-ai-development",
        }
    },
    "the-thoughts-that-count": {
        "hackernoon": {
            "title": "The Quiet Power of Paying Attention",
            "url": "https://hackernoon.com/the-quiet-power-of-paying-attention",
        },
        "medium": {
            "url": "https://vwinland.medium.com/the-thoughts-that-count-8ed919a30ddd",
        },
    },
    "the-developer-workstation-is-becoming-an-autonomous-system": {
        "hackernoon": {
            "title": "The IDE Is No Longer Just a Place to Write Code",
            "url": "https://hackernoon.com/the-ide-is-no-longer-just-a-place-to-write-code",
        }
    },
    "ai-wrote-your-docs": {
        "hackernoon": {
            "title": "The Problem With Autogenerated Docs",
            "url": "https://hackernoon.com/the-problem-with-autogenerated-docs",
        }
    },
    "why-ai-changes-software-faster-than-previous-engineering-revolutions": {
        "hackernoon": {
            "title": "The Real Reason AI Is Moving Faster Than Past Engineering Shifts",
            "url": "https://hackernoon.com/the-real-reason-ai-is-moving-faster-than-past-engineering-shifts",
        }
    },
    "rise-of-intent-driven-development": {
        "hackernoon": {
            "title": "Software Engineering's New Bottleneck Is Requirements",
            "url": "https://hackernoon.com/software-engineerings-new-bottleneck-is-requirements",
        }
    },
    "software-engineering-after-coding-era": {
        "hackernoon": {
            "title": "AI Can Write Code Fast. Can Engineering Teams Govern It?",
            "url": "https://hackernoon.com/ai-can-write-code-fast-can-engineering-teams-govern-it",
        }
    },
    "arrivals": {
        "medium": {
            "url": "https://vwinland.medium.com/arrivals-bdf1d31539a3",
        }
    },
}


def sync_blog_repo():
    if BLOG_REPO_DIR.exists():
        subprocess.run(["git", "-C", str(BLOG_REPO_DIR), "pull", "--ff-only"], check=True)
    else:
        BLOG_REPO_DIR.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", BLOG_REPO_URL, str(BLOG_REPO_DIR)], check=True)


def parse_post(path: Path) -> SourceDocument | None:
    match = FRONTMATTER_RE.match(path.read_text())
    if not match:
        raise ValueError(f"{path} has no parseable frontmatter")
    frontmatter_raw, body = match.groups()
    meta = yaml.safe_load(frontmatter_raw)

    slug = meta["slug"]
    title = meta["title"]
    if slug in EXCLUDED_SLUGS or title.strip().lower() in EXCLUDED_TITLES:
        return None

    content_type = "personal_essay" if slug in PERSONAL_ESSAY_SLUGS else "essay"

    platform_urls = {"blog": f"{BLOG_BASE_URL}/{slug}"}
    syndicated_titles = {}
    for platform, info in SYNDICATION.get(slug, {}).items():
        platform_urls[platform] = info["url"]
        if "title" in info:
            syndicated_titles[platform] = info["title"]

    return SourceDocument(
        canonical_title=title,
        primary_platform="blog",
        content_type=content_type,
        published_date=meta["date"],
        body=body.strip(),
        syndicated_titles=syndicated_titles,
        platform_urls=platform_urls,
        series=meta.get("series"),
        series_part=meta.get("series_order"),
    )


def load_blog_documents() -> list[SourceDocument]:
    docs = []
    for path in sorted(BLOG_POSTS_DIR.glob("*.md")):
        doc = parse_post(path)
        if doc is not None:
            docs.append(doc)
    return docs


def reset_collection():
    """Drop any existing collection so re-running this loader doesn't pile
    up duplicate chunks (chunk_document mints a fresh uuid per chunk)."""
    import chromadb

    client = chromadb.PersistentClient(path=DB_PATH)
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass


def main():
    sync_blog_repo()
    docs = load_blog_documents()

    reset_collection()

    total_chunks = 0
    for doc in docs:
        chunks = chunk_document(doc)
        add_chunks(chunks)
        total_chunks += len(chunks)
        print(f"Indexed '{doc.canonical_title}' ({doc.content_type}): {len(chunks)} chunks")

    print(f"\nDone. {total_chunks} total chunks indexed across {len(docs)} documents.")


if __name__ == "__main__":
    main()
