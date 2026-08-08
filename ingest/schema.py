"""
Metadata schema for indexed chunks.

This is the schema we designed to handle:
- Syndication across platforms (blog is canonical; HackerNoon/Medium are
  syndicated copies with their own titles and URLs)
- Multiple source platforms with different content types (personal essays,
  technical essays, IBM Think explainers/tutorials)
- Co-authored pieces (a couple of IBM Think articles have a second author)
"""

from dataclasses import dataclass, field


@dataclass
class SourceDocument:
    """One canonical piece of writing, before chunking."""

    canonical_title: str
    primary_platform: str  # "blog" | "ibm_think" | "ibmdotcom_tutorials"
    content_type: str  # "essay" | "personal_essay" | "explainer" | "tutorial" | "insight"
    published_date: str  # ISO format, e.g. "2026-06-16"
    body: str  # full markdown/plain text body

    # Syndication (only populated for blog-originated pieces)
    syndicated_titles: dict = field(default_factory=dict)  # {"hackernoon": "...", "medium": "..."}
    platform_urls: dict = field(default_factory=dict)  # {"blog": "...", "hackernoon": "...", ...}

    # Series membership, if any
    series: str | None = None  # e.g. "Actually Agentic"
    series_part: int | None = None

    # Co-authorship, for IBM Think pieces written with someone else
    co_authors: list[str] = field(default_factory=list)


@dataclass
class Chunk:
    """One retrievable unit stored in the vector store."""

    chunk_id: str
    text: str
    canonical_title: str
    primary_platform: str
    content_type: str
    published_date: str
    platform_urls: dict
    series: str | None = None
    co_authors: list[str] = field(default_factory=list)

    def to_metadata_dict(self) -> dict:
        """Chroma metadata values must be str/int/float/bool, not nested
        dicts or lists, so we flatten here."""
        return {
            "canonical_title": self.canonical_title,
            "primary_platform": self.primary_platform,
            "content_type": self.content_type,
            "published_date": self.published_date,
            "series": self.series or "",
            "co_authors": ", ".join(self.co_authors) if self.co_authors else "",
            # flatten platform_urls into individual fields so they're filterable
            "url_blog": self.platform_urls.get("blog", ""),
            "url_hackernoon": self.platform_urls.get("hackernoon", ""),
            "url_medium": self.platform_urls.get("medium", ""),
            "url_ibm_think": self.platform_urls.get("ibm_think", ""),
        }
