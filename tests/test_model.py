import json

import pytest

from arabizikit import benchmark as bench
from arabizikit.corpus import config as corpus_config
from arabizikit.model import CharacterLM, Model
from arabizikit.transliterate import Transliterator


def _bench_file(path, entries):
    path.write_text(json.dumps({"version": "0.3.0", "entries": entries}, ensure_ascii=False), encoding="utf-8")


def _fixture_model(tmp_path) -> Model:
    src = tmp_path / "train.json"
    _bench_file(
        src,
        [
            {"id": "a1", "arabizi": "ana 3ayz 2akol", "reference": "أنا عايز آكل", "dialect": "egyptian"},
            {"id": "a2", "arabizi": "enta gay feen", "reference": "انت جاي فين", "dialect": "egyptian"},
            {"id": "b1", "arabizi": "shu akhbarak ya 5al", "reference": "شو أخبارك يا خال", "dialect": "levantine"},
            {"id": "b2", "arabizi": "keefak el yom", "reference": "كيفك اليوم", "dialect": "levantine"},
            {"id": "m1", "arabizi": "bach n9ra f had lktab", "reference": "باش نقرا ف هاد الكتاب", "dialect": "maghrebi"},
        ],
    )
    return Model.train([src])


def test_dialect_classifier_trains_and_predicts(tmp_path):
    model = _fixture_model(tmp_path)
    dialect, confidence = model.dialect.predict("ana 3ayz 2akol")
    assert dialect == "egyptian"
    assert confidence > 0.3
    dialect2, _ = model.dialect.predict("shu akhbarak")
    assert dialect2 == "levantine"


def test_hint_for_effective_only(tmp_path):
    model = _fixture_model(tmp_path)
    # Maghrebi flips the engine's digit and doubling conventions, so the
    # classifier emits it as a hint.
    assert model.hint_for("bach n9ra f had lktab") == "maghrebi"
    # Egyptian and Levantine match the engine defaults: no hint needed.
    assert model.hint_for("ana 3ayz 2akol") is None
    assert model.hint_for("shu akhbarak ya 5al") is None
    # No strong signal: no confident hint (avoid guessing wrong conventions).
    assert model.hint_for("zzzz qqqq") is None


def test_word_table_readings_ranked_by_frequency(tmp_path):
    model = _fixture_model(tmp_path)
    readings = model.words.readings("ana")
    assert readings is not None
    assert readings[0][0] == "أنا"
    assert readings[0][1] == 0.0
    assert model.words.readings("zzzznotaword") is None


def test_lm_penalty_prefers_seen_text():
    lm = CharacterLM()
    lm.train_texts(["أنا عايز آكل", "انت جاي فين", "شو أخبارك يا خال"])
    seen = lm.penalty("أنا عايز آكل")
    unseen = lm.penalty("قفقططقزئءءؤؤ")
    assert seen < unseen


def test_save_load_roundtrip(tmp_path):
    model = _fixture_model(tmp_path)
    path = tmp_path / "model.json"
    model.save(path)
    loaded = Model.load(path)
    assert loaded.words.words == model.words.words
    assert loaded.lm.vocab == model.lm.vocab
    assert loaded.dialect.classes == model.dialect.classes
    assert loaded.rerank_lambda == model.rerank_lambda


def test_transliterate_uses_learned_readings(tmp_path):
    model = _fixture_model(tmp_path)
    tr = Transliterator(model=model)
    res = tr.transliterate("ana 3ayz 2akol", top_k=3)
    rendered = {ar for ar, _ in res.candidates}
    assert "أنا عايز آكل" in rendered


def test_benchmark_model_mode(tmp_path, monkeypatch):
    model = _fixture_model(tmp_path)
    model_path = tmp_path / "model.json"
    model.save(model_path)
    monkeypatch.setattr(corpus_config, "MODEL_PATH", model_path)

    data = tmp_path / "test.json"
    _bench_file(
        data,
        [
            {"id": "t1", "arabizi": "ana 3ayz 2akol", "reference": "أنا عايز آكل", "dialect": "egyptian"},
            {"id": "t2", "arabizi": "shu akhbarak ya 5al", "reference": "شو أخبارك يا خال", "dialect": "levantine"},
        ],
    )
    report = bench.run_benchmark(data_path=data, use_model=True)
    assert report["mode"] == "rules+model"
    assert set(report["overall"]) == {"n", "exact", "hit", "cer", "wer"}
    assert report["overall"]["n"] == 2


def test_benchmark_model_mode_requires_trained_model(tmp_path, monkeypatch):
    monkeypatch.setattr(corpus_config, "MODEL_PATH", tmp_path / "missing.json")
    with pytest.raises(FileNotFoundError):
        bench.run_benchmark(data_path=None, use_model=True)
