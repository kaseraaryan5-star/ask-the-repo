"""Compare chunking strategies on the same golden questions."""

import json
import sys

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app import code_chunker, naive_chunker
from app.indexer import get_model


def build(chunks):
    client = QdrantClient(":memory:")
    client.create_collection(
        "c", vectors_config=VectorParams(size=384, distance=Distance.COSINE))
    vecs = get_model().encode([c["text"] for c in chunks], show_progress_bar=False)
    client.upsert("c", [
        PointStruct(id=i, vector=v.tolist(), payload=c)
        for i, (c, v) in enumerate(zip(chunks, vecs))
    ])
    return client


def evaluate(client, cases, targets, k=3):
    model = get_model()
    top1 = topk = 0
    rr = 0.0
    for case in cases:
        spans = [targets[e] for e in case["expected"]]
        hits = client.query_points(
            "c", query=model.encode(case["q"]).tolist(), limit=k).points
        rank = None
        for i, h in enumerate(hits, start=1):
            p = h.payload
            if any(p["file"] == f and p["start_line"] <= end and s <= p["end_line"]
                   for f, s, end in spans):
                rank = i
                break
        top1 += rank == 1
        topk += rank is not None
        rr += 1 / rank if rank else 0
    n = len(cases)
    return top1 / n, topk / n, rr / n


if __name__ == "__main__":
    repo = sys.argv[1]
    cases = json.load(open("evals/golden.json", encoding="utf-8"))
    ast_chunks = code_chunker.chunk_repo(repo)
    targets = {f"{c['file']}::{c['symbol']}": (c["file"], c["start_line"], c["end_line"])
              for c in ast_chunks}
    naive_chunks = naive_chunker.chunk_repo(repo)

    print(f"{'strategy':<22}{'chunks':>7}{'top-1':>8}{'top-3':>8}{'MRR':>8}")
    for name, chunks in [("AST (function-level)", ast_chunks),
                         ("Fixed 1000 chars", naive_chunks)]:
        t1, t3, mrr = evaluate(build(chunks), cases, targets)
        print(f"{name:<22}{len(chunks):>7}{t1:>8.0%}{t3:>8.0%}{mrr:>8.3f}")