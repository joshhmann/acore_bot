import pytest
from bot.intent_router import classify_intent, route, Intent


def test_classify_intent_password():
    assert classify_intent("can you change my password?") is Intent.PW_CHANGE


def test_route_modes_memory():
    first = route("what is the realm status?", None)
    assert first.mode == "authoritative"
    follow = route("and what about that?", first.mode)
    assert follow.mode == "authoritative"
