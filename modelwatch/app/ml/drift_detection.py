"""Distribution-drift detection, implemented from first principles.

Two complementary tests are used for numeric features:

1. Population Stability Index (PSI)
   ---------------------------------
   PSI measures how much a distribution has *shifted* between a reference
   ("expected") sample and a current ("actual") sample.

   Procedure:
     * Cut the reference sample into 10 bins using its deciles as edges, so
       each reference bin holds ~10% of the reference mass.
     * For each bin i, let  E_i = fraction of reference rows in bin i
                            A_i = fraction of current   rows in bin i
     * PSI = Σ_i (A_i - E_i) * ln(A_i / E_i)

   Each term is the bin's share change multiplied by the log-ratio of shares,
   which is exactly the symmetrised relative-entropy contribution of that bin.
   Adding a term for growth and shrinkage makes PSI symmetric-ish and always
   >= 0. Rule-of-thumb bands (industry standard from credit-risk scorecards):
       PSI < 0.1   -> no significant shift        (severity: stable)
       0.1 <= PSI < 0.2 -> moderate shift, monitor (severity: moderate)
       PSI >= 0.2  -> significant shift, investigate (severity: significant)

2. Kolmogorov-Smirnov two-sample test
   ----------------------------------
   The KS statistic D is the largest vertical gap between the two samples'
   empirical cumulative distribution functions (ECDFs):

       D = sup_x | F_ref(x) - F_cur(x) |

   Under the null hypothesis "both samples are drawn from the same continuous
   distribution", D (scaled by sqrt(n*m/(n+m))) follows the Kolmogorov
   distribution, which gives a p-value. A small p-value (< 0.05) means the gap
   is too large to be sampling noise -> the distributions differ. We delegate
   the exact p-value math to ``scipy.stats.ks_2samp`` but compute D ourselves
   in the docstring's spirit; scipy's implementation is the same sup-gap idea.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

# Default thresholds (overridden by Flask config at call sites).
PSI_STABLE_MAX = 0.1
PSI_MODERATE_MAX = 0.2
KS_P_VALUE_THRESHOLD = 0.05

_EPS = 1e-6  # floor for empty bins so ln() and division stay finite


def _decile_edges(reference: np.ndarray, n_bins: int = 10) -> np.ndarray:
    """Bin edges from the reference sample's quantiles.

    Duplicate edges (common with low-cardinality / spiky data) are collapsed,
    and the outer edges are pushed to +/- inf so out-of-range current values
    still land in the first/last bin.
    """
    quantiles = np.linspace(0.0, 1.0, n_bins + 1)
    edges = np.quantile(reference, quantiles)
    edges = np.unique(edges)
    if edges.size < 2:
        # Degenerate: reference is a single constant value.
        edges = np.array([reference[0] - 0.5, reference[0] + 0.5])
    edges[0] = -np.inf
    edges[-1] = np.inf
    return edges


def calculate_psi(reference: np.ndarray, current: np.ndarray, n_bins: int = 10) -> dict:
    """Population Stability Index between two 1-D numeric samples.

    Returns a dict with the scalar ``psi`` plus the per-bin breakdown, which is
    handy for explaining *where* the mass moved.
    """
    reference = np.asarray(reference, dtype=float)
    reference = reference[~np.isnan(reference)]
    current = np.asarray(current, dtype=float)
    current = current[~np.isnan(current)]

    if reference.size == 0 or current.size == 0:
        return {"psi": 0.0, "bins": [], "note": "empty sample"}

    edges = _decile_edges(reference, n_bins=n_bins)

    ref_counts, _ = np.histogram(reference, bins=edges)
    cur_counts, _ = np.histogram(current, bins=edges)

    expected_pct = ref_counts / ref_counts.sum()
    actual_pct = cur_counts / cur_counts.sum()

    expected_pct = np.clip(expected_pct, _EPS, None)
    actual_pct = np.clip(actual_pct, _EPS, None)

    contributions = (actual_pct - expected_pct) * np.log(actual_pct / expected_pct)
    psi = float(np.sum(contributions))

    bins = []
    for i in range(len(contributions)):
        bins.append(
            {
                "bin": i,
                "range": [
                    None if np.isinf(edges[i]) else float(edges[i]),
                    None if np.isinf(edges[i + 1]) else float(edges[i + 1]),
                ],
                "expected_pct": float(expected_pct[i]),
                "actual_pct": float(actual_pct[i]),
                "contribution": float(contributions[i]),
            }
        )
    return {"psi": psi, "bins": bins}


def ks_test(reference: np.ndarray, current: np.ndarray) -> dict:
    """Two-sample Kolmogorov-Smirnov test.

    ``statistic`` is D = sup_x |F_ref(x) - F_cur(x)|; ``p_value`` is the
    probability of seeing a gap that large if both samples share a distribution.
    """
    reference = np.asarray(reference, dtype=float)
    reference = reference[~np.isnan(reference)]
    current = np.asarray(current, dtype=float)
    current = current[~np.isnan(current)]

    if reference.size < 2 or current.size < 2:
        return {"statistic": 0.0, "p_value": 1.0, "note": "insufficient data"}

    result = stats.ks_2samp(reference, current)
    return {"statistic": float(result.statistic), "p_value": float(result.pvalue)}


def psi_severity(
    psi: float,
    stable_max: float = PSI_STABLE_MAX,
    moderate_max: float = PSI_MODERATE_MAX,
) -> str:
    """Map a PSI value onto a severity band."""
    if psi < stable_max:
        return "stable"
    if psi < moderate_max:
        return "moderate"
    return "significant"


def compare_feature(
    baseline: np.ndarray,
    current: np.ndarray,
    *,
    stable_max: float = PSI_STABLE_MAX,
    moderate_max: float = PSI_MODERATE_MAX,
    ks_p_threshold: float = KS_P_VALUE_THRESHOLD,
) -> dict:
    """Run PSI + KS for one feature and decide whether it has drifted."""
    psi_result = calculate_psi(baseline, current)
    ks_result = ks_test(baseline, current)

    psi_value = psi_result["psi"]
    ks_p = ks_result["p_value"]
    severity = psi_severity(psi_value, stable_max, moderate_max)

    drift_detected = bool(psi_value > moderate_max or ks_p < ks_p_threshold)

    return {
        "psi": psi_value,
        "psi_bins": psi_result.get("bins", []),
        "ks_statistic": ks_result["statistic"],
        "ks_p_value": ks_p,
        "severity": severity,
        "drift_detected": drift_detected,
        # `significant` == the stricter bar the auto-retrain logic keys off.
        "significant": severity == "significant",
        "method": "PSI+KS",
        "baseline_mean": float(np.nanmean(baseline)) if len(baseline) else None,
        "current_mean": float(np.nanmean(current)) if len(current) else None,
        "baseline_std": float(np.nanstd(baseline)) if len(baseline) else None,
        "current_std": float(np.nanstd(current)) if len(current) else None,
    }


def compare_distributions(
    baseline_df: pd.DataFrame,
    current_df: pd.DataFrame,
    features: list[str],
    *,
    stable_max: float = PSI_STABLE_MAX,
    moderate_max: float = PSI_MODERATE_MAX,
    ks_p_threshold: float = KS_P_VALUE_THRESHOLD,
) -> dict:
    """Compare every named feature between baseline and current frames.

    Returns ``{"features": {name: result, ...}, "summary": {...}}`` where each
    ``result`` is the dict from :func:`compare_feature`.
    """
    per_feature: dict[str, dict] = {}
    for feat in features:
        if feat not in baseline_df.columns or feat not in current_df.columns:
            continue
        base = pd.to_numeric(baseline_df[feat], errors="coerce").to_numpy()
        curr = pd.to_numeric(current_df[feat], errors="coerce").to_numpy()
        per_feature[feat] = compare_feature(
            base,
            curr,
            stable_max=stable_max,
            moderate_max=moderate_max,
            ks_p_threshold=ks_p_threshold,
        )

    n_checked = len(per_feature)
    drifted = [f for f, r in per_feature.items() if r["drift_detected"]]
    significant = [f for f, r in per_feature.items() if r["significant"]]

    summary = {
        "n_features_checked": n_checked,
        "n_drifted": len(drifted),
        "n_significant": len(significant),
        "drifted_features": drifted,
        "significant_features": significant,
        "drift_fraction": (len(significant) / n_checked) if n_checked else 0.0,
        "any_drift": bool(drifted),
    }
    return {"features": per_feature, "summary": summary}
