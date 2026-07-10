"""User-facing error type."""
from __future__ import annotations

from foundation.exceptions import PlatformError

from creator.errors import CreatorError


def test_creator_error_is_a_platform_error():
    assert issubclass(CreatorError, PlatformError)


def test_carries_message_and_hint():
    err = CreatorError("something went wrong", hint="try this instead")
    assert err.message == "something went wrong"
    assert err.hint == "try this instead"


def test_hint_defaults_to_empty():
    assert CreatorError("boom").hint == ""


def test_details_are_preserved():
    err = CreatorError("bad value", hint="fix it", field="renderer")
    assert err.details["field"] == "renderer"
