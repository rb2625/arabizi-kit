# Release runbook

How to publish arabizikit to PyPI and npm. Requires a PyPI token and an npm
token; both are free and neither grants anyone code access. The trained
model is not shipped, it is built locally with `arabizikit model train`.

## 1. Bump versions

Edit all three in one commit:

- `pyproject.toml` -> `version`
- `src/arabizikit/__init__.py` -> `__version__`
- `web/package.json` -> `version`

Keep PyPI and npm versions in lockstep so the docs stay truthful.

## 2. Verify before shipping

```bash
uv run pytest
uv run ruff check src tests scripts
uv build
# wheel must contain arabizikit/data/lexicon.json and phonemes.json
unzip -l dist/*.whl | grep data/
# smoke the wheel in a clean venv (no repo on the path)
uvx --from dist/*.whl python -c "from arabizikit import transliterate, __version__; print(transliterate('ezayak ya 7abiby')); print(__version__)"
```

Then smoke the npm side from `web/`:

```bash
cd web && npm pack --dry-run
```

## 3. Publish to PyPI

```bash
uv build
uv publish --publish-url https://upload.pypi.org/legacy/
```

or, with twine: `twine upload dist/*`. The first release needs a project
name on PyPI: create an account, add a token with "entire project" scope
(not the default project-scoped token, which only works once the project
exists), then `uv publish` accepts `--token`.

## 4. Publish to npm

```bash
cd web
npm publish
```

First release also needs `npm adduser` once.

## 5. Tag the release

```bash
git tag v1.0.0
git push origin v1.0.0
```

Tags are also picked up by `.github/workflows/release.yml` if you prefer the
CI path (it publishes PyPI on every `v*` tag from the workflow's configured
PyPI token; set `PYPI_TOKEN` as a repository secret).

## 6. Post-release checklist

- [ ] `pip install arabizikit` works in a clean environment
- [ ] `npm install arabizikit` works and `require("arabizikit")` runs
- [ ] Demo (https://arabizi-kit.vercel.app) still loads the released bundle
- [ ] `arabizikit eval --model` reproduces the numbers in the README
