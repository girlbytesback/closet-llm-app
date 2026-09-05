"""Stand-ins for the Anthropic SDK objects, shared by the fixtures and tests.

Kept out of conftest.py so a test module can import them by name; conftest
puts this directory on sys.path.
"""

import json
from pathlib import Path


class FakeBlock:
    """A content block: only .type and .input are ever read."""

    def __init__(self, type_, input_=None):
        self.type = type_
        self.input = input_


class FakeResponse:
    def __init__(self, content, stop_reason="tool_use"):
        self.content = content
        self.stop_reason = stop_reason


class FakeMessages:
    """Scripted replies, and a record of every call for assertions."""

    def __init__(self, replies):
        self._replies = list(replies)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._replies:
            raise AssertionError("the model was called more times than the test allowed")
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())
