"""Ranking stability (spec 02 task 2.13, requirement R10): is a top match robust to the weights?

For one target and one lens, perturb the group weights (Dirichlet around the lens) and the
per-feature tolerances (log-normal), rescore every Earth row, and count how often each hex lands in
the top ``top_fraction`` of eligible rows. A hex at 1.0 stays in the top slice in every draw; 0.0
never does.

Groups the target has no data for (e.g. thermal on Mars) get weight 0 and the rest are renormalised,
as the app does, so the score is judged on what can be compared.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from doppelgrund.config import Profiles
from doppelgrund.harmonise import Scaler
from doppelgrund.scoring import COMPOSITION, GROUPS, score


def available_groups(prof: Profiles, x_t: np.ndarray, l_t: np.ndarray | None) -> tuple[str, ...]:
    """Groups in which the target has at least one measured value."""
    have = {f.group for f, v in zip(prof.features, x_t, strict=True) if np.isfinite(v)}
    if l_t is not None and np.isfinite(l_t).all() and np.nansum(l_t) > 0:
        have.add(GROUPS[COMPOSITION])
    return tuple(g for g in GROUPS if g in have)


def lens_for_target(
    prof: Profiles, lens: str | Mapping[str, float], x_t: np.ndarray, l_t: np.ndarray | None
) -> dict[str, float]:
    """Lens weights with unavailable groups zeroed and the rest renormalised to sum to 1."""
    base = dict(prof.lenses[lens]) if isinstance(lens, str) else dict(lens)
    avail = set(available_groups(prof, x_t, l_t))
    w = {g: (base[g] if g in avail else 0.0) for g in GROUPS}
    tot = sum(w.values())
    if tot <= 0:
        raise ValueError("the lens puts no weight on any group the target has data for")
    return {g: v / tot for g, v in w.items()}


def stability(
    Xe: np.ndarray,
    Le: np.ndarray,
    flags: np.ndarray,
    x_t: np.ndarray,
    l_t: np.ndarray | None,
    scaler: Scaler,
    prof: Profiles,
    weights: Mapping[str, float],
    rng: np.random.Generator,
    draws: int | None = None,
) -> np.ndarray:
    """float32 (N,) in [0, 1]: fraction of draws in which each row is in the top slice."""
    p = prof.params["stability"]
    draws = int(draws if draws is not None else p["draws"])
    conc, sigma, top = (
        float(p["dirichlet_concentration"]),
        float(p["tol_log_sigma"]),
        float(p["top_fraction"]),
    )
    transforms = [f.transform for f in prof.features]
    gof = [GROUPS.index(f.group) for f in prof.features]
    base = np.array([weights[g] for g in GROUPS], float)
    live = base > 0
    count = np.zeros(len(Xe))
    floor = float(prof.params["coverage_floor"])
    for _ in range(draws):
        w = np.zeros(len(GROUPS))
        w[live] = rng.dirichlet(conc * base[live] / base[live].sum())
        s = scaler.s * np.exp(rng.normal(0.0, sigma, len(scaler.s)))
        w_num, w_lith = prof.feature_weights(dict(zip(GROUPS, w, strict=True)))
        r = score(
            Xe,
            Le,
            flags,
            x_t,
            l_t,
            Scaler(scaler.median, s, scaler.counts),
            transforms,
            gof,
            w_num,
            w_lith,
            prof.compat_matrix,
        )
        ok = np.flatnonzero(np.isfinite(r.S) & (r.coverage >= floor))
        if ok.size == 0:
            continue
        k = max(1, int(np.ceil(top * ok.size)))
        best = ok[np.argsort(-r.S[ok], kind="stable")[:k]]
        count[best] += 1
    return (count / max(draws, 1)).astype(np.float32)


def top_rows(frac: np.ndarray, k: int) -> list[tuple[int, float]]:
    """The ``k`` most stable rows as (row, fraction); ties to the lower row, zeros dropped."""
    order = np.lexsort((np.arange(len(frac)), -frac))
    return [(int(i), float(frac[i])) for i in order[:k] if frac[i] > 0]
