"""Write data/interim/doppelgrund_colab.zip: pipeline/, config/ and notebooks/*.ipynb, for the Colab notebooks.

Upload the zip to MyDrive/DoppelGrund/ (the notebooks unzip it to /content/DoppelGrund). Run: python notebooks/make_colab_zip.py
The zip goes under data/ because that folder is gitignored (a top-level dist/ is not).
"""
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data/interim/doppelgrund_colab.zip"
SKIP = {"__pycache__", ".venv", ".pytest_cache", ".ruff_cache", "tests", "textures"}  # textures: only the web bundle needs them

files = [p for top in ("pipeline", "config") for p in sorted((REPO / top).rglob("*"))
         if p.is_file() and not (SKIP & set(p.relative_to(REPO).parts)) and not any(s.endswith(".egg-info") for s in p.relative_to(REPO).parts)]
files += sorted((REPO / "notebooks").glob("*.ipynb"))
OUT.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
    for p in files:
        zf.write(p, p.relative_to(REPO).as_posix())
print(f"{OUT}: {len(files)} files, {OUT.stat().st_size / 1e3:.0f} kB")
