"""Pareto-frontier plot: recall@k vs. average query latency as ef_search varies.

This is the standard chart in ANN benchmarks -- up-and-to-the-right of the knee
is wasted latency, and each dataset size traces its own frontier. ``matplotlib``
is an optional dependency (``pip install 'vecsearch[viz]'``).
"""

from __future__ import annotations

from pathlib import Path

from .benchmark import BenchmarkResult, run_benchmark


def plot_pareto(result: BenchmarkResult, path: str | Path = "pareto.png") -> Path:
    """Write the recall-vs-latency frontier for ``result`` to ``path``."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    by_size: dict[int, list] = {}
    for row in result.rows:
        by_size.setdefault(row.size, []).append(row)

    fig, ax = plt.subplots(figsize=(7, 5))
    for size, rows in sorted(by_size.items()):
        rows = sorted(rows, key=lambda r: r.recall)
        ax.plot(
            [r.recall for r in rows],
            [r.hnsw_ms for r in rows],
            marker="o",
            label=f"HNSW, N={size:,}",
        )
        for r in rows:
            ax.annotate(
                f"ef={r.ef_search}",
                (r.recall, r.hnsw_ms),
                textcoords="offset points",
                xytext=(6, 4),
                fontsize=8,
            )
        brute_ms = rows[0].brute_ms
        ax.axhline(
            brute_ms,
            linestyle="--",
            linewidth=1,
            alpha=0.6,
            color=ax.lines[-1].get_color(),
        )
        ax.annotate(
            f"brute force, N={size:,}",
            (ax.get_xlim()[0], brute_ms),
            textcoords="offset points",
            xytext=(4, 4),
            fontsize=8,
            alpha=0.8,
        )

    ax.set_xlabel(f"recall@{result.k}")
    ax.set_ylabel("avg query time (ms, log scale)")
    ax.set_yscale("log")
    ax.set_title("HNSW: recall vs. query latency (higher ef_search →)")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend()
    fig.tight_layout()

    path = Path(path)
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Plot the HNSW Pareto frontier")
    parser.add_argument("--output", default="pareto.png")
    parser.add_argument(
        "--sizes",
        type=lambda s: [int(x) for x in s.split(",")],
        default=[1_000, 10_000],
    )
    parser.add_argument("--dim", type=int, default=128)
    args = parser.parse_args(argv)

    result = run_benchmark(sizes=args.sizes, dim=args.dim)
    out = plot_pareto(result, args.output)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
