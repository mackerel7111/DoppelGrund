"""Reference scorer and match cards (spec 02 tasks 2.2 and 2.3). Implements contracts C4 and C5.

web/src/engine/{scoring,cards}.ts must agree with this to 1e-5. Computed in float64, returned as
float32.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from doppelgrund.config import EXPECTED_GROUPS, Profiles
from doppelgrund.harmonise import Scaler, apply_transforms

GROUPS: tuple[str, ...] = EXPECTED_GROUPS
COMPOSITION = GROUPS.index("composition")
EARTH_R_KM = 6371.0088
MASKED = 1  # flags bit 0


@dataclass(frozen=True)
class ScoreResult:
    S: np.ndarray  # (N,) float32, 0-100 or NaN
    coverage: np.ndarray  # (N,) float32 in [0, 1]
    groups: np.ndarray  # (N, len(GROUPS)) float32, order GROUPS


def haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Great-circle distance in km (R = 6371.0088), broadcasting."""
    la1, lo1, la2, lo2 = (np.radians(np.asarray(v, np.float64)) for v in (lat1, lon1, lat2, lon2))
    a = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return 2 * EARTH_R_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def _smooth(L: np.ndarray, C: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Rows of ``normalise(L @ C)`` and a validity mask (finite, positive sums)."""
    L = np.atleast_2d(np.asarray(L, np.float64))
    finite = np.isfinite(L).all(axis=1)
    Lz = np.where(np.isfinite(L), L, 0.0)
    ok = finite & (Lz.sum(axis=1) > 0)
    p = Lz @ C
    tot = p.sum(axis=1)
    ok &= tot > 0
    return p / np.where(tot > 0, tot, 1.0)[:, None], ok


def lith_similarity(
    L_e: np.ndarray, l_t: np.ndarray | None, C: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """(k, valid) per Earth row: 1 - Hellinger distance of the C-smoothed vectors (C4.3)."""
    p, ok_e = _smooth(L_e, C)
    if l_t is None:
        return np.full(len(p), np.nan), np.zeros(len(p), bool)
    q, ok_t = _smooth(l_t, C)
    valid = ok_e & bool(ok_t[0])
    bc = np.sqrt(p * q[0]).sum(axis=1)
    k = 1.0 - np.sqrt(np.maximum(0.0, 1.0 - bc))
    return np.where(valid, k, np.nan), valid


def lens_weights(profiles: Profiles, lens: str | dict[str, float]) -> tuple[np.ndarray, float]:
    """``(w_numeric, w_lith)`` by the C3 weight rule; delegates to ``Profiles.feature_weights``."""
    return profiles.feature_weights(lens)


def score(
    X_e: np.ndarray,
    L_e: np.ndarray,
    flags: np.ndarray,
    x_t: np.ndarray,
    l_t: np.ndarray | None,
    scaler: Scaler,
    transforms: Sequence[str],
    groups_of_feature: Sequence[int],
    w_num: np.ndarray,
    w_lith: float,
    C: np.ndarray,
) -> ScoreResult:
    """Score every Earth row against one target (C4.1-C4.6). ``X_e`` is raw, (N, F)."""
    n_groups = len(GROUPS)
    Xe = apply_transforms(X_e, transforms)
    xt = apply_transforms(np.asarray(x_t, np.float64)[None, :], transforms)[0]
    with np.errstate(invalid="ignore"):
        z = np.abs(xt - Xe) / scaler.s  # NaN where either side is missing
    valid = np.isfinite(z)
    k = np.where(valid, np.exp(-0.5 * np.where(valid, z, 0.0) ** 2), 0.0)
    w = np.where(valid, np.asarray(w_num, np.float64), 0.0)
    onehot = np.zeros((len(groups_of_feature), n_groups))
    onehot[np.arange(len(groups_of_feature)), np.asarray(groups_of_feature, int)] = 1.0
    g_num, g_den = (k * w) @ onehot, w @ onehot

    k_lith, lith_ok = lith_similarity(L_e, l_t, C)
    g_num[:, COMPOSITION] += np.where(lith_ok, w_lith * np.nan_to_num(k_lith), 0.0)
    g_den[:, COMPOSITION] += np.where(lith_ok, w_lith, 0.0)

    w_all = float(np.sum(w_num)) + w_lith
    num, den = g_num.sum(axis=1), g_den.sum(axis=1)
    masked = (np.asarray(flags) & MASKED) == MASKED
    has = den > 0
    S = np.where(has & ~masked, 100.0 * num / np.where(has, den, 1.0), np.nan)
    coverage = np.where(has & (w_all > 0), den / (w_all if w_all > 0 else 1.0), 0.0)
    ok_g = (g_den > 0) & ~masked[:, None]
    groups = np.where(ok_g, 100.0 * g_num / np.where(g_den > 0, g_den, 1.0), np.nan)
    return ScoreResult(S.astype(np.float32), coverage.astype(np.float32), groups.astype(np.float32))


def _card(kind: str, row: int, res: ScoreResult, s_g: float) -> dict:
    return {
        "kind": kind,
        "row": row,
        "S": float(res.S[row]),
        "S_g": float(s_g),
        "coverage": float(res.coverage[row]),
    }


def _no_match(kind: str) -> dict:
    return {
        "kind": kind,
        "row": None,
        "S": np.nan,
        "S_g": np.nan,
        "coverage": np.nan,
        "reason": "no_eligible_match",
    }


def select_cards(res: ScoreResult, latlng: np.ndarray, params: dict[str, Any]) -> list[dict]:
    """Best overall + best per group, >= card_min_separation_km apart (C5). 6 cards, fixed order."""
    S = res.S
    eligible = np.isfinite(S) & (res.coverage >= params["coverage_floor"])
    cards: list[dict] = []
    chosen: list[int] = []
    pool = np.zeros(len(S), bool)
    if eligible.any():
        thr = np.percentile(S[eligible].astype(np.float64), params["card_overall_percentile"])
        pool = eligible & (S >= thr)
        best = int(np.argmax(np.where(eligible, S, -np.inf)))  # ties -> lower row index
        chosen.append(best)
        cards.append(_card("overall", best, res, S[best]))
    else:
        cards.append(_no_match("overall"))

    lat, lon = latlng[:, 0], latlng[:, 1]
    for gi, g in enumerate(GROUPS):
        sg = res.groups[:, gi]
        cand = pool & np.isfinite(sg)
        for c in chosen:
            cand &= haversine_km(lat, lon, lat[c], lon[c]) >= params["card_min_separation_km"]
        idx = np.flatnonzero(cand)
        if idx.size == 0:
            cards.append(_no_match(g))
            continue
        pick = int(idx[np.lexsort((idx, -S[idx], -sg[idx]))[0]])  # max S_g, then higher S, then row
        chosen.append(pick)
        cards.append(_card(g, pick, res, sg[pick]))
    return cards
