from arabizikit.corpus.filter import arabizi_score, clean_sentence, is_arabizi, sentences


def test_arabizi_score():
    assert arabizi_score("ana 3ayz 2akol") >= 4
    assert arabizi_score("shlonak ya 5al") >= 2
    assert arabizi_score("I love this weather") == 0


def test_is_arabizi():
    assert is_arabizi("ana 3ayz 2akol")
    assert is_arabizi("shlonak ya 5al")
    assert not is_arabizi("The quick brown fox jumps over the lazy dog")
    assert not is_arabizi("مرحبا كيف حالك")  # pure Arabic script
    assert not is_arabizi("hello")  # single word, no markers


def test_clean_sentence_strips_noise():
    cleaned = clean_sentence("check https://t.co/abc123 now 3ashan 7alek")
    assert "http" not in cleaned
    cleaned = clean_sentence("el 7ay #dubai 7elw")
    assert "#dubai" not in cleaned


def test_sentences_split():
    result = sentences("ana 3ayz 2akol. shlonak ya 5al")
    assert len(result) == 2


def test_english_rejected():
    assert sentences("I went to the mall and bought some things") == []


def test_url_only_rejected():
    assert sentences("check this out https://example.com/xyz") == []
