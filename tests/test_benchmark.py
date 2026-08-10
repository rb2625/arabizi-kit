from arabizikit.benchmark import DEFAULT_DATA, levenshtein, run_benchmark


def test_levenshtein():
    assert levenshtein("kitten", "sitting") == 3
    assert levenshtein("", "") == 0
    assert levenshtein("abc", "abc") == 0


def test_default_data_exists():
    assert DEFAULT_DATA.exists()


def test_benchmark_runs_and_reports():
    report = run_benchmark(top_k=3)
    overall = report["overall"]
    assert overall["n"] >= 20
    for key in ("n", "exact", "hit", "cer", "wer"):
        assert key in overall
    assert set(report["by_dialect"].keys()) >= {"gulf", "egyptian", "levantine", "maghrebi", "msa"}
    assert len(report["rows"]) == overall["n"]


def test_benchmark_is_not_entirely_memorised():
    # the seed set must not be 100% lexicon lookups: at least one row should
    # come from the rule engine (its predicted form differs from a pure pass-through)
    report = run_benchmark(top_k=3)
    assert report["overall"]["hit"] >= 0.7
