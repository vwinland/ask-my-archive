"""
Streamlit chat interface for the RAG pipeline.

Imports query/ask.py's ask() directly rather than re-implementing retrieval
or generation — this app is a thin UI layer over the same pipeline the CLI
uses. Defaults to the Hugging Face free Serverless Inference backend, since
this is the public-facing deployment and there's no billing risk on a free
HF token (no payment method on file, so the worst case is a slow or failed
response, never a surprise bill). Claude and Ollama stay available as CLI
flags for local testing/comparison (see query/ask.py) but are not exposed
here, specifically so a public visitor can never trigger a paid API call.

Visual styling is a HackerNoon-inspired pixel aesthetic: dark background,
green accents, blocky borders, on top of the base dark theme set in
.streamlit/config.toml. Icons are pulled unmodified from HackerNoon's Pixel
Icon Library (app/assets/*.svg, CC BY 4.0 — see the footer for attribution)
and recolored via CSS rather than editing the SVG files themselves.
"""

import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent / "query"))

from ask import ask  # noqa: E402

BACKEND = "huggingface"
ASSETS_DIR = Path(__file__).parent / "assets"

GITHUB_REPO_URL = "https://github.com/vwinland/ask-my-archive"
PORTFOLIO_URL = "https://vwinland.github.io/"
BUILD_LOG_URL = "https://vwinland.github.io/blog/build-log-ask-my-archive/"
PIXEL_ICON_LIBRARY_URL = "https://github.com/hackernoon/pixel-icon-library"


def _resolve_hf_token() -> str | None:
    """Bridge st.secrets (deployed app) into the HF_TOKEN env var ask.py already
    reads, so ask.py itself never needs to know Streamlit exists. Falls back to
    a locally-exported env var for `streamlit run app.py` during development."""
    try:
        if "HF_TOKEN" in st.secrets:
            return st.secrets["HF_TOKEN"]
    except Exception:
        pass
    return os.environ.get("HF_TOKEN")


def _inject_css() -> None:
    css = (ASSETS_DIR / "style.css").read_text()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def icon(name: str) -> str:
    """Inline one of app/assets/*.svg as HTML. The SVG content itself is
    never edited — see the .pixel-icon CSS rule for how it gets recolored."""
    svg = (ASSETS_DIR / f"{name}.svg").read_text()
    return f'<span class="pixel-icon">{svg}</span>'


token = _resolve_hf_token()
if token:
    os.environ["HF_TOKEN"] = token

st.set_page_config(page_title="Ask My Archive", page_icon="📚")
_inject_css()

st.title("📚 Ask My Archive")
st.markdown(
    """*A search engine for one person's brain — mine, Vanna Winland's.*

Ask it anything. It'll dig through everything I've actually published,
find the relevant bits, and answer using only those, no filling in the
blanks. If I haven't written about it, it'll tell you instead of making
something up.

Running on a free model because paying per query felt excessive for a
Q&A tool about my own opinions."""
)

st.markdown(
    f"""
    <div class="archive-nav">
        <a href="{BUILD_LOG_URL}" target="_blank">{icon("book")} Read the build log</a>
        <a href="{GITHUB_REPO_URL}" target="_blank">View the code</a>
        <a href="{PORTFOLIO_URL}" target="_blank">My portfolio</a>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.form("ask_form"):
    st.markdown(
        f'<div class="archive-input-label">{icon("search")} Your question</div>',
        unsafe_allow_html=True,
    )
    question = st.text_input(
        "Your question",
        placeholder="e.g. What has Vanna written about AI and code review?",
        label_visibility="collapsed",
    )
    submitted = st.form_submit_button("Ask", use_container_width=True)

if submitted:
    if not question.strip():
        st.warning("Enter a question first.")
    else:
        with st.spinner("Searching the archive and drafting an answer..."):
            result = ask(question.strip(), backend=BACKEND)

        if result.error:
            st.info(f"Couldn't get an answer this time: {result.error}")
            if result.debug_detail:
                with st.expander("Technical details"):
                    st.code(result.debug_detail)
        else:
            st.markdown(
                f'<div class="archive-section-header">{icon("robot")}<span>Answer</span></div>',
                unsafe_allow_html=True,
            )
            if result.answer.strip():
                st.write(result.answer)
            else:
                st.write("No relevant information found in the archive for this question.")

            st.markdown(
                f'<div class="archive-section-header">{icon("book")}<span>Sources</span></div>',
                unsafe_allow_html=True,
            )
            if result.sources:
                for s in result.sources:
                    st.markdown(f"- [{s['title']}]({s['url']})")
            else:
                st.caption("No specific essay was cited for this answer.")

st.divider()
st.caption(
    "Answers are generated by a free Hugging Face model grounded only in "
    "excerpts retrieved from the essay archive — if the archive doesn't cover "
    "a topic, the model is instructed to say so rather than guess."
)

st.markdown(
    f"""
    <div class="archive-footer">
        Icons: <a href="{PIXEL_ICON_LIBRARY_URL}" target="_blank">HackerNoon's Pixel Icon Library</a>,
        licensed <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank">CC BY 4.0</a>.
        Used unmodified (recolored via CSS to match this page's theme).
    </div>
    """,
    unsafe_allow_html=True,
)
