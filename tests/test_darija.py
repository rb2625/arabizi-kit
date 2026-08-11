"""Tests for the Maghrebi (Darija) conventions added in v0.3."""

from arabizikit.transliterate import transliterate


def _cands(text: str, top_k: int = 3, hint: str | None = None) -> list[str]:
    return [ar for ar, _ in transliterate(text, top_k=top_k, dialect_hint=hint).candidates]


def test_9_reads_qaf_with_maghrebi_hint():
    # With the dialect hint, 9 -> qaf: mtye99n -> متيقن, yb9aw -> يبقاو.
    assert transliterate("mtye99n", dialect_hint="maghrebi").text == "متيقن"
    assert transliterate("yb9aw", dialect_hint="maghrebi").text == "يبقاو"


def test_9_keeps_sad_primary_in_egyptian():
    # Without a hint, 9 -> sad is the global default: 9ba7 -> صباح.
    assert transliterate("9ba7").text == "صباح"
    assert transliterate("9ba7", dialect_hint="egyptian").text == "صباح"


def test_9_apostrophe_is_dad():
    # 9' is dad in the Egyptian convention: ra9'e -> راض (with a hamza-less reading).
    assert "ض" in transliterate("ra9'e").text


def test_8_apostrophe_is_ghayn():
    assert "غ" in transliterate("8'ali").text


def test_8_reads_heh_in_moroccan():
    # n8ar -> نهار uses the heh reading with the Maghrebi hint.
    assert transliterate("n8ar", dialect_hint="maghrebi").text == "نهار"


def test_ch_reads_shin():
    # ch is shin in French-influenced spelling: ghanmchi ranks ش first.
    assert "ش" in transliterate("ghanmchi").text
    assert "غنمشي" in _cands("ghanmchi", top_k=8)
    assert "نمشي" in _cands("nmchi")


def test_doubled_consonant_written_once_in_maghrebi():
    # Gemination is written once in the Darija convention: mbrrdin -> مبردين.
    assert transliterate("mbrrdin", dialect_hint="maghrebi").text == "مبردين"
    assert transliterate("mkhbbyin", dialect_hint="maghrebi").text == "مخبيين"


def test_doubled_consonant_kept_in_levantine():
    # The Levant keeps the double letter: mml -> ممل, allyla -> الليلة.
    assert transliterate("mml", dialect_hint="levantine").text == "ممل"
    assert transliterate("allyla", dialect_hint="levantine").text == "الليلة"
    assert transliterate("mmt3a", dialect_hint="levantine").text == "ممتعة"


def test_initial_double_is_assimilated_article():
    # l + coronal assimilates in Darija: jjaya -> الجاية, ssimana -> السيمانة.
    assert transliterate("jjaya", dialect_hint="maghrebi").text == "الجاية"
    assert transliterate("ssimana", dialect_hint="maghrebi").text == "السيمانة"


def test_double_after_preposition():
    # bssalama -> بالسلامة comes from the lexicon; the rule reading is also sound.
    assert transliterate("bssalama").text == "بالسلامة"


def test_capital_t_is_emphatic_ta():
    assert _cands("loTilat")[0] == "لوطيلات"
    assert transliterate("Tayeb").text == "طايب"
    assert "طيب" in _cands("Tayeb")  # ay -> ي is a ranked alternative


def test_capital_s_is_sad():
    # 9Sdti -> قصدتي needs 9 -> ق (hint) and S -> ص (case rule).
    assert transliterate("9Sdti", dialect_hint="maghrebi").text == "قصدتي"


def test_final_a_ya_alternative():
    # b9a -> بقى uses the lexicon entry with the ya spelling.
    assert transliterate("b9a").text == "بقى"


def test_maghrebi_lexicon_entries():
    assert transliterate("bach").text == "باش"
    assert transliterate("m3ak").text == "معاك"
    assert "نقرا" in _cands("n9ra", top_k=8)  # 9 -> ق plus final a -> ا
