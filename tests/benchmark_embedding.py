"""Benchmark: CPU local embedding vs Xinference GPU embedding.

Usage:
    python tests/benchmark_embedding.py                  # test local (EMBEDDING_BACKEND=local)
    python tests/benchmark_embedding.py --backend xinference  # test GPU (requires xinference running)

Requires: pytest, requests, openai
"""

import argparse
import time
import sys
from pathlib import Path

import requests

BASE_URL = "http://localhost:8000"
XINFERENCE_URL = "http://localhost:9997"


def generate_test_chunks(n: int = 99, avg_words: int = 150) -> list[str]:
    """Generate synthetic text chunks for benchmarking."""
    words = [
        "the", "quick", "brown", "fox", "jumps", "over", "lazy", "dog",
        "machine", "learning", "natural", "language", "processing", "embedding",
        "vector", "semantic", "search", "document", "indexing", "retrieval",
        "artificial", "intelligence", "neural", "network", "training", "dataset",
    ]
    chunks = []
    import random
    rng = random.Random(42)
    for _ in range(n):
        length = rng.randint(avg_words - 50, avg_words + 50)
        text = " ".join(rng.choice(words) for _ in range(length))
        chunks.append(text)
    return chunks


def benchmark_local(chunks: list[str]) -> dict:
    """Benchmark via FastAPI /api/v1/embeddings endpoint."""
    payload = {"texts": chunks}
    start = time.monotonic()
    resp = requests.post(f"{BASE_URL}/api/v1/embeddings", json=payload, timeout=600)
    elapsed = time.monotonic() - start

    if resp.status_code != 200:
        print(f"  ERROR: {resp.status_code} — {resp.text[:200]}")
        sys.exit(1)

    data = resp.json()
    return {
        "backend": "local (CPU)",
        "elapsed_sec": elapsed,
        "num_chunks": len(chunks),
        "chunks_per_sec": len(chunks) / elapsed if elapsed > 0 else 0,
        "vector_dim": len(data.get("embeddings", [[]])[0]) if data.get("embeddings") else 0,
    }


def benchmark_xinference(chunks: list[str]) -> dict:
    """Benchmark via Xinference OpenAI-compatible API."""
    from openai import AsyncOpenAI, OpenAI

    client = OpenAI(base_url=f"{XINFERENCE_URL}/v1", api_key="fake")
    start = time.monotonic()
    resp = client.embeddings.create(model="bge-m3", input=chunks)
    elapsed = time.monotonic() - start

    embeddings = [e.embedding for e in resp.data]
    return {
        "backend": "xinference (GPU)",
        "elapsed_sec": elapsed,
        "num_chunks": len(chunks),
        "chunks_per_sec": len(chunks) / elapsed if elapsed > 0 else 0,
        "vector_dim": len(embeddings[0]) if embeddings else 0,
    }


def main():
    parser = argparse.ArgumentParser(description="Embedding benchmark")
    parser.add_argument("--backend", choices=["local", "xinference"], default=None)
    parser.add_argument("--num-chunks", type=int, default=99)
    parser.add_argument("--avg-words", type=int, default=150)
    args = parser.parse_args()

    chunks = generate_test_chunks(args.num_chunks, args.avg_words)
    total_bytes = sum(len(c.encode()) for c in chunks)
    print(f"Generated {len(chunks)} chunks, {total_bytes / 1024:.1f} KB total\n")

    results = []

    if args.backend == "xinference" or args.backend is None:
        if args.backend is None:
            print("=" * 60)
            print("Test 1: Xinference (GPU) embedding")
            print("=" * 60)
        try:
            r = benchmark_xinference(chunks)
            results.append(r)
            print(f"  Chunks:     {r['num_chunks']}")
            print(f"  Time:       {r['elapsed_sec']:.2f}s")
            print(f"  Rate:       {r['chunks_per_sec']:.2f} chunks/sec")
            print(f"  Vector dim: {r['vector_dim']}")
        except Exception as e:
            print(f"  FAILED: {e}")

    if args.backend == "local" or args.backend is None:
        if args.backend is None:
            print(f"\n{'=' * 60}")
            print("Test 2: Local (CPU) embedding")
            print("=" * 60)
        try:
            r = benchmark_local(chunks)
            results.append(r)
            print(f"  Chunks:     {r['num_chunks']}")
            print(f"  Time:       {r['elapsed_sec']:.2f}s")
            print(f"  Rate:       {r['chunks_per_sec']:.2f} chunks/sec")
            print(f"  Vector dim: {r['vector_dim']}")
        except Exception as e:
            print(f"  FAILED: {e}")

    # Summary
    if len(results) == 2:
        gpu = results[0]
        cpu = results[1]
        speedup = cpu["elapsed_sec"] / gpu["elapsed_sec"] if gpu["elapsed_sec"] > 0 else float("inf")
        print(f"\n{'=' * 60}")
        print("SUMMARY")
        print("=" * 60)
        print(f"  GPU time:   {gpu['elapsed_sec']:.2f}s  ({gpu['backend']})")
        print(f"  CPU time:   {cpu['elapsed_sec']:.2f}s  ({cpu['backend']})")
        print(f"  Speedup:    {speedup:.1f}x")
        print(f"  Time saved: {cpu['elapsed_sec'] - gpu['elapsed_sec']:.1f}s")


if __name__ == "__main__":
    main()
