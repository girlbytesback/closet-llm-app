"""Stand-ins for the Anthropic SDK and for Postgres, shared by the fixtures
and tests.

Kept out of conftest.py so a test module can import them by name; conftest
puts this directory on sys.path.
"""

import io
import json
import uuid
from pathlib import Path

from PIL import Image

from closetllm import db
from closetllm.ingest import storage_key_for

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
    """An in-memory stand-in for the four functions in closetllm.db.

    Rows are keyed the way the unique constraint is — (table, user, filename) —
    so the 409 the real insert raises is reproduced here, and a filename two
    different users both own is kept apart the same way. Each row carries the
    other two columns the endpoints read back: its storage_key and its id.

    What it does NOT do is run any SQL: the conflict below is a dict lookup, not
    an IntegrityError coming back from Postgres, and nothing here checks column
    types or nullability. That is the accepted trade (see
    docs/adr/0001-testing-the-database-layer.md); the postgres-marked tests in
    integration/test_db_integration.py are what hold the real constraint to the
    same behaviour.
    """

    def __init__(self):
        # {(table_name, user_id): {filename: {"colors", "storage_key", "id"}}}
        self.rows: dict[tuple[str, str], dict[str, dict]] = {}
        self.calls: list[dict] = []          # every add_photo, for assertions
        self.deleted: list[tuple[str, object]] = []   # every delete_photo

    # ---------------------------------------------- the db module's interface

    def add_photo(self, table, user_id, filename, colors, storage_key, photo_id=None):
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
            raise db.DuplicatePhoto(filename)
        owned[filename] = {
            "colors": list(colors),
            "storage_key": storage_key,
            "id": photo_id,
        }

    def load_user_colors(self, table, user_id) -> dict:
        # a copy, so a caller mutating what it got back cannot edit the store
        rows = self.rows.get((table.name, user_id), {})
        return {filename: list(row["colors"]) for filename, row in rows.items()}

    def load_user_keys(self, table, user_id) -> dict:
        rows = self.rows.get((table.name, user_id), {})
        return {filename: row["storage_key"] for filename, row in rows.items()}

    def delete_photo(self, table, photo_id) -> None:
        # the real one deletes by primary key, so it does not know or care
        # which user owns the row; scan every owner in this table, same as a
        # `WHERE id = ...` would
        self.deleted.append((table.name, photo_id))
        for (table_name, _user), owned in self.rows.items():
            if table_name != table.name:
                continue
            for filename, row in list(owned.items()):
                if row["id"] == photo_id:
                    del owned[filename]

    # ------------------------------------------------- conveniences for tests

    def seed(self, table, user_id, rows: dict) -> None:
        """Rows that were already there, as if an earlier upload had written them.

        Each gets a storage_key in the same shape ingest mints, so a test can
        seed a closet and still get signed links back out of /color-matches.
        """
        owned = self.rows.setdefault((table.name, user_id), {})
        for filename, colors in rows.items():
            photo_id = uuid.uuid4()
            owned[filename] = {
                "colors": list(colors),
                "storage_key": storage_key_for(table, user_id, photo_id, Path(filename).suffix.lower()),
                "id": photo_id,
            }

    def garments(self, user_id=TEST_USER) -> dict:
        return self.load_user_colors(db.garments, user_id)

    def palettes(self, user_id=TEST_USER) -> dict:
        return self.load_user_colors(db.palettes, user_id)


class FakeStorage:
    """An in-memory stand-in for the three functions in closetllm.storage.

    The real ones talk to the Supabase bucket the actual closet lives in, so
    every test that uploads goes through this instead. Keys are stored the way
    the bucket does — one flat namespace, "<user_id>/<filename>" — and put()
    refuses a key that is already taken, which is what the real upload does.

    signed_urls() returns a made-up link per key so a test can tell one photo's
    URL from another's; it deliberately skips keys that were never put, because
    that is how the real call behaves and the endpoints have to cope with a row
    whose photo is missing.
    """

    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.content_types: dict[str, str] = {}
        self.deleted: list[str] = []          # every delete, for assertions

    # ------------------------------------------- the storage module's interface

    def put(self, key: str, data: bytes, content_type: str) -> None:
        if key in self.files:
            raise FileExistsError(key)
        self.files[key] = bytes(data)
        self.content_types[key] = content_type

    def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.files.pop(key, None)
        self.content_types.pop(key, None)

    def signed_urls(self, keys: list[str]) -> dict[str, str]:
        return {key: f"https://fake.storage/{key}?token=test" for key in keys if key in self.files}


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


class RefusingBucket:
    """Stands in for storage._bucket everywhere the fake is not installed.

    Same reasoning as RefusingEngine: the real bucket is built at import from
    SUPABASE_URL, which on a laptop is the one holding the actual closet's
    photos. A test that uploads by a path nobody faked should fail here rather
    than quietly put a file there.
    """

    def _refuse(self, *args, **kwargs):
        raise RuntimeError(
            "a test tried to reach the real storage bucket; use the "
            "fake_storage fixture"
        )

    upload = remove = create_signed_urls = _refuse


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
