from utils.formatters import copper_to_gsc


def test_copper_to_gsc_basic():
    assert copper_to_gsc(0) == "0c"
    assert copper_to_gsc(99) == "99c"
    assert copper_to_gsc(100) == "1s"
    assert copper_to_gsc(101) == "1s 1c"
    assert copper_to_gsc(10000) == "1g"
    assert copper_to_gsc(1234567) == "123g 45s 67c"

