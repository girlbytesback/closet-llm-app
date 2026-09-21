"""Stand-ins for the Anthropic SDK and for Postgres, shared by the fixtures
and tests.

Kept out of conftest.py so a test module can import them by name; conftest
puts this directory on sys.path.
"""

import io
import json
from pathlib import Path

from fastapi import HTTPException
from PIL import Image

from closetllm import db

# The id the `client` fixture signs in as. Rows are owned, so a test that seeds
# the fake store and a request made through that client have to agree on who
# the owner is — hence one constant rather than a literal in each place.
TEST_USER = "test-user"


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


class FakeDB:
    """An in-memory stand-in for the two functions in closetllm.db.

    Rows are keyed the way the unique constraint is — (table, user, filename) —
    so the 409 the real insert raises is reproduced here, and a filename two
    different users both own is kept apart the same way.

    What it does NOT do is run any SQL: the conflict below is a dict lookup, not
    an IntegrityError coming back from Postgres, and nothing here checks column
    types or nullability. That is the accepted trade (see
    docs/adr/0001-testing-the-database-layer.md); the postgres-marked tests in
    integration/test_db_integration.py are what hold the real constraint to the
    same behaviour.
    """

    def __init__(self):
        # {(table_name, user_id): {filename: [hexes]}}
        self.rows: dict[tuple[str, str], dict[str, list[str]]] = {}
        self.calls: list[dict] = []          # every add_photo, for assertions

    # ---------------------------------------------- the db module's interface

    def add_photo(self, table, user_id, filename, colors, storage_key):
        self.calls.append(
            {
                "table": table.name,
                "user_id": user_id,
                "filename": filename,
                "colors": list(colors),
                "storage_key": storage_key,
            }
        )
        owned = self.rows.setdefault((table.name, user_id), {})
        if filename in owned:
            raise HTTPException(status_code=409, detail=f"{filename} already exists")
        owned[filename] = list(colors)

    def load_user_colors(self, table, user_id) -> dict:
        # a copy, so a caller mutating what it got back cannot edit the store
        return dict(self.rows.get((table.name, user_id), {}))

    # ------------------------------------------------- conveniences for tests

    def seed(self, table, user_id, rows: dict) -> None:
        self.rows.setdefault((table.name, user_id), {}).update(rows)

    def garments(self, user_id=TEST_USER) -> dict:
        return self.load_user_colors(db.garments, user_id)

    def palettes(self, user_id=TEST_USER) -> dict:
        return self.load_user_colors(db.palettes, user_id)


class RefusingEngine:
    """Stands in for db.engine everywhere the fake is not installed.

    The real engine is built at import from DATABASE_URL, which on a laptop is
    the Supabase database holding the actual closet. A test that reaches the
    database by a path nobody faked should fail loudly here rather than
    quietly read — or write — that.
    """

    def _refuse(self, *args, **kwargs):
        raise RuntimeError(
            "a test tried to open a real database connection; use the fake_db "
            "fixture, or mark the test @pytest.mark.postgres to run it against "
            "a throwaway Postgres"
        )

    connect = begin = _refuse


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def jpeg_bytes(color=(180, 194, 154), size=(40, 40)) -> bytes:
    """Real JPEG bytes for an upload payload.

    Uploads have to carry a decodable image: web_copy and image_block both
    open the file they are handed, so a b"fake" placeholder would blow up in
    PIL rather than exercising the path under test.
    """
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()
