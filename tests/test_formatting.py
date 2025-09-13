from bot.formatting import render_tool_result


def test_realm_status_render():
    tr = {
        "name": "realm_status",
        "result": {"online": True, "uptime_h": 5, "players": 10, "ts": "2024-01-01T00:00:00Z"},
    }
    out = render_tool_result(tr)
    assert "Realm — Online: True" in out
    assert "as of" in out


def test_account_render_no_secrets():
    tr = {"name": "change_password", "result": {"ok": True, "ts": "x"}}
    out = render_tool_result(tr)
    assert "🔒" in out
    assert "password" not in out.lower()
