"""Cave/pit density: positive-only, hand-computed counts. No downloads."""

from __future__ import annotations

import h3
import numpy as np
import pytest

from doppelgrund.caves import (
    density,
    disc_density,
    hex_density,
    load_earth_lava_tubes,
    load_lroc_pits,
)
from doppelgrund.config import REPO


def test_density_is_nan_not_zero_without_a_catalogued_feature() -> None:
    d = density(np.array([0, 2]), np.array([1000.0, 1000.0]))
    assert np.isnan(d[0]) and d[1] == pytest.approx(2.0) and d.dtype == np.float32


def test_hex_density_counts_points_in_their_own_hex() -> None:
    a = h3.latlng_to_cell(64.78, -20.73, 4)
    b = h3.latlng_to_cell(-24.0, -69.0, 4)
    out = hex_density(np.array([64.78, 64.7801, 10.0]), np.array([-20.73, -20.7301, 10.0]), [a, b])
    assert out[0] == pytest.approx(2 / h3.cell_area(a, unit="km^2") * 1000, rel=1e-4)
    assert np.isnan(out[1])  # no catalogued feature there: not measured


def test_disc_density_uses_the_great_circle_radius() -> None:
    # on the equator 1 degree of longitude = 30.32 km on the Moon (1737.4 km radius)
    plat, plon = np.array([0.0, 0.0, 0.0]), np.array([0.0, 0.5, 1.0])  # 0, 15.2 and 30.3 km away
    out = disc_density(np.array([0.0, 40.0]), np.array([0.0, 0.0]), plat, plon, 23.7)
    assert out[0] == pytest.approx(
        2 / (np.pi * 23.7**2) * 1000, rel=1e-4
    )  # 0 and 15 km inside, 30 km out
    assert np.isnan(out[1])


def test_loaders_drop_uncertain_pits_and_non_lava_tubes(tmp_path) -> None:
    csv = tmp_path / "pits.csv"
    csv.write_bytes(
        "Type,Latitude,Longitude_180\n,1.0,2.0\nUncertain,3.0,4.0\nFracture,5.0,6.0\n".encode(
            "cp1252"
        )
    )
    lat, lon = load_lroc_pits(csv)
    assert lat.tolist() == [1.0, 5.0] and lon.tolist() == [2.0, 6.0]
    t = tmp_path / "tubes.csv"
    t.write_text("name,type,lat,lon\na,lava_tube,1,2\nb,karst,3,4\n", encoding="utf-8")
    assert load_earth_lava_tubes(t)[0].tolist() == [1.0]


def test_committed_earth_list_is_lava_tubes_only_and_unverified() -> None:
    import pandas as pd

    d = pd.read_csv(REPO / "config/earth_lava_tubes.csv")
    assert set(d["type"]) == {"lava_tube"} and not d["verified"].any()
    assert d["lat"].between(-90, 90).all() and d["lon"].between(-180, 180).all()


def test_landmark_targets_are_computed_at_the_landmark_not_copied_from_a_disc(monkeypatch) -> None:
    import pandas as pd

    from doppelgrund import real
    from doppelgrund.config import EXPECTED_FEATURES
    from doppelgrund.fixtures.synthetic import LITH_COLS

    cols = [*EXPECTED_FEATURES, *LITH_COLS]
    # three landmarks 1 degree (~30 km on the Moon) apart: closer than the disc grid, so a
    # nearest-disc copy would give two of them identical features
    lm = pd.DataFrame(
        {
            "id": ["a", "m", "b"],
            "name": ["A", "M", "B"],
            "body": ["moon", "mars", "moon"],
            "lat": [-88.0, 18.0, -89.0],
            "lon": [10.0, 77.0, 10.0],
            "source": ["x"] * 3,
            "notes": [""] * 3,
        }
    )
    calls = []

    def fake_builder(body):
        def build(lat, lon, ids):  # every feature = the latitude it was evaluated at
            calls.append((body, list(lat), list(lon)))
            return pd.DataFrame({c: np.asarray(lat, np.float32) for c in cols})

        return build

    monkeypatch.setattr(real, "load_landmarks", lambda: lm)
    monkeypatch.setattr(real, "moon_discs_real", fake_builder("moon"))
    monkeypatch.setattr(real, "mars_discs_real", fake_builder("mars"))
    empty = pd.DataFrame({"lat": [0.0], "lon": [0.0], **{c: [np.nan] for c in cols}})
    t = real.targets_real(empty, empty)
    assert list(t["target_id"]) == ["a", "m", "b"]  # landmark order kept across bodies
    assert calls == [("moon", [-88.0, -89.0], [10.0, 10.0]), ("mars", [18.0], [77.0])]
    assert t.set_index("target_id")["slope_p50_deg"].to_dict() == {
        "a": -88.0,
        "m": 18.0,
        "b": -89.0,
    }
