"""Command-line interface: ``vecsearch build | query | benchmark``."""

from __future__ import annotations

import argparse
import sys

import numpy as np

from .benchmark import DEFAULT_DIM, DEFAULT_EF_SEARCH, DEFAULT_SIZES, format_tables, run_benchmark
from .hnsw import HNSWIndex
from .persistence import load_index, save_index


def _int_list(s: str) -> list[int]:
    return [int(x) for x in s.split(",") if x.strip()]


def _cmd_build(args: argparse.Namespace) -> int:
    vectors = np.load(args.vectors)
    if vectors.ndim != 2:
        raise SystemExit(f"expected an (n, dim) array, got shape {vectors.shape}")

    index = HNSWIndex(m=args.m, seed=args.seed, metric=args.metric)
    for i, v in enumerate(vectors):
        index.insert(v, ef_construction=args.ef_construction)
        if args.verbose and (i + 1) % 1000 == 0:
            print(f"  inserted {i + 1}/{len(vectors)}", file=sys.stderr)

    save_index(index, args.output)
    print(
        f"built HNSWIndex: {len(index)} vectors, dim={vectors.shape[1]}, "
        f"m={index.m}, m0={index.m0}, max_level={index.max_level} -> {args.output}"
    )
    return 0


def _cmd_query(args: argparse.Namespace) -> int:
    index = load_index(args.index)
    query = np.load(args.query)
    query = np.asarray(query, dtype=np.float64).ravel()

    ids, dists = index.search(query, k=args.k, ef_search=args.ef_search)
    print(f"top {len(ids)} of {len(index)} (ef_search={args.ef_search}):")
    print(f"{'rank':>4}  {'id':>8}  {'distance':>12}")
    for rank, (i, d) in enumerate(zip(ids.tolist(), dists.tolist()), start=1):
        print(f"{rank:>4}  {i:>8}  {d:>12.6f}")
    return 0


def _cmd_benchmark(args: argparse.Namespace) -> int:
    result = run_benchmark(
        sizes=args.sizes,
        dim=args.dim,
        ef_search_values=args.ef_search,
        n_queries=args.queries,
        m=args.m,
        ef_construction=args.ef_construction,
    )
    print(format_tables(result))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vecsearch", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="build an HNSW index from an .npy matrix")
    p_build.add_argument("vectors", help="path to an (n, dim) .npy array")
    p_build.add_argument("--output", "-o", required=True, help="path for the .pkl index")
    p_build.add_argument("--m", type=int, default=16, help="max connections per layer (default 16)")
    p_build.add_argument("--ef-construction", type=int, default=100, dest="ef_construction")
    p_build.add_argument("--metric", default="cosine", choices=["cosine", "euclidean", "l2"])
    p_build.add_argument("--seed", type=int, default=0)
    p_build.add_argument("--verbose", "-v", action="store_true")
    p_build.set_defaults(func=_cmd_build)

    p_query = sub.add_parser("query", help="query a saved index with a single vector")
    p_query.add_argument("index", help="path to a .pkl index from `vecsearch build`")
    p_query.add_argument("query", help="path to a length-dim .npy vector")
    p_query.add_argument("--k", type=int, default=5)
    p_query.add_argument("--ef-search", type=int, default=50, dest="ef_search")
    p_query.set_defaults(func=_cmd_query)

    p_bench = sub.add_parser("benchmark", help="run the HNSW vs brute-force comparison")
    p_bench.add_argument("--sizes", type=_int_list, default=list(DEFAULT_SIZES))
    p_bench.add_argument("--dim", type=int, default=DEFAULT_DIM)
    p_bench.add_argument("--ef-search", type=_int_list, default=list(DEFAULT_EF_SEARCH), dest="ef_search")
    p_bench.add_argument("--queries", type=int, default=100)
    p_bench.add_argument("--m", type=int, default=16)
    p_bench.add_argument("--ef-construction", type=int, default=100, dest="ef_construction")
    p_bench.set_defaults(func=_cmd_benchmark)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
