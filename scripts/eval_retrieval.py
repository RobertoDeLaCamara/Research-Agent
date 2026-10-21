#!/usr/bin/env python3
"""Compare dense, lexical and hybrid retrieval on a set of (question, gold chunk id) pairs.

    python scripts/eval_retrieval.py --persist-dir data/chroma_db --questions questions.jsonl

questions.jsonl: one JSON object per line, {"question": "...", "gold_id": "<chunk id in the collection>"}.
A hit is any retrieved chunk whose normalised text equals the gold chunk's text, so duplicate chunks
(same book in two editions) do not count as misses. Prints R@1/5/10 and MRR@10 per mode, plus a
paired bootstrap 95% CI of the hybrid-minus-dense difference.

Point --persist-dir at a COPY of the live Chroma directory: the first hybrid query builds the keyword
index (``--lexical-path``) from the collection.
"""
import argparse
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from src.tools.vector_store import VectorStoreManager  # noqa: E402


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def rank_of(hits, gold_text):
    for rank, h in enumerate(hits, start=1):
        if norm(h["content"]) == gold_text:
            return rank
    return 999


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--persist-dir", required=True)
    ap.add_argument("--questions", required=True)
    ap.add_argument("--lexical-path", default=None)
    ap.add_argument("--candidates", type=int, default=50)
    args = ap.parse_args()

    store = VectorStoreManager(args.persist_dir, lexical_path=args.lexical_path)
    rows = [json.loads(line) for line in open(args.questions) if line.strip()]
    gold = store._collection.get(ids=[r["gold_id"] for r in rows], include=["documents"])
    gold_text = {i: norm(d) for i, d in zip(gold["ids"], gold["documents"])}
    rows = [r for r in rows if r["gold_id"] in gold_text]
    print(f"{len(rows)} questions, {store.count()} chunks, candidates={args.candidates}")

    modes = {
        "dense": lambda q: store.query_similar(q, n_results=10),
        "lexical": lambda q: store.query_lexical(q, n_results=10),
        "hybrid": lambda q: store.query_hybrid(q, n_results=10, candidates=args.candidates),
    }
    ranks = {m: np.array([rank_of(fn(r["question"]), gold_text[r["gold_id"]]) for r in rows]) for m, fn in modes.items()}

    rng = np.random.default_rng(0)

    def ci(x, boot=2000):
        s = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(boot)]
        return np.percentile(s, [2.5, 97.5])

    metric = {
        "R@1": lambda r: (r <= 1).astype(float),
        "R@5": lambda r: (r <= 5).astype(float),
        "R@10": lambda r: (r <= 10).astype(float),
        "MRR@10": lambda r: np.where(r <= 10, 1.0 / r, 0.0),
    }
    print(f"{'mode':9}" + "".join(f"{m:>9}" for m in metric))
    for mode, r in ranks.items():
        print(f"{mode:9}" + "".join(f"{f(r).mean():9.3f}" for f in metric.values()))
    print("\nhybrid - dense (paired bootstrap, 95% CI):")
    for name, f in metric.items():
        d = f(ranks["hybrid"]) - f(ranks["dense"])
        lo, hi = ci(d)
        flag = "  *significant*" if lo > 0 or hi < 0 else ""
        print(f"  {name:7} {d.mean():+.3f}  [{lo:+.3f}, {hi:+.3f}]{flag}")


if __name__ == "__main__":
    main()
