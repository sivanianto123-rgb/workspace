"""Benchmark HNSW against exact brute-force search.

The story to look for: as ``ef_search`` rises, recall climbs toward 1.0 and so
does query time; and at the larger dataset sizes HNSW answers a query far
faster than brute force for any given recall level.

Run directly (``python -m vecsearch.benchmark``) or via ``vecsearch benchmark``.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field

import numpy as np

from .brute_force import BruteForceIndex
from .dataset import generate_random_vectors
from .hnsw import HNSWIndex

DEFAULT_SIZES = (1_000, 10_000, 50_000)
DEFAULT_DIM = 128
DEFAULT_EF_SEARCH = (10, 50, 100, 200)
DEFAULT_N_QUERIES = 100
DEFAULT_K = 10


@dataclass
class QueryRow:
    size: int
    ef_search: int
    recall: float
    hnsw_ms: float
    brute_ms: float

    @property
    def speedup(self) -> float:
        return self.brute_ms / self.hnsw_ms if self.hnsw_ms else float("inf")


@dataclass
class BuildRow:
    size: int
    brute_build_s: float
    hnsw_build_s: float


@dataclass
class BenchmarkResult:
    dim: int
    k: int
    n_queries: int
    m: int
    ef_construction: int
    builds: list[BuildRow] = field(default_factory=list)
    rows: list[QueryRow] = field(default_factory=list)


def _recall_at_k(true_ids: np.ndarray, got_ids: np.ndarray, k: int) -> float:
    return len(set(true_ids[:k].tolist()) & set(got_ids[:k].tolist())) / k


def run_benchmark(
    sizes=DEFAULT_SIZES,
    dim: int = DEFAULT_DIM,
    ef_search_values=DEFAULT_EF_SEARCH,
    n_queries: int = DEFAULT_N_QUERIES,
    k: int = DEFAULT_K,
    m: int = 16,
    ef_construction: int = 100,
    seed: int = 0,
    progress=lambda msg: print(msg, file=sys.stderr),
) -> BenchmarkResult:
    result = BenchmarkResult(
        dim=dim, k=k, n_queries=n_queries, m=m, ef_construction=ef_construction
    )
    rng = np.random.default_rng(seed)

    for size in sizes:
        progress(f"[size={size}] generating {size} x {dim} vectors")
        data = generate_random_vectors(size, dim, seed=int(rng.integers(1 << 31)))
        queries = generate_random_vectors(
            n_queries, dim, seed=int(rng.integers(1 << 31))
        )

        progress(f"[size={size}] building BruteForceIndex")
        t0 = time.perf_counter()
        brute = BruteForceIndex()
        brute.add(data)
        brute_build_s = time.perf_counter() - t0

        progress(f"[size={size}] building HNSWIndex (m={m}, ef_c={ef_construction})")
        t0 = time.perf_counter()
        hnsw = HNSWIndex(m=m, seed=seed, metric="cosine")
        for v in data:
            hnsw.insert(v, ef_construction=ef_construction)
        hnsw_build_s = time.perf_counter() - t0
        result.builds.append(BuildRow(size, brute_build_s, hnsw_build_s))

        # Exact ground truth + brute-force timing (independent of ef_search).
        true_ids = []
        t0 = time.perf_counter()
        for q in queries:
            ids, _ = brute.search(q, k=k, metric="cosine")
            true_ids.append(ids)
        brute_ms = (time.perf_counter() - t0) / n_queries * 1e3

        for ef in ef_search_values:
            progress(f"[size={size}] querying HNSW at ef_search={ef}")
            recalls = np.empty(n_queries)
            t0 = time.perf_counter()
            for i, q in enumerate(queries):
                ids, _ = hnsw.search(q, k=k, ef_search=ef)
                recalls[i] = _recall_at_k(true_ids[i], ids, k)
            hnsw_ms = (time.perf_counter() - t0) / n_queries * 1e3
            result.rows.append(
                QueryRow(size, ef, float(recalls.mean()), hnsw_ms, brute_ms)
            )

    return result


def format_tables(result: BenchmarkResult) -> str:
    lines: list[str] = []
    lines.append(
        f"dim={result.dim}  k={result.k}  queries={result.n_queries}  "
        f"m={result.m}  ef_construction={result.ef_construction}"
    )
    lines.append("")
    lines.append("Build time")
    lines.append(f"{'size':>8} | {'brute (s)':>10} | {'HNSW (s)':>10}")
    lines.append("-" * 34)
    for b in result.builds:
        lines.append(
            f"{b.size:>8} | {b.brute_build_s:>10.3f} | {b.hnsw_build_s:>10.3f}"
        )
    lines.append("")
    lines.append("Query (recall@%d, avg latency)" % result.k)
    header = (
        f"{'size':>8} | {'ef':>4} | {'recall@%d' % result.k:>9} | "
        f"{'HNSW ms':>9} | {'brute ms':>9} | {'speedup':>8}"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for r in result.rows:
        lines.append(
            f"{r.size:>8} | {r.ef_search:>4} | {r.recall:>9.3f} | "
            f"{r.hnsw_ms:>9.3f} | {r.brute_ms:>9.3f} | {r.speedup:>7.1f}x"
        )
    return "\n".join(lines)


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="HNSW vs brute-force benchmark")
    parser.add_argument(
        "--sizes",
        type=lambda s: [int(x) for x in s.split(",")],
        default=list(DEFAULT_SIZES),
    )
    parser.add_argument("--dim", type=int, default=DEFAULT_DIM)
    parser.add_argument(
        "--ef-search",
        type=lambda s: [int(x) for x in s.split(",")],
        default=list(DEFAULT_EF_SEARCH),
    )
    parser.add_argument("--queries", type=int, default=DEFAULT_N_QUERIES)
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    parser.add_argument("--m", type=int, default=16)
    parser.add_argument("--ef-construction", type=int, default=100)
    args = parser.parse_args(argv)

    result = run_benchmark(
        sizes=args.sizes,
        dim=args.dim,
        ef_search_values=args.ef_search,
        n_queries=args.queries,
        k=args.k,
        m=args.m,
        ef_construction=args.ef_construction,
    )
    print(format_tables(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
