"""Load and validate DoppelGrund configuration files (contract C3 and the config/ schemas).

All weights, thresholds and dataset IDs are read from ``config/``; code never hardcodes them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import yaml

logger = logging.getLogger(__name__)

REPO: Path = Path(__file__).resolve().parents[2]

# Hardcoded copy of C1 used only for validation.
EXPECTED_FEATURES: tuple[str, ...] = (
    "slope_p50_deg",
    "slope_p90_deg",
    "relief_std_m",
    "frac_slope_lt_10deg",
    "lst_mean_K",
    "diurnal_range_K",
    "annual_range_K",
    "frac_below_0C",
    "permafrost_prob",
    "aridity_index",
)
EXPECTED_GROUPS: tuple[str, ...] = ("terrain", "thermal", "cold_ice", "composition")
EXPECTED_LITH: tuple[str, ...] = (
    "mafic_volcanic",
    "felsic_feldspathic",
    "carbonate",
    "siliciclastic",
    "evaporite",
    "ice",
)
REQUIRED_PARAMS: tuple[str, ...] = (
    "seed",
    "footprint_radius_km",
    "land_frac_min",
    "coverage_floor",
    "card_overall_percentile",
    "card_min_separation_km",
    "novelty_gate_km",
    "mask",
    "stability",
)
DATASET_FIELDS: tuple[str, ...] = (
    "id_or_url",
    "version",
    "licence",
    "citation",
    "access",
    "verified",
)
LANDMARK_COLUMNS: tuple[str, ...] = ("id", "name", "body", "lat", "lon", "source", "notes")
KNOWN_SITE_COLUMNS: tuple[str, ...] = (
    "site_id",
    "name",
    "lat",
    "lon",
    "target_body",
    "documented_target_id",
    "dimension",
    "reference_url",
    "well_known",
)
CROSSWALK_COLUMNS: tuple[str, ...] = ("source", "unit_code", "unit_name", *EXPECTED_LITH, "notes")


class ConfigError(ValueError):
    """Raised when a config file does not match its contract; the message names the field."""


@dataclass(frozen=True)
class Feature:
    name: str
    group: str
    unit: str
    transform: Literal["none", "log1p"]


@dataclass(frozen=True)
class Profiles:
    version: int
    features: tuple[Feature, ...]
    lith_classes: tuple[str, ...]
    compat_matrix: np.ndarray  # (6, 6) float64
    groups: tuple[str, ...]
    lenses: dict[str, dict[str, float]]
    params: dict[str, Any]
    assumptions: tuple[str, ...]

    def feature_weights(self, lens: str | dict[str, float]) -> tuple[np.ndarray, float]:
        """Return ``(w_numeric[10], w_lith)`` using the C3 weight rule ``w_f = W_g / n_g``.

        Parameters
        ----------
        lens
            A lens id from ``profiles.lenses`` or a mapping ``group -> weight``.

        Returns
        -------
        w_numeric
            float64 array of length 10, one weight per C1 numeric feature (dimensionless).
        w_lith
            Weight of the single lithology feature in group ``composition``.
        """
        if isinstance(lens, str):
            if lens not in self.lenses:
                raise ConfigError(f"lenses: unknown lens '{lens}'")
            weights = self.lenses[lens]
        else:
            weights = _validate_lens("custom", lens)
        n_group = {g: 0 for g in self.groups}
        for f in self.features:
            n_group[f.group] += 1
        n_group["composition"] += 1  # the lithology vector counts as one feature
        w_num = np.array(
            [weights[f.group] / n_group[f.group] for f in self.features], dtype=np.float64
        )
        w_lith = float(weights["composition"]) / n_group["composition"]
        return w_num, w_lith


def _read_yaml(path: Path) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except FileNotFoundError as exc:
        raise ConfigError(f"{path}: file not found") from exc


def _validate_lens(name: str, lens: Any) -> dict[str, float]:
    if not isinstance(lens, dict):
        raise ConfigError(f"lenses.{name}: must be a mapping of group -> weight")
    missing = [g for g in EXPECTED_GROUPS if g not in lens]
    extra = [g for g in lens if g not in EXPECTED_GROUPS]
    if missing:
        raise ConfigError(f"lenses.{name}: missing group(s) {missing}")
    if extra:
        raise ConfigError(f"lenses.{name}: unknown group(s) {extra}")
    out = {g: float(lens[g]) for g in EXPECTED_GROUPS}
    if any(v < 0 or not np.isfinite(v) for v in out.values()):
        raise ConfigError(f"lenses.{name}: weights must be finite and non-negative")
    total = sum(out.values())
    if abs(total - 1.0) > 1e-6:
        raise ConfigError(f"lenses.{name}: weights sum to {total}, expected 1.0 ± 1e-6")
    return out


def _validate_features(raw: Any) -> tuple[Feature, ...]:
    if not isinstance(raw, list):
        raise ConfigError("features: must be a list")
    names = tuple(str(f.get("name")) if isinstance(f, dict) else "" for f in raw)
    if names != EXPECTED_FEATURES:
        raise ConfigError(f"features: names/order {list(names)} differ from C1 {EXPECTED_FEATURES}")
    out: list[Feature] = []
    for i, f in enumerate(raw):
        group, unit, transform = f.get("group"), f.get("unit"), f.get("transform")
        if group not in EXPECTED_GROUPS[:3]:
            raise ConfigError(f"features[{i}].group: '{group}' is not a numeric group")
        if transform not in ("none", "log1p"):
            raise ConfigError(f"features[{i}].transform: '{transform}' not in (none, log1p)")
        if not isinstance(unit, str) or not unit:
            raise ConfigError(f"features[{i}].unit: missing")
        out.append(Feature(name=f["name"], group=group, unit=unit, transform=transform))
    return tuple(out)


def _validate_matrix(raw: Any, n: int) -> np.ndarray:
    try:
        m = np.asarray(raw, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ConfigError("compat_matrix: not a numeric matrix") from exc
    if m.shape != (n, n):
        raise ConfigError(f"compat_matrix: shape {m.shape}, expected ({n}, {n})")
    if not np.allclose(m, m.T, atol=1e-12):
        raise ConfigError("compat_matrix: not symmetric")
    if not np.allclose(np.diag(m), 1.0):
        raise ConfigError("compat_matrix: diagonal must be 1.0")
    if np.any(m < 0) or np.any(m > 1):
        raise ConfigError("compat_matrix: values must be in [0, 1]")
    return m


def load_profiles(path: Path = REPO / "config/profiles.yaml") -> Profiles:
    """Load ``config/profiles.yaml`` and validate it against contracts C1 and C3."""
    raw = _read_yaml(Path(path))
    if not isinstance(raw, dict):
        raise ConfigError("profiles: top level must be a mapping")
    for key in ("version", "features", "lith_classes", "compat_matrix", "groups", "lenses"):
        if key not in raw:
            raise ConfigError(f"{key}: missing")
    features = _validate_features(raw["features"])
    lith = tuple(raw["lith_classes"] or ())
    if lith != EXPECTED_LITH:
        raise ConfigError(f"lith_classes: {list(lith)} differ from C1 {EXPECTED_LITH}")
    groups = tuple(raw["groups"] or ())
    if groups != EXPECTED_GROUPS:
        raise ConfigError(f"groups: {list(groups)} differ from {EXPECTED_GROUPS}")
    if not isinstance(raw["lenses"], dict) or not raw["lenses"]:
        raise ConfigError("lenses: must be a non-empty mapping")
    lenses = {str(k): _validate_lens(str(k), v) for k, v in raw["lenses"].items()}
    params = raw.get("params")
    if not isinstance(params, dict):
        raise ConfigError("params: missing or not a mapping")
    for key in REQUIRED_PARAMS:
        if key not in params:
            raise ConfigError(f"params.{key}: missing")
    return Profiles(
        version=int(raw["version"]),
        features=features,
        lith_classes=lith,
        compat_matrix=_validate_matrix(raw["compat_matrix"], len(lith)),
        groups=groups,
        lenses=lenses,
        params=params,
        assumptions=tuple(str(a) for a in raw.get("assumptions") or ()),
    )


def load_datasets(path: Path = REPO / "config/datasets.yaml") -> dict[str, dict]:
    """Load ``config/datasets.yaml``; every entry must carry the documented fields."""
    raw = _read_yaml(Path(path)) or {}
    if not isinstance(raw, dict):
        raise ConfigError("datasets: top level must be a mapping")
    for key, entry in raw.items():
        if not isinstance(entry, dict):
            raise ConfigError(f"datasets.{key}: must be a mapping")
        if not isinstance(entry.get("verified"), bool):
            raise ConfigError(f"datasets.{key}.verified: must be true or false")
        if key == "textures":
            continue
        for field in DATASET_FIELDS:
            if field not in entry:
                raise ConfigError(f"datasets.{key}.{field}: missing")
        if entry["access"] not in ("ee", "download"):
            raise ConfigError(f"datasets.{key}.access: '{entry['access']}' not in (ee, download)")
    return raw


def require_dataset(key: str, path: Path = REPO / "config/datasets.yaml") -> dict:
    """Return one dataset entry; log a warning naming it if ``verified`` is false."""
    datasets = load_datasets(path)
    if key not in datasets:
        raise ConfigError(f"datasets.{key}: not defined")
    entry = datasets[key]
    if not entry["verified"]:
        logger.warning("dataset '%s' is not verified (verified: false in datasets.yaml)", key)
    return entry


def _check_columns(df: pd.DataFrame, expected: tuple[str, ...], name: str) -> pd.DataFrame:
    cols = tuple(df.columns)
    if cols != expected:
        raise ConfigError(f"{name}: columns {list(cols)} differ from {list(expected)}")
    return df


def load_landmarks(path: Path = REPO / "config/landmarks.yaml") -> pd.DataFrame:
    """Load landmarks as a DataFrame with columns id, name, body, lat, lon, source, notes."""
    raw = _read_yaml(Path(path)) or {}
    entries = raw.get("landmarks", []) if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        raise ConfigError("landmarks: must be a list")
    for i, e in enumerate(entries):
        for col in LANDMARK_COLUMNS[:-1]:
            if not isinstance(e, dict) or col not in e:
                raise ConfigError(f"landmarks[{i}].{col}: missing")
        if e["body"] not in ("moon", "mars"):
            raise ConfigError(f"landmarks[{i}].body: '{e['body']}' not in (moon, mars)")
    df = pd.DataFrame(entries, columns=list(LANDMARK_COLUMNS))
    return df.astype({"lat": "float64", "lon": "float64"})


def load_known_sites(path: Path = REPO / "config/known_sites.csv") -> pd.DataFrame:
    """Load documented analogue sites (header per foundation design §2)."""
    return _check_columns(pd.read_csv(path), KNOWN_SITE_COLUMNS, "known_sites.csv")


def load_crosswalk(path: Path = REPO / "config/ontology_crosswalk.csv") -> pd.DataFrame:
    """Load the lithology crosswalk; each row's class weights sum to 1 or are all 0 (unmapped)."""
    df = _check_columns(pd.read_csv(path), CROSSWALK_COLUMNS, "ontology_crosswalk.csv")
    if len(df):
        sums = df[list(EXPECTED_LITH)].astype("float64").sum(axis=1).to_numpy()
        bad = ~(np.isclose(sums, 1.0, atol=1e-6) | np.isclose(sums, 0.0))
        if bad.any():
            raise ConfigError(f"ontology_crosswalk.csv: rows {np.flatnonzero(bad).tolist()} sum")
    return df
