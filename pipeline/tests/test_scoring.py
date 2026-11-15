"""Reference scorer (C4) and match cards (C5): hand-computed cases, properties, speed."""

from __future__ import annotations

import time

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from doppelgrund.config import load_profiles
from doppelgrund.harmonise import Scaler
from doppelgrund.scoring import (
    GROUPS,
    ScoreResult,
    haversine_km,
    lith_similarity,
    score,
    select_cards,
)

PROF = load_profiles()
FEATS = PROF.features
F = len(FEATS)
TRANSFORMS = [f.transform for f in FEATS]
GOF = [GROUPS.index(f.group) for f in FEATS]
C = PROF.compat_matrix
SCALER = Scaler(np.zeros(F), np.full(F, 2.0), {"earth": 0, "moon": 0, "mars": 0})
W_NUM, W_LITH = PROF.feature_weights("balanced")


def run(X_e, L_e, flags, x_t, l_t, w_num=W_NUM, w_lith=W_LITH, scaler=SCALER) -> ScoreResult:
    return score(X_e, L_e, flags, x_t, l_t, scaler, TRANSFORMS, GOF, w_num, w_lith, C)


def rows(n: int, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    return rng.uniform(0, 5, (n, F)), rng.dirichlet(np.ones(6), n)


def test_one_feature_by_hand() -> None:
    # only feature 0 (terrain) is weighted; z = |3 - 1| / 2 = 1 -> k = exp(-0.5) -> S = 100 * k
    w = np.zeros(F)
    w[0] = 1.0
    X_e = np.full((1, F), np.nan)
    X_e[0, 0] = 1.0
    x_t = np.full(F, np.nan)
    x_t[0] = 3.0
    r = run(X_e, np.full((1, 6), np.nan), np.zeros(1, np.uint8), x_t, None, w, 0.0)
    assert r.S[0] == pytest.approx(100 * np.exp(-0.5), rel=1e-6)
    assert r.coverage[0] == pytest.approx(1.0)  # all the weight (just feature 0) is valid
    assert r.groups[0, GROUPS.index("terrain")] == pytest.approx(r.S[0])
    assert np.isnan(r.groups[0, GROUPS.index("thermal")])  # group with no valid feature


def test_coverage_is_valid_weight_over_total_weight() -> None:
    X_e, L_e = rows(1)
    X_e[0, 4:] = np.nan  # drop everything but the four terrain features and the first thermal one
    r = run(X_e, L_e, np.zeros(1, np.uint8), X_e[0] * 0 + 1.0, L_e[0])
    valid_w = (
        W_NUM[:4].sum() + W_NUM[4] * 0 + W_LITH
    )  # terrain x4 + lithology; feature 4 is NaN here too
    assert r.coverage[0] == pytest.approx(valid_w / (W_NUM.sum() + W_LITH))


def test_lithology_hellinger_by_hand() -> None:
    I6 = np.eye(6)  # no smoothing
    same, valid = lith_similarity(
        np.array([[0.5, 0.5, 0, 0, 0, 0]]), np.array([0.5, 0.5, 0, 0, 0, 0]), I6
    )
    assert valid[0] and same[0] == pytest.approx(1.0)
    k, _ = lith_similarity(np.array([[1.0, 0, 0, 0, 0, 0]]), np.array([0, 1.0, 0, 0, 0, 0]), I6)
    assert k[0] == pytest.approx(0.0)  # disjoint: bc 0 -> 1 - sqrt(1)
    k, _ = lith_similarity(np.array([[0.5, 0.5, 0, 0, 0, 0]]), np.array([1.0, 0, 0, 0, 0, 0]), I6)
    assert k[0] == pytest.approx(1 - np.sqrt(1 - np.sqrt(0.5)))
    _, ok = lith_similarity(
        np.array([[np.nan, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]]), np.array([1.0, 0, 0, 0, 0, 0]), I6
    )
    assert not ok.any()  # NaN or zero-sum rows are invalid
    _, ok = lith_similarity(np.array([[1.0, 0, 0, 0, 0, 0]]), None, I6)
    assert not ok.any()  # unmapped target


def test_masked_rows_have_no_score_but_still_a_coverage() -> None:
    X_e, L_e = rows(2)
    r = run(X_e, L_e, np.array([1, 0], np.uint8), X_e[1], L_e[1])
    assert np.isnan(r.S[0]) and np.isnan(r.groups[0]).all() and r.coverage[0] > 0
    assert r.S[1] == pytest.approx(100.0)


def test_row_with_no_valid_weight_is_nan_with_zero_coverage() -> None:
    X_e = np.full((1, F), np.nan)
    r = run(X_e, np.full((1, 6), np.nan), np.zeros(1, np.uint8), np.ones(F), np.ones(6) / 6)
    assert np.isnan(r.S[0]) and r.coverage[0] == 0.0


@settings(max_examples=200, deadline=None)
@given(seed=st.integers(0, 2**32 - 1), nan_frac=st.floats(0, 0.8))
def test_score_properties(seed: int, nan_frac: float) -> None:
    rng = np.random.default_rng(seed)
    X_e, L_e = rows(40, seed)
    X_e[rng.random(X_e.shape) < nan_frac] = np.nan
    x_t = rng.uniform(0, 5, F)
    x_t[rng.random(F) < nan_frac] = np.nan
    flags = rng.integers(0, 2, 40).astype(np.uint8)
    r = run(X_e, L_e, flags, x_t, rng.dirichlet(np.ones(6)))
    fin = np.isfinite(r.S)
    assert ((r.S[fin] >= 0) & (r.S[fin] <= 100 + 1e-4)).all()
    assert ((r.coverage >= 0) & (r.coverage <= 1 + 1e-6)).all()
    assert not fin[(flags & 1) == 1].any()  # masked rows never score
    # a row identical to the target (and unmasked) scores 100 with coverage 1 when nothing is NaN
    full = np.vstack([rng.uniform(0, 5, F)])
    lith = rng.dirichlet(np.ones(6))
    r2 = run(full, lith[None], np.zeros(1, np.uint8), full[0], lith)
    assert r2.S[0] == pytest.approx(100.0, abs=1e-4) and r2.coverage[0] == pytest.approx(1.0)


@settings(max_examples=200, deadline=None)
@given(seed=st.integers(0, 2**32 - 1))
def test_zero_weight_groups_never_change_s(seed: int) -> None:
    rng = np.random.default_rng(seed)
    X_e, L_e = rows(30, seed)
    x_t, l_t = rng.uniform(0, 5, F), rng.dirichlet(np.ones(6))
    w_num, w_lith = PROF.feature_weights(
        {"terrain": 0.5, "thermal": 0.0, "cold_ice": 0.5, "composition": 0.0, "subsurface": 0.0}
    )
    base = run(X_e, L_e, np.zeros(30, np.uint8), x_t, l_t, w_num, w_lith)
    X2 = X_e.copy()
    for j, f in enumerate(FEATS):
        if f.group in ("thermal", "subsurface"):
            X2[:, j] = rng.uniform(0, 5, 30)  # change only zero-weight groups
    again = run(X2, rng.dirichlet(np.ones(6), 30), np.zeros(30, np.uint8), x_t, l_t, w_num, w_lith)
    np.testing.assert_allclose(base.S, again.S, rtol=1e-6)
    assert np.isnan(base.groups[:, GROUPS.index("thermal")]).all()  # W_g == 0 -> NaN group score


def test_85k_rows_score_in_under_a_second() -> None:
    X_e, L_e = rows(85_000)
    X_e[np.random.default_rng(1).random(X_e.shape) < 0.1] = np.nan
    flags = np.zeros(85_000, np.uint8)
    t0 = time.perf_counter()
    run(X_e, L_e, flags, X_e[0], L_e[0])
    dt = time.perf_counter() - t0
    print(f"score 85k rows: {dt:.3f} s")
    assert dt < 1.0


# ---- match cards (C5) ------------------------------------------------------------------------
PARAMS = {"coverage_floor": 0.6, "card_overall_percentile": 50, "card_min_separation_km": 300}


def make_res(S, groups=None, cov=None) -> ScoreResult:
    S = np.asarray(S, np.float32)
    g = (
        np.full((len(S), len(GROUPS)), np.nan, np.float32)
        if groups is None
        else np.asarray(groups, np.float32)
    )
    return ScoreResult(
        S, np.ones(len(S), np.float32) if cov is None else np.asarray(cov, np.float32), g
    )


def test_haversine_one_degree_of_latitude() -> None:
    assert haversine_km(0, 0, 1, 0) == pytest.approx(111.195, abs=1e-2)
    assert haversine_km(10, 20, 10, 20) == 0.0


def test_overall_picks_the_max_with_ties_to_the_lower_row_and_skips_ineligible() -> None:
    res = make_res(
        [50, 90, 90, np.nan, 99], cov=[1, 1, 1, 1, 0.3]
    )  # row 4: below the coverage floor
    cards = select_cards(
        res, np.array([[0, 0], [0, 40], [0, 80], [0, 120], [0, 160]], float), PARAMS
    )
    assert cards[0]["kind"] == "overall" and cards[0]["row"] == 1
    assert [c["kind"] for c in cards] == ["overall", *GROUPS] and len(cards) == 6


def test_group_card_respects_separation_percentile_and_tie_breaks() -> None:
    # rows 0..3; percentile 50 of [60,70,80,90] = 75 -> pool {2, 3}. Row 3 is the overall card.
    S = [60, 70, 80, 90]
    g = np.full((4, len(GROUPS)), np.nan)
    terrain, thermal = GROUPS.index("terrain"), GROUPS.index("thermal")
    g[:, terrain] = [99, 99, 50, 40]  # rows 0,1 are better but fall outside the pool
    g[:, thermal] = [0, 0, 70, 70]  # tie between rows 2 and 3
    latlng = np.array([[0, 0], [0, 1], [0, 2], [0, 3]], float)  # all within 300 km of each other
    cards = select_cards(make_res(S, g), latlng, PARAMS)
    assert cards[0]["row"] == 3
    assert (
        cards[1]["reason"] == "no_eligible_match"
    )  # terrain: only row 2 is left but it is < 300 km from row 3
    far = np.array([[0, 0], [0, 1], [0, 20], [0, 40]], float)  # 20 deg of longitude ~ 2,200 km
    cards = select_cards(make_res(S, g), far, PARAMS)
    assert cards[1]["row"] == 2  # terrain: best in-pool row far enough away
    assert (
        cards[2]["reason"] == "no_eligible_match"
    )  # thermal: row 2 was taken, row 3 is the overall card


def test_ties_prefer_higher_overall_score_then_lower_row() -> None:
    S = [80, 85, 90]
    g = np.full((3, len(GROUPS)), np.nan)
    g[:, GROUPS.index("terrain")] = [70, 70, 70]
    latlng = np.array([[0, 0], [0, 30], [0, 60]], float)
    cards = select_cards(make_res(S, g), latlng, {**PARAMS, "card_overall_percentile": 0})
    assert (
        cards[0]["row"] == 2 and cards[1]["row"] == 1
    )  # equal S_g: higher S wins (row 1 over row 0)


def test_no_eligible_rows_gives_six_empty_cards() -> None:
    cards = select_cards(make_res([np.nan, 40.0], cov=[1, 0.1]), np.zeros((2, 2)), PARAMS)
    assert len(cards) == 6 and all(
        c["row"] is None and c["reason"] == "no_eligible_match" for c in cards
    )


def test_masked_rows_are_never_chosen() -> None:
    X_e, L_e = rows(20)
    flags = np.zeros(20, np.uint8)
    flags[:10] = 1
    r = run(X_e, L_e, flags, X_e[0], L_e[0])  # row 0 matches the target perfectly but is masked
    latlng = np.column_stack([np.linspace(-60, 60, 20), np.linspace(-170, 170, 20)])
    cards = select_cards(r, latlng, {**PARAMS, "coverage_floor": 0.0})
    assert all(c["row"] is None or c["row"] >= 10 for c in cards)
