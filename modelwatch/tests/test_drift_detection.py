"""Tests for the from-scratch PSI and KS drift math."""

import numpy as np
import pandas as pd
import pytest

from app.ml.drift_detection import (
    calculate_psi,
    compare_distributions,
    compare_feature,
    ks_test,
    psi_severity,
)

RNG = np.random.default_rng(42)


# --------------------------------------------------------------------------- PSI

def test_psi_near_zero_for_same_distribution():
    a = RNG.normal(0, 1, 5000)
    b = RNG.normal(0, 1, 5000)
    psi = calculate_psi(a, b)["psi"]
    assert psi < 0.1  # "stable" band


def test_psi_large_for_shifted_mean():
    baseline = RNG.normal(0, 1, 5000)
    shifted = RNG.normal(2.0, 1, 5000)  # +2 sigma mean shift
    psi = calculate_psi(baseline, shifted)["psi"]
    assert psi > 0.2  # "significant" band


def test_psi_grows_monotonically_with_shift():
    baseline = RNG.normal(0, 1, 8000)
    psis = [calculate_psi(baseline, RNG.normal(delta, 1, 8000))["psi"] for delta in (0.0, 0.5, 1.0, 2.0)]
    assert psis == sorted(psis)
    assert psis[0] < psis[-1]


def test_psi_bins_sum_to_psi():
    baseline = RNG.normal(0, 1, 3000)
    current = RNG.normal(0.7, 1.2, 3000)
    result = calculate_psi(baseline, current)
    assert result["psi"] == pytest.approx(sum(b["contribution"] for b in result["bins"]), rel=1e-9)


def test_psi_symmetric_when_swapped_is_still_flagged():
    a = RNG.normal(0, 1, 4000)
    b = RNG.normal(1.5, 1, 4000)
    assert calculate_psi(a, b)["psi"] > 0.2
    assert calculate_psi(b, a)["psi"] > 0.2


def test_psi_handles_empty_and_constant_input():
    assert calculate_psi(np.array([]), np.array([1, 2, 3]))["psi"] == 0.0
    const = np.ones(100)
    # No error, finite result.
    assert np.isfinite(calculate_psi(const, const)["psi"])


# ---------------------------------------------------------------------------- KS

def test_ks_high_pvalue_for_same_distribution():
    a = RNG.normal(0, 1, 2000)
    b = RNG.normal(0, 1, 2000)
    res = ks_test(a, b)
    assert res["p_value"] > 0.05
    assert res["statistic"] < 0.1


def test_ks_low_pvalue_for_shifted_distribution():
    a = RNG.normal(0, 1, 2000)
    b = RNG.normal(1.0, 1, 2000)
    res = ks_test(a, b)
    assert res["p_value"] < 0.05
    assert res["statistic"] > 0.2


def test_ks_detects_variance_change_with_equal_means():
    a = RNG.normal(0, 1, 3000)
    b = RNG.normal(0, 3, 3000)  # same mean, 3x spread
    assert ks_test(a, b)["p_value"] < 0.05


def test_ks_insufficient_data_is_safe():
    res = ks_test(np.array([1.0]), np.array([2.0, 3.0]))
    assert res["p_value"] == 1.0


# ----------------------------------------------------------------- severity + API

@pytest.mark.parametrize(
    "psi,expected",
    [(0.0, "stable"), (0.05, "stable"), (0.1, "moderate"), (0.15, "moderate"),
     (0.2, "significant"), (0.9, "significant")],
)
def test_psi_severity_bands(psi, expected):
    assert psi_severity(psi) == expected


def test_compare_feature_no_drift():
    a = RNG.normal(0, 1, 3000)
    b = RNG.normal(0, 1, 3000)
    res = compare_feature(a, b)
    assert res["drift_detected"] is False
    assert res["severity"] == "stable"


def test_compare_feature_with_drift():
    a = RNG.normal(0, 1, 3000)
    b = RNG.normal(1.5, 1.4, 3000)
    res = compare_feature(a, b)
    assert res["drift_detected"] is True
    assert res["significant"] is True
    assert res["ks_p_value"] < 0.05
    assert res["psi"] > 0.2


def test_compare_distributions_flags_only_drifted_features():
    n = 4000
    baseline = pd.DataFrame(
        {
            "stable_a": RNG.normal(0, 1, n),
            "stable_b": RNG.normal(10, 2, n),
            "drifted": RNG.normal(0, 1, n),
        }
    )
    current = pd.DataFrame(
        {
            "stable_a": RNG.normal(0, 1, n),
            "stable_b": RNG.normal(10, 2, n),
            "drifted": RNG.normal(2.5, 1, n),  # obvious shift
        }
    )
    out = compare_distributions(baseline, current, ["stable_a", "stable_b", "drifted"])
    assert out["summary"]["n_features_checked"] == 3
    assert out["summary"]["drifted_features"] == ["drifted"]
    assert out["features"]["drifted"]["significant"] is True
    assert out["features"]["stable_a"]["drift_detected"] is False
    assert out["features"]["stable_b"]["drift_detected"] is False
    assert out["summary"]["drift_fraction"] == pytest.approx(1 / 3)


def test_compare_distributions_ignores_unknown_features():
    df = pd.DataFrame({"a": RNG.normal(0, 1, 100)})
    out = compare_distributions(df, df, ["a", "does_not_exist"])
    assert out["summary"]["n_features_checked"] == 1
