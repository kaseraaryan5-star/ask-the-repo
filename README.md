# Ask the Repo

Ask questions about a Python codebase in plain English. Every answer cites the exact lines it came from, like `app/vector_db.py:41-68`, so you can check it instead of trusting it.

## Example

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Where are the document chunks stored?"}'
```

```json
{
  "answer": "Based on the provided code chunks, the text chunks are stored in Qdrant [app/vector_db.py:41-68].",
  "sources": [
    {
      "file": "app/vector_db.py",
      "start_line": 41,
      "end_line": 68,
      "symbol": "VectorStore.upsert_transcript",
      "score": 0.274
    }
  ]
}
```

(`sources` is shortened here; the API returns the top 5 retrieved chunks.)

## How it works

```
Python repo -> AST chunking (functions, classes, methods)
            -> embeddings (all-MiniLM-L6-v2, 384-dim) -> Qdrant

Question -> embed -> top-5 chunks -> Gemini -> answer with file:line citations
```

- **AST chunking:** the Python `ast` module splits each file into function, class and method chunks. Every chunk keeps its file, symbol name and line range, which is what makes exact citations possible. Chunks longer than 3000 characters are split into parts.
- **Indexing:** each chunk (path, docstring and code) is embedded with `sentence-transformers/all-MiniLM-L6-v2` and stored in Qdrant (embedded local mode, cosine distance). Chunk IDs are deterministic, so re-indexing never creates duplicates.
- **Answering:** the top 5 chunks go to Google Gemini with a prompt that allows answers only from those chunks and requires `[file:start-end]` citations.
- **Reliability:** Gemini calls retry with backoff on 429/500/503 errors and fall back to a second model.

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
3. Index a repo (this replaces the previously indexed repo):
   ```bash
   python3 -m app.indexer index /path/to/python/repo
   ```
4. Ask from the command line:
   ```bash
   python3 -m app.ask "How does authentication work?"
   ```
5. Or start the API and open http://127.0.0.1:8000/docs:
   ```bash
   python3 -m uvicorn app.api:app --port 8000
   ```

Qdrant runs in embedded local mode (data in `qdrant_data/`), so only one process can use it at a time. Stop the API before running the indexer or the evals.

## Project layout

```
app/code_chunker.py     AST chunking with line ranges
app/naive_chunker.py    fixed-size baseline for comparison
app/indexer.py          embeddings, Qdrant, semantic search
app/ask.py              prompt, Gemini call, retry and fallback
app/api.py              FastAPI: POST /ask
evals/golden.json       labelled questions
evals/run_eval.py       top-k accuracy and MRR
evals/compare_chunking.py   AST vs fixed-size
```

## Limitations

- Python only. Module-level code is skipped when a file contains functions or classes.
- One indexed repo at a time; indexing replaces the previous one.
- Citations come from the model, so it can occasionally cite a line range that was not retrieved. Checking citations against the retrieved chunks is not implemented yet.
- The embedding model is small; similarly named functions can be confused (visible in the top-1 misses in the eval).
- The evaluation is small, as described above.

## Next steps

- `POST /index` to index a GitHub repo from its URL
- Validate that every citation matches a retrieved chunk
- Larger evaluation on bigger repositories; try a stronger embedding model and hybrid (BM25 + vector) retrieval
- Redis answer cache, async endpoint, Docker Compose, tests and CI

## Author

Aryan Kasera | [GitHub](https://github.com/kaseraaryan5-star) | [X](https://x.com/KaseraAryan) | [LinkedIn](https://www.linkedin.com/in/aryan-kasera-ai)
