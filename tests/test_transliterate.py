import pytest

from arabizikit import transliterate
from arabizikit.transliterate import Transliterator


def test_lexicon_priority():
    assert transliterate("ana").text == "أنا"
    assert transliterate("shukran").text == "شكرا"


def test_digraph_th():
    assert transliterate("hatha").text == "هذا"


def test_short_vowel_elision():
    # e and o are elided as primaries: 3emlo -> عملو (he did it)
    assert transliterate("3emlo").text == "عملو"


def test_hamza_seating_after_waaw():
    # su2al -> سؤال (the 2 seats on the waaw as ؤ)
    assert transliterate("su2al").text == "سؤال"


def test_final_2_is_qaf_after_vowel():
    assert transliterate("tare2").text == "طريق"
    assert transliterate("fo2").text == "فوق"


def test_article_attachment():
    assert transliterate("el 7ayat").text == "الحياة"
    assert transliterate("el yom").text == "اليوم"


def test_conjunction_attachment():
    assert transliterate("w ana").text == "وأنا"


def test_contraction_attachment():
    assert transliterate("3al 7ay").text == "على الحي"


def test_taa_marbuta_default():
    # word-final a defaults to taa marbuta: saa3a -> ساعة
    assert transliterate("saa3a").text == "ساعة"


def test_hamza_seating_merge_sa2al():
    # ا + ء + ا collapses to أ: sa2al -> سأل
    assert transliterate("sa2al").text == "سأل"


def test_hamza_seating_shay2():
    assert transliterate("shay2").text == "شيء"


def test_ay_split_primary():
    # raye7 -> رايح via the alif+ya split (rule-based, not lexicon)
    assert transliterate("raye7").text == "رايح"


def test_ay_word_in_lexicon():
    assert transliterate("dayman").text == "دايما"


def test_ay_digraph_alternative():
    # the alif+ya split (عالايك) is primary; the ya-diphthong reading (عليك)
    # with the short a elided is produced as a ranked alternative
    res = transliterate("3alayk", top_k=5)
    cands = [c for c, _ in res.candidates]
    assert "عليك" in cands
    assert cands.index("عليك") == 3
    assert cands.index("ععلايك") > cands.index("عليك")  # bad sequence ranks last


def test_punctuation_passthrough():
    assert transliterate("ana!").text == "أنا!"


def test_top_k_candidates_ranked():
    res = transliterate("tare2", top_k=3)
    scores = [s for _, s in res.candidates]
    assert scores == sorted(scores)


def test_dialect_gulf():
    res = transliterate("shlonak ya 5al", with_dialect=True)
    assert res.dialect["dialect"] == "gulf"


def test_dialect_egyptian():
    res = transliterate("ana 3ayz 2akol", with_dialect=True)
    assert res.dialect["dialect"] == "egyptian"


def test_evidence_collected():
    res = transliterate("shlonak ya 5al", with_dialect=True)
    arabizi_words = [e["arabizi"] for e in res.evidence]
    assert "shlonak" in arabizi_words


def test_emojis_and_hashtags_pass_through():
    assert "🔥" in transliterate("ya salam 🔥").text
    # hashtag content is Arabizi too, but the # symbol itself is preserved
    assert transliterate("el 7ay #dubai").text == "الحي #دوباي"


def test_candidate_generation_bounded():
    tr = Transliterator()
    # long ambiguous words must not explode the candidate space
    res = tr._rule_candidates("3ayzansltrb", max_candidates=8)
    assert len(res) <= 8


@pytest.mark.parametrize(
    "text,expected",
    [
        ("ana 3ayz 2akol", "أنا عايز آكل"),
        ("shlonak ya 5al", "شلونك يا خال"),
        ("shu 3am 3emel", "شو عم عمل"),
        ("wacha kolshi mzyan", "واش كلشي مزيان"),
        ("hatha maqal mumtaz", "هذا مقال ممتاز"),
        ("lazem nro7 el su2", "لازم نروح السوق"),
        ("kwayes awi", "كويس أوي"),
        ("ya3ne shu", "يعني شو"),
    ],
)
def test_golden_sentences(text, expected):
    assert transliterate(text).text == expected
