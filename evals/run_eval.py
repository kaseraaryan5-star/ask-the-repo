"""Measure retrieval quality: does the right chunk land in the top-k?"""

import json
import sys

from app.indexer import COLLECTION, get_client, get_model


def retrieve(question, k):
    vec = get_model().encode(question).tolist()
    hits = get_client().query_points(COLLECTION, query=vec, limit=k).points
    # "foo (part 1/2)" -> "foo"
    return [f"{h.payload['file']}::{h.payload['symbol'].split(' (part')[0]}" for h in hits]


def main(path="evals/golden.json", k=3):
    cases = json.load(open(path, encoding="utf-8"))
    top1 = topk = 0
    rr_sum = 0.0
    for c in cases:
        got = retrieve(c["q"], k)
        rank = next((i + 1 for i, g in enumerate(got) if g in c["expected"]), None)
        top1 += rank == 1
        topk += rank is not None
        rr_sum += 1 / rank if rank else 0
        mark = f"rank {rank}" if rank else "MISS"
        print(f"[{mark:>6}] {c['q']}")
        if rank != 1:
            print(f"          expected: {c['expected']}")
            print(f"          got:      {got}")
    n = len(cases)
    print(f"\nQuestions: {n}")
    print(f"Top-1 accuracy: {top1}/{n} = {top1 / n:.0%}")
    print(f"Top-{k} accuracy: {topk}/{n} = {topk / n:.0%}")
    print(f"MRR: {rr_sum / n:.3f}")


if __name__ == "__main__":
    main(k=int(sys.argv[1]) if len(sys.argv) > 1 else 3)