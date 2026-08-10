from arabizikit.normalize import normalize, normalized_tokens


def test_alef_variants_collapse():
    assert normalize("آكل") == "اكل"
    assert normalize("إنت") == "انت"
    assert normalize("أنا") == "انا"


def test_taa_marbuta_to_ha():
    assert normalize("مدة") == "مده"
    assert normalize("حلوة") == "حلوه"


def test_alef_maqsura_to_ya():
    assert normalize("على") == "علي"


def test_diacritics_are_stripped():
    assert normalize("شكراً") == "شكرا"
    assert normalize("مُحَمَّد") == "محمد"


def test_tatweel_is_removed():
    assert normalize("متــر") == "متر"


def test_hamza_seats_normalise():
    assert normalize("سؤال") == "سوال"
    assert normalize("شيء") == "شيا"


def test_whitespace_collapsed():
    assert normalize("  أنا   طالب  ") == "انا طالب"


def test_tokens():
    assert normalized_tokens("أنا طالب") == ["انا", "طالب"]
