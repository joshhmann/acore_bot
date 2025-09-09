from utils.formatter import normalize_ratio, format_gold, normalize_item_name, wrap_response


def test_format_gold():
    assert format_gold(1234567) == "123g 45s 67c"


def test_normalize_ratio():
    assert normalize_ratio(2) == "2x"
    assert normalize_ratio("1.234x") == "1.23x"


def test_normalize_item_name():
    assert normalize_item_name("cracked_egg") == "Cracked Egg"


def test_wrap_response():
    assert wrap_response("Players", "10") == "Players: 10 — source: Slum DB"
