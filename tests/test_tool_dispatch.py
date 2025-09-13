import pytest
from bot.tool_dispatch import dispatch
from bot import tools


def test_schema_validation_error():
    res = dispatch({"name": "register_account", "arguments": {"username": "u"}})
    assert res["type"] == "tool_error"


def test_dispatch_success_and_redaction(monkeypatch, caplog):
    def fake_handler(args):
        return {"ok": True, "ts": "T"}

    spec = tools.TOOL_REGISTRY["change_password"].copy()
    spec["handler"] = fake_handler
    monkeypatch.setitem(tools.TOOL_REGISTRY, "change_password", spec)
    caplog.set_level("INFO")
    res = dispatch(
        {
            "name": "change_password",
            "arguments": {"username": "u", "old_password": "old", "new_password": "new"},
        }
    )
    assert res["type"] == "tool_result"
    assert "old" not in caplog.text and "new" not in caplog.text
