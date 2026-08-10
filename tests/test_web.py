"""The browser bundle must never drift from the data tables.

The test regenerates web/arabizikit.js from src/arabizikit/data and asserts
byte-identical output, then syntax-checks the bundle with Node when available.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "web" / "arabizikit.js"
DEMO = ROOT / "web" / "demo.html"


def test_bundle_regenerates_identically():
    assert BUNDLE.exists() and DEMO.exists(), "run `python scripts/build_web.py` once before testing"
    before = (BUNDLE.read_text(encoding="utf-8"), DEMO.read_text(encoding="utf-8"))
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_web.py")],
        check=True,
        capture_output=True,
    )
    after = (BUNDLE.read_text(encoding="utf-8"), DEMO.read_text(encoding="utf-8"))
    assert after == before, "web bundle/demo is out of date — run scripts/build_web.py"


def test_bundle_contains_engine_and_tables():
    content = BUNDLE.read_text(encoding="utf-8")
    assert "const PHONEMES" in content
    assert "const LEXICON" in content
    assert "ArabiziKit" in content


def test_bundle_syntax_with_node():
    if not shutil.which("node"):
        return
    subprocess.run(["node", "--check", str(BUNDLE)], check=True, capture_output=True)
