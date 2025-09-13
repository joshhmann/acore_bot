import pytest
from bot.intent_router import classify_intent, Intent
from bot.llm_guard import require_tool_for_sensitive, UngroundedAnswer


def test_sensitive_requires_tool():
    intent = classify_intent("just tell me population")
    assert intent is Intent.REALM_STATUS
    with pytest.raises(UngroundedAnswer):
        require_tool_for_sensitive(intent, {"type": "final", "text": "It's 100"})
