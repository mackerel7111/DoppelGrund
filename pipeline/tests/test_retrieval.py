"""Cluster-conditioned retrieval (spec 02 task 2.9): regime membership and the global fallback."""

from __future__ import annotations

import numpy as np
import pandas as pd

from doppelgrund.ml.retrieval import MIN_MEMBERS, regime_first, regime_mask, restrict


def table(n_a: int, n_b: int) -> tuple[list[str], pd.DataFrame]:
    h = [f"h{i}" for i in range(n_a + n_b)]
    lab = [0] * n_a + [1] * n_b
    cl = pd.DataFrame(
        {"row_key": [f"earth:{x}" for x in h] + ["moon:0"], "hdb_label": [*lab, 0],
         "gmm_label": [*lab, 0], "gmm_maxprob": [0.9] * (n_a + n_b) + [0.9]}
    )  # fmt: skip
    return h, cl


def test_hdbscan_candidates_are_the_rows_with_the_targets_label() -> None:
    h, cl = table(80, 60)
    mask, none = regime_mask("hdbscan", h, cl, {"hdb": 1, "gmm": 1})
    assert not none and mask.sum() == 60 and not mask[:80].any()


def test_noise_or_a_tiny_regime_falls_back_to_the_global_ranking() -> None:
    h, cl = table(80, MIN_MEMBERS - 1)
    assert regime_mask("hdbscan", h, cl, {"hdb": -1, "gmm": 0}) == (None, True)  # noise
    assert regime_mask("hdbscan", h, cl, {"hdb": 1, "gmm": 1}) == (None, True)  # < MIN_MEMBERS
    S = np.arange(5.0)
    assert restrict(S, None) is S


def test_gmm_needs_probability_at_least_half_and_unknown_rows_are_never_members() -> None:
    h, cl = table(80, 60)
    cl.loc[:9, "gmm_maxprob"] = 0.4  # ten rows of component 0 are not confident
    mask, none = regime_mask("gmm", h + ["masked_hex"], cl, {"hdb": 0, "gmm": 0})
    assert not none and mask.sum() == 70 and not mask[-1]


def test_restrict_makes_outside_rows_ineligible() -> None:
    out = restrict(np.array([5.0, 7.0, 9.0]), np.array([True, False, True]))
    assert out[0] == 5.0 and np.isnan(out[1]) and out[2] == 9.0


def test_regime_first_keeps_the_whole_pool_and_puts_the_regime_ahead() -> None:
    S = np.array([90.0, 80.0, 70.0, np.nan, 60.0])
    mask = np.array([False, False, True, True, True])
    out = regime_first(S, mask)
    assert np.isnan(out[3])  # ineligible stays ineligible
    assert out[2] > out[0] > out[1]  # regime row 70 beats outside rows 90 and 80
    assert out[4] > out[0]  # but ordering inside each group is by S
    assert regime_first(S, None) is S
