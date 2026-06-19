"""End-to-end GPU verification for BGE reranker.

Usage:
    python tests/gpu_verify.py

Checks:
1. CUDA is available and GPU is detected
2. BGE reranker loads to GPU successfully
3. Warmup and cold rerank timing
4. Reranker correctly uses GPU device (not CPU)
"""
import asyncio
import time
import subprocess
import torch

from app.adapters.reranker.bge import BGEReranker
from app.adapters.reranker.factory import get_reranker


def get_gpu_mem_mb():
    """Query GPU memory via nvidia-smi."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used",
             "--format=csv,noheader,nounits", "-i", "0"],
            capture_output=True, text=True, timeout=5,
        )
        return int(r.stdout.strip())
    except Exception:
        return 0


async def main():
    # === Check 1: CUDA availability ===
    print("=" * 60)
    print("CHECK 1: CUDA Availability")
    print("=" * 60)
    print(f"  CUDA available: {torch.cuda.is_available()}")
    if not torch.cuda.is_available():
        print("  FAIL: CUDA not available. Cannot proceed.")
        return False
    print(f"  CUDA version: {torch.version.cuda}")
    print(f"  GPU count: {torch.cuda.device_count()}")
    for i in range(torch.cuda.device_count()):
        print(f"  GPU {i}: {torch.cuda.get_device_name(i)}")
    print()

    # === Check 2: GPU memory before load ===
    gpu_mem_before = get_gpu_mem_mb()
    print("=" * 60)
    print("CHECK 2: GPU Memory Before Model Load")
    print("=" * 60)
    print(f"  GPU memory: {gpu_mem_before} MB")
    print()

    # === Check 3: Load BGE reranker to GPU ===
    print("=" * 60)
    print("CHECK 3: Load BGE Reranker to GPU")
    print("=" * 60)
    t0 = time.time()
    reranker = BGEReranker(
        model_name="D:/models/BAAI/bge-reranker-v2-m3",
        use_fp16=True,
    )
    reranker.warmup()
    load_time = time.time() - t0
    print(f"  Load + warmup time: {load_time:.2f}s (cold)")
    print(f"  Model loaded: {reranker._model is not None}")
    print()

    # === Check 4: GPU memory after load + warmup ===
    gpu_mem_after = get_gpu_mem_mb()
    print("=" * 60)
    print("CHECK 4: GPU Memory After Load + Warmup")
    print("=" * 60)
    print(f"  GPU memory: {gpu_mem_after} MB")
    print(f"  Model VRAM: {gpu_mem_after - gpu_mem_before} MB")
    print()

    # === Check 5: Rerank timing (cold → warm) ===
    print("=" * 60)
    print("CHECK 5: Rerank Timing (Cold -> Warm)")
    print("=" * 60)
    test_docs = [
        {"text": f"Document {i} about machine learning and deep neural networks."}
        for i in range(50)
    ]
    # Cold run (first call after warmup)
    t0 = time.time()
    result = await reranker.rerank("What is deep learning?", test_docs, top_k=10)
    cold_time = time.time() - t0
    # Warm run
    t0 = time.time()
    result = await reranker.rerank("What is deep learning?", test_docs, top_k=10)
    warm_time = time.time() - t0
    # Another warm run
    t0 = time.time()
    result = await reranker.rerank("What is deep learning?", test_docs, top_k=10)
    warm2_time = time.time() - t0
    print(f"  Documents: 50, Top-k: 10")
    print(f"  Cold rerank:  {cold_time*1000:.1f}ms")
    print(f"  Warm rerank:  {warm_time*1000:.1f}ms")
    print(f"  Warm rerank2: {warm2_time*1000:.1f}ms")
    print()

    # === Check 6: Factory reranker check ===
    print("=" * 60)
    print("CHECK 6: Factory Reranker Configuration")
    print("=" * 60)
    factory_reranker = get_reranker()
    print(f"  Provider: {factory_reranker.__class__.__name__}")
    if hasattr(factory_reranker, "_s2"):
        print(f"  Stage 2: {factory_reranker._s2.__class__.__name__}")
    print()

    # === Summary ===
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    gpu_vram_used = gpu_mem_after - gpu_mem_before
    gpu_ok = gpu_vram_used > 100  # >100MB indicates GPU loading
    print(f"  CUDA available:        {'OK' if torch.cuda.is_available() else 'FAIL'}")
    print(f"  GPU detected:          OK ({torch.cuda.get_device_name(0)})")
    print(f"  Model loaded:          {'OK' if reranker._model is not None else 'FAIL'}")
    print(f"  GPU VRAM used:         {gpu_vram_used} MB ({'OK' if gpu_ok else 'FAIL - may be on CPU'})")
    print(f"  Warm rerank (50 docs): {warm_time*1000:.1f}ms")
    print(f"  Overall:               {'PASS' if (gpu_ok and reranker._model is not None) else 'FAIL'}")
    print()
    return gpu_ok and reranker._model is not None


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
