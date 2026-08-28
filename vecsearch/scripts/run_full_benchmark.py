"""Run the headline benchmark once, emit the table, the Pareto chart, and JSON.

Kept in the repo so the README's numbers and figure are reproducible:

    python scripts/run_full_benchmark.py
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from vecsearch.benchmark import format_tables, run_benchmark
from vecsearch.visualize import plot_pareto

SIZES = (1_000, 10_000, 50_000)
DIM = 128
EF_SEARCH = (10, 50, 100, 200, 500)
OUT = Path(__file__).resolve().parent.parent / "docs"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    result = run_benchmark(
        sizes=SIZES, dim=DIM, ef_search_values=EF_SEARCH, n_queries=100
    )

    table = format_tables(result)
    print(table)
    (OUT / "benchmark.txt").write_text(table + "\n")

    (OUT / "benchmark.json").write_text(
        json.dumps(
            {
                "dim": result.dim,
                "k": result.k,
                "n_queries": result.n_queries,
                "m": result.m,
                "ef_construction": result.ef_construction,
                "builds": [asdict(b) for b in result.builds],
                "rows": [{**asdict(r), "speedup": r.speedup} for r in result.rows],
            },
            indent=2,
        )
        + "\n"
    )

    chart = plot_pareto(result, OUT / "pareto.png")
    print(f"\nwrote {OUT / 'benchmark.txt'}, {OUT / 'benchmark.json'}, {chart}")


if __name__ == "__main__":
    main()
