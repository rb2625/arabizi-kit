import json

from arabizikit.corpus.split import split_annotated


def _write_fake_annotated(path, counts):
    rows = []
    n = 0
    for dialect, count in counts.items():
        for i in range(count):
            n += 1
            rows.append(
                {
                    "id": f"x-{n}",
                    "arabizi": f"sample sentence {n}",
                    "arabic": f"جملة {n}",
                    "dialect": dialect,
                    "note": "",
                }
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")


def test_split_is_stratified_and_deterministic(tmp_path):
    annotated = tmp_path / "annotated.jsonl"
    _write_fake_annotated(annotated, {"egyptian": 20, "gulf": 10, "levantine": 10, "maghrebi": 5, "msa": 5})
    out = tmp_path / "splits"

    report = split_annotated(annotated_path=annotated, out_dir=out, seed=7)
    assert report["n"] == 50
    assert sum(report["splits"].values()) == 50
    assert report["splits"]["train"] > report["splits"]["dev"] > 0
    assert report["splits"]["test"] > 0

    # deterministic with the same seed
    report2 = split_annotated(annotated_path=annotated, out_dir=tmp_path / "splits2", seed=7)
    assert report2["splits"] == report["splits"]

    test_entries = json.loads((out / "test.json").read_text(encoding="utf-8"))["entries"]
    assert test_entries
    for entry in test_entries:
        assert set(entry) >= {"id", "arabizi", "reference", "dialect"}
        assert entry["id"].startswith("corp-")
    # every dialect with enough mass must appear in the test split
    dialects_in_test = {e["dialect"] for e in test_entries}
    assert dialects_in_test >= {"egyptian", "gulf", "levantine"}


def test_split_empty(tmp_path):
    annotated = tmp_path / "annotated.jsonl"
    annotated.write_text("", encoding="utf-8")
    report = split_annotated(annotated_path=annotated, out_dir=tmp_path / "splits")
    assert "error" in report
