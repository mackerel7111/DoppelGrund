"""Cross-platform helpers for Kiro hooks (replace POSIX shell one-liners).

Usage: python .kiro/hooks/scripts/portable.py <command> [args]
  status                 print the top of docs/STATUS.md
  lint <path>            run `make -s lint-py|lint-web FILE=<path>` if a Makefile exists
  gate                   run `make -s verify-quick`; exit 2 when red
  nonn <path>            exit 1 if a neural-network dependency appears in the file
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile

from pathlib import Path

NN = re.compile(r"(torch|tensorflow|keras|\bjax\b|onnxruntime|@tensorflow)", re.I)


def status() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = Path("docs/STATUS.md")
    if p.is_file():
        print("\n".join(p.read_text(encoding="utf-8-sig").splitlines()[:80]))
    else:
        print("docs/STATUS.md not found yet (repo not scaffolded).")
    return 0


def lint(path: str) -> int:
    if not Path("Makefile").is_file() or shutil.which("make") is None:
        return 0
    norm = path.replace("\\", "/")
    target = "lint-py" if norm.endswith(".py") else "lint-web" if re.search(r"web/.*\.(ts|vue)$", norm) else None
    if target is None:
        return 0
    return subprocess.run(["make", "-s", target, f"FILE={path}"]).returncode


def gate() -> int:
    if not Path("Makefile").is_file() or shutil.which("make") is None:
        return 0
    r = subprocess.run(["make", "-s", "verify-quick"], capture_output=True, text=True)
    if r.returncode == 0:
        return 0
    log = Path(tempfile.gettempdir()) / "doppelgrund-verify.log"
    log.write_text(r.stdout + r.stderr, encoding="utf-8")
    tail = "\n".join((r.stdout + r.stderr).splitlines()[-40:])
    print("verify-quick is failing; fix it before starting a new task. Last 40 lines:\n" + tail, file=sys.stderr)
    return 2


def nonn(path: str) -> int:
    p = Path(path)
    if p.is_file() and NN.search(p.read_text(encoding="utf-8", errors="ignore")):
        print(f"Forbidden neural-network dependency found in {path}. Remove it (see tech.md hard constraints).", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else ""
    arg = argv[2] if len(argv) > 2 else ""
    return {"status": status, "gate": gate}.get(cmd, lambda: {"lint": lint, "nonn": nonn}[cmd](arg))()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
