"""Smoke test: the package imports and the pinned scientific stack is importable."""

import importlib

import pytest

import doppelgrund


def test_package_version() -> None:
    assert isinstance(doppelgrund.__version__, str)


@pytest.mark.parametrize(
    "module",
    ["numpy", "pandas", "pyarrow", "scipy", "sklearn", "h3", "shapely", "pyproj", "PIL", "yaml"],
)
def test_stack_importable(module: str) -> None:
    importlib.import_module(module)


def test_h3_v4_api() -> None:
    import h3

    cell = h3.latlng_to_cell(0.0, 0.0, 4)
    assert h3.get_resolution(cell) == 4
