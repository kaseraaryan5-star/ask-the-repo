# Ask the Repo

Ask questions about a Python codebase in plain English. Every answer cites the exact lines it came from, like `app/ask.py:52-57`, and every source comes with a GitHub permalink pinned to the indexed commit, so you can click through and check the code instead of trusting the answer.

## Example

Index a public GitHub repo, then ask about it:

```bash
curl -X POST http://127.0.0.1:8000/index \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/kaseraaryan5-star/ask-the-repo"}'
# {"status": "indexed", "repo": "https://github.com/kaseraaryan5-star/ask-the-repo", "chunks": 27}

curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What does the github_url function do?"}'
```

```json
{
  "answer": "The `github_url` function returns a permalink to the exact lines on GitHub, or `None` for locally indexed repos [app/ask.py:52-57].",
  "sources": [
    {
      "file": "app/ask.py",
      "start_line": 52,
      "end_line": 57,
      "symbol": "github_url",
      "score": 0.486,
      "url": "https://github.com/kaseraaryan5-star/ask-the-repo/blob/<commit>/app/ask.py#L52-L57"
    }
  ]
}
```

(`sources` is shortened here; the API returns the top 8 retrieved chunks by default.)

## How it works

```
GitHub URL -> clone -> AST chunking (functions, classes, methods)
           -> embeddings (all-MiniLM-L6-v2, 384-dim) -> Qdrant

Question -> embed -> top-8 chunks -> Gemini -> answer with file:line citations + permalinks
```

- **Cloning:** `POST /index` clones a public GitHub repo and records its commit, so every permalink points at the exact code that was indexed.
- **AST chunking:** the Python `ast` module splits each file into function, class and method chunks. Every chunk keeps its file, symbol name and line range, which is what makes exact citations possible. Chunks longer than 3000 characters are split into parts.
- **Indexing:** each chunk (path, docstring and code) is embedded with `sentence-transformers/all-MiniLM-L6-v2` and stored in Qdrant (embedded local mode, cosine distance). Chunk IDs are deterministic, so re-indexing never creates duplicates.
- **Answering:** the top chunks go to Google Gemini with a prompt that allows answers only from those chunks and requires `[file:start-end]` citations. If the answer is not in the retrieved code, the model says so instead of guessing.
- **Reliability:** Gemini calls retry with backoff on 429/500/503 errors and fall back to a second model.

## API

| Endpoint | Body | Description |
|---|---|---|
| `POST /index` | `{"repo_url": "..."}` | Clone and index a public GitHub repo (replaces the previous one) |
| `POST /ask` | `{"question": "...", "k": 8}` | Answer with citations and permalinks. `k` is optional (default 8) |

## Evaluation

17 hand-written questions, each with the correct chunk labelled in advance, run on a 27-chunk Python repo. A question counts as a hit when the right chunk is in the top results.

| Chunking strategy | Chunks | Top-1 | Top-3 | MRR |
|---|---|---|---|---|
| **AST (function-level)** | 27 | **71%** | **100%** | **0.84** |
| Fixed 1000 characters | 24 | 53% | 82% | 0.65 |

For the fixed-size baseline, a retrieved chunk counts as a hit if it overlaps the lines of the correct function, which is generous to the baseline.

Reproduce:

```bash
python3 -m evals.run_eval                                  # retrieval metrics
python3 -m evals.compare_chunking /path/to/repo            # AST vs fixed-size
```

Caveats: the set is small (17 questions, 3 questions separate the two strategies), the repo is small, the labels are function-level (which suits AST chunking), and only one fixed-size setting was tried. Treat it as a first measurement, not a benchmark.

## Run locally

1. Install dependencies:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and add your Google API key. Optionally set the models:
   ```
   GOOGLE_API_KEY=your-key-here
   GEMINI_MODEL=your-primary-model
   GEMINI_FALLBACK_MODEL=your-fallback-model
   ```
3. Start the API:
   ```bash
   python3 -m uvicorn app.api:app --port 8000
   ```
4. Open http://127.0.0.1:8000/docs, call `POST /index` with a GitHub repo URL, then `POST /ask`.

Or use the command line on a local folder (no permalinks in this mode):

```bash
python3 -m app.indexer index /path/to/python/repo
python3 -m app.ask "How does authentication work?"
```

Qdrant runs in embedded local mode (data in `qdrant_data/`), so only one process can use it at a time. Stop the API before running the indexer or the evals.

## Project layout

```
app/github.py           clone a repo, parse URLs
app/code_chunker.py     AST chunking with line ranges
app/naive_chunker.py    fixed-size baseline for comparison
app/indexer.py          embeddings, Qdrant, semantic search
app/ask.py              prompt, Gemini call, retry and fallback, permalinks
app/api.py              FastAPI: POST /index, POST /ask
evals/golden.json       labelled questions
evals/run_eval.py       top-k accuracy and MRR
evals/compare_chunking.py   AST vs fixed-size
```

## Limitations

- Python only. Module-level code is skipped when a file contains functions or classes.
- `/index` clones from GitHub, so it only sees committed code, not local uncommitted changes.
- One indexed repo at a time; indexing replaces the previous one. Repos over 1500 chunks are rejected.
- Comparison questions ("difference between X and Y") need chunks from several files. In testing, `k=5` answered "could not find", while `k=10` answered correctly, so the default is 8 and `k` can be raised per request.
- Citations come from the model, so it can occasionally cite a line range that was not retrieved. Checking citations against the retrieved chunks is not implemented yet.
- The embedding model is small; similarly named functions can be confused (visible in the top-1 misses in the eval).
- The evaluation is small, as described above.

## Next steps

- Validate that every citation matches a retrieved chunk
- Larger evaluation on bigger repositories; try a stronger embedding model and hybrid (BM25 + vector) retrieval
- Redis answer cache, async endpoint, Docker Compose, tests and CI

## Author

Aryan Kasera | [GitHub](https://github.com/kaseraaryan5-star) | [X](https://x.com/KaseraAryan) | [LinkedIn](https://www.linkedin.com/in/aryan-kasera-ai)
