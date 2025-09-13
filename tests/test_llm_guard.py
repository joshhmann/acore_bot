import pytest
from bot.llm_guard import require_tool_for_sensitive, UngroundedAnswer
from bot.intent_router import Intent


def test_rejects_final_answer():
    with pytest.raises(UngroundedAnswer):
        require_tool_for_sensitive(Intent.REALM_STATUS, {"type": "final", "text": "Realm is online"})


def test_allows_clarifying_final():
    require_tool_for_sensitive(Intent.REALM_STATUS, {"type": "final", "text": "Which realm?"})


def test_allows_tool_call():
    require_tool_for_sensitive(Intent.REALM_STATUS, {"type": "tool_call", "name": "realm_status", "arguments": {}})
