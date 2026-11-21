"""Embed code chunks and store them in Qdrant, then search them."""

import sys
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from app.code_chunker import chunk_repo

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"  # 384 dimensions
COLLECTION = "code_chunks"
DB_PATH = "qdrant_data"

_model = None
_client = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def get_client():
    global _client
    if _client is None:
        _client = QdrantClient(path=DB_PATH)
    return _client


def index_repo(root, base_url=None, max_chunks=None):
    """Index a repo (replacing the previous one). Returns the number of chunks."""
    chunks = chunk_repo(root)
    if not chunks:
        raise ValueError("No Python code found in this repo.")
    if max_chunks and len(chunks) > max_chunks:
        raise ValueError(f"Repo too large: {len(chunks)} chunks (limit {max_chunks}).")

    model = get_model()
    client = get_client()

    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
    client.create_collection(
        COLLECTION,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
    )

    vectors = model.encode([c["text"] for c in chunks], show_progress_bar=True)
    points = []
    for c, vec in zip(chunks, vectors):
        # same chunk -> same id, so re-indexing never creates duplicates
        key = f"{c['file']}:{c['start_line']}-{c['end_line']}:{c['symbol']}"
        payload = {k: c[k] for k in
                   ("file", "symbol", "kind", "start_line", "end_line", "code")}
        payload["base_url"] = base_url  # GitHub permalink base, None for local repos
        points.append(PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, key)),
            vector=vec.tolist(),
            payload=payload,
        ))
    client.upsert(COLLECTION, points)
    print(f"Indexed {len(points)} chunks into '{COLLECTION}'.")
    return len(points)


def search(query, k=3):
    model = get_model()
    client = get_client()
    vec = model.encode(query).tolist()
    hits = client.query_points(COLLECTION, query=vec, limit=k).points
    for h in hits:
        p = h.payload
        print(f"{h.score:.3f}  {p['file']}:{p['start_line']}-{p['end_line']}  {p['symbol']}")
    return hits


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "index":
        try:
            index_repo(sys.argv[2])
        except ValueError as e:
            print(e)
    elif len(sys.argv) >= 3 and sys.argv[1] == "search":
        search(" ".join(sys.argv[2:]))
    else:
        print('Usage:\n  python3 -m app.indexer index <repo_path>\n  python3 -m app.indexer search "your question"')