import os

import streamlit as st

# On Streamlit Cloud the keys live in st.secrets; the app code reads os.environ.
try:
    for key in ("GOOGLE_API_KEY", "GEMINI_MODEL", "GEMINI_FALLBACK_MODEL"):
        if key in st.secrets and not os.getenv(key):
            os.environ[key] = str(st.secrets[key])
except Exception:
    pass  # no secrets file locally; .env is used instead

from app.ask import answer
from app.github import clone
from app.indexer import index_repo

MAX_CHUNKS = 1500


def friendly_error(e: Exception) -> str:
    msg = str(e)
    if "503" in msg or "UNAVAILABLE" in msg:
        return (
            "Gemini is busy right now (high demand on Google's side). "
            "Please wait a minute and press Ask again."
        )
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
        return (
            "The demo's Gemini quota is rate-limited right now. "
            "Please try again in a few minutes."
        )
    if "API key" in msg or "PERMISSION_DENIED" in msg:
        return "The demo is misconfigured (API key issue). Please try again later."
    return "Something went wrong while generating the answer. Please try again."


st.set_page_config(page_title="Ask the Repo", page_icon="🔎")
st.title("🔎 Ask the Repo")
st.caption(
    "Ask questions about a public Python repo on GitHub. Every answer cites file:line "
    "and links to the exact code. Demo may be rate-limited; if it fails, try again in a minute."
)

st.subheader("1. Repo URL")
repo_url = st.text_input(
    "Public GitHub repo URL",
    value=st.session_state.get("indexed_repo", ""),
    placeholder="https://github.com/owner/repo",
)

if st.button("Index repo"):
    if not repo_url.strip():
        st.warning("Paste a GitHub repo URL first.")
    else:
        try:
            with st.spinner("Cloning and indexing (10-30 seconds)..."):
                with clone(repo_url.strip()) as (path, base_url):
                    n = index_repo(path, base_url=base_url, max_chunks=MAX_CHUNKS)
            st.session_state["indexed_repo"] = repo_url.strip()
            st.session_state["chunks"] = n
            st.success(f"Indexed {n} chunks.")
        except ValueError as e:
            st.error(str(e))
        except Exception as e:  # network, git, embedding errors
            st.error(f"Indexing failed: {e}")
            
st.caption(
    f"DEBUG key={bool(os.getenv('GOOGLE_API_KEY'))} "
    f"model={os.getenv('GEMINI_MODEL')} fallback={os.getenv('GEMINI_FALLBACK_MODEL')}"
)

st.subheader("2. Ask a question")
if "indexed_repo" not in st.session_state:
    st.info(
        "Index a repo first. Note: the index is shared, so indexing a new repo "
        "replaces the previous one."
    )
else:
    st.caption(
        f"Indexed: {st.session_state['indexed_repo']} "
        f"({st.session_state.get('chunks', '?')} chunks)"
    )
    question = st.text_input(
        "Your question", placeholder="What does the github_url function do?"
    )
    k = st.slider(
        "How many code chunks to retrieve",
        3, 12, 8,
        help="Comparison questions ('difference between X and Y') need a higher value.",
    )
    if st.button("Ask") and question.strip():
        try:
            with st.spinner("Thinking..."):
                result = answer(question.strip(), k)
            st.markdown("**Answer**")
            st.write(result["answer"])
            st.markdown("**Sources**")
            for s in result.get("sources", []):
                label = f"{s['file']}:{s['start_line']}-{s['end_line']} ({s.get('symbol', '')})"
                if s.get("url"):
                    st.markdown(f"- [{label}]({s['url']}) · score {s.get('score', '')}")
                else:
                    st.markdown(f"- {label} · score {s.get('score', '')}")
        except Exception as e:
            st.warning(friendly_error(e))
            with st.expander("Technical details"):
                st.code(str(e))