"""Earth Engine timeout handling: split the batch on a timeout, retry transient errors."""

from __future__ import annotations

import pandas as pd
import pytest

from doppelgrund.real import reduce_with_retry


def frame(hexes: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"v": [float(h) for h in hexes]}, index=pd.Index(hexes, name="h3"))


def test_a_timeout_splits_the_batch_until_the_pieces_fit() -> None:
    calls: list[int] = []

    def fn(hexes: list[str]) -> pd.DataFrame:
        calls.append(len(hexes))
        if len(hexes) > 3:
            raise RuntimeError("Computation timed out.")
        return frame(hexes)

    hexes = [str(i) for i in range(10)]
    out = reduce_with_retry(fn, hexes, sleep=lambda s: None, log=lambda m: None)
    assert out.index.tolist() == hexes and out["v"].tolist() == [float(i) for i in range(10)]
    assert calls[0] == 10 and max(c for c in calls[1:]) <= 5  # first the whole batch, then halves


def test_a_single_hex_that_times_out_is_raised() -> None:
    def fn(hexes: list[str]) -> pd.DataFrame:
        raise RuntimeError("Computation timed out.")

    with pytest.raises(RuntimeError, match="timed out"):
        reduce_with_retry(fn, ["a"], sleep=lambda s: None, log=lambda m: None)


def test_transient_errors_are_retried_with_a_growing_wait_then_succeed() -> None:
    waits: list[float] = []
    state = {"n": 0}

    def fn(hexes: list[str]) -> pd.DataFrame:
        state["n"] += 1
        if state["n"] <= 2:
            raise RuntimeError("Too many concurrent aggregations.")
        return frame(hexes)

    out = reduce_with_retry(fn, ["1", "2"], sleep=waits.append, log=lambda m: None)
    assert out.shape == (2, 1) and waits == [10, 20]


def test_transient_errors_give_up_after_the_last_try_and_other_errors_are_not_retried() -> None:
    def always_busy(hexes: list[str]) -> pd.DataFrame:
        raise RuntimeError("quota exceeded")

    with pytest.raises(RuntimeError, match="quota"):
        reduce_with_retry(always_busy, ["1"], tries=3, sleep=lambda s: None, log=lambda m: None)

    calls: list[int] = []

    def bad(hexes: list[str]) -> pd.DataFrame:
        calls.append(1)
        raise ValueError("a real bug")

    with pytest.raises(ValueError):
        reduce_with_retry(bad, ["1"], sleep=lambda s: None, log=lambda m: None)
    assert len(calls) == 1
