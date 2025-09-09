import slum_queries as sq


def test_resolve_skill_id_by_name_case_insensitive():
    assert sq.resolve_skill_id("Enchanting") == 333
    assert sq.resolve_skill_id("alchemy") == 171
    assert sq.resolve_skill_id("ALCHEMY") == 171


def test_resolve_skill_id_numeric():
    assert sq.resolve_skill_id("333") == 333
    assert sq.resolve_skill_id(333) == 333


def test_profession_counts_default(monkeypatch):
    called = {}

    def fake_kpi(skill_id, min_value):
        called["args"] = (skill_id, min_value)
        return 42

    monkeypatch.setattr(sq, "kpi_profession_counts", fake_kpi)
    assert sq.profession_counts(333) == 42
    assert called["args"] == (333, 225)
