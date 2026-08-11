"""The browser bundle must never drift from the data tables.

The test regenerates web/arabizikit.js from src/arabizikit/data and asserts
byte-identical output, then syntax-checks the bundle with Node when available
and verifies it works as an npm package (CommonJS require).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "web" / "arabizikit.js"
DEMO = ROOT / "web" / "demo.html"
PKG = ROOT / "web" / "package.json"


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


def test_npm_manifest():
    pkg = json.loads(PKG.read_text(encoding="utf-8"))
    assert pkg["name"] == "arabizikit"
    assert pkg["main"] == "arabizikit.js"
    assert pkg["types"] == "index.d.ts"
    assert "arabizikit.js" in pkg["files"]


def test_bundle_commonjs_export():
    content = BUNDLE.read_text(encoding="utf-8")
    assert "module.exports = global.ArabiziKit" in content


def test_npm_require_transliterates():
    if not shutil.which("node"):
        return
    script = (
        "const k = require(process.argv[1]);"
        "const r = k.transliterate('ana 3ayz 2akol', { withDialect: true });"
        "if (r.text !== 'أنا عايز آكل') process.exit(1);"
        "if (r.dialect.dialect !== 'egyptian') process.exit(2);"
    )
    subprocess.run(["node", "-e", script, str(BUNDLE)], check=True, capture_output=True)
