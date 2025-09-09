import ac_metrics as kpi


def test_copper_to_gold_s_basic():
    assert kpi.copper_to_gold_s(0) == "0c"
    assert kpi.copper_to_gold_s(99) == "99c"
    assert kpi.copper_to_gold_s(100) == "1s"
    assert kpi.copper_to_gold_s(101) == "1s 1c"
    assert kpi.copper_to_gold_s(10000) == "1g"
    assert kpi.copper_to_gold_s(1234567) == "123g 45s 67c"

