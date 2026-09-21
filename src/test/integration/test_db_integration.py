"""The one place the tests talk to a real Postgres.

Everything else fakes closetllm.db (see conftest's fake_db), which keeps the
suite fast and Docker-free but never runs a line of SQL. These tests are what
hold the real schema to the behaviour the fake pretends to have: the unique
constraint, its scope, and the array round-tripping as a list of strings.

They are deselected by default — pyproject sets `-m "not postgres"` — because
they need a database that does not exist on a fresh checkout. To run them:

    createdb closetllm_test
    TEST_DATABASE_URL=postgresql+psycopg:///closetllm_test \\
        uv run pytest -m postgres

TEST_DATABASE_URL must not be the database the real closet lives in; the
guard below refuses to run if it looks like DATABASE_URL. The schema is built
by `alembic upgrade head` against that URL, so a migration that does not match
db.py's table definitions fails here rather than in production.
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine, delete, make_url

from closetllm import db
from closetllm.config import database_url, project_root

pytestmark = pytest.mark.postgres

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


def _same_database(a: str, b: str) -> bool:
    """Ignore the driver and the password; host, port and name are the identity."""
    one, two = make_url(a), make_url(b)
    return (one.host, one.port, one.database) == (two.host, two.port, two.database)


@pytest.fixture(scope="module")
def engine():
    if not TEST_DATABASE_URL:
        pytest.skip("set TEST_DATABASE_URL to a throwaway Postgres to run these")
    if _same_database(TEST_DATABASE_URL, database_url):
        pytest.fail(
            "TEST_DATABASE_URL and DATABASE_URL name the same database — "
            "refusing to run the schema and the inserts below against the "
            "closet you actually use"
        )

    from alembic import command
    from alembic.config import Config

    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "migrations"))
    os.environ["ALEMBIC_DATABASE_URL"] = TEST_DATABASE_URL   # read by migrations/env.py
    try:
        command.upgrade(config, "head")
    finally:
        del os.environ["ALEMBIC_DATABASE_URL"]

    engine = create_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def real_db(engine, monkeypatch):
    """Point db's two functions at the throwaway database.

    They use the module-level engine, so swapping that is enough — the
    functions under test are the real ones, unlike everywhere else. Rows are
    written under a user id nobody else has and deleted afterwards, so the
    tests can run against a database that already has data in it.
    """
    monkeypatch.setattr(db, "engine", engine)
    user = f"test-{uuid.uuid4()}"
    other = f"test-{uuid.uuid4()}"
    yield user, other

    with engine.begin() as conn:
        for table in (db.garments, db.palettes):
            conn.execute(delete(table).where(table.c.user_id.in_([user, other])))


def test_a_row_comes_back_the_way_it_went_in(real_db):
    user, _ = real_db

    db.add_photo(db.garments, user, "shirt.jpeg", ["#B5C29A", "#E4A8C0"], storage_key="shirt.jpeg")

    # a text[] has to arrive as a list of str, in order — match.py compares
    # these strings and the UI renders them
    assert db.load_user_colors(db.garments, user) == {"shirt.jpeg": ["#B5C29A", "#E4A8C0"]}


def test_the_unique_constraint_is_what_raises_the_409(real_db):
    # this is the assertion the fake cannot make: FakeDB's conflict is a dict
    # lookup, and ingest's fast path would hide a constraint that was missing
    # or scoped to the wrong columns
    user, _ = real_db
    db.add_photo(db.garments, user, "shirt.jpeg", ["#B5C29A"], storage_key="shirt.jpeg")

    with pytest.raises(Exception) as err:
        db.add_photo(db.garments, user, "shirt.jpeg", ["#111111"], storage_key="shirt.jpeg")

    assert err.value.status_code == 409
    assert "shirt.jpeg" in err.value.detail
    # the loser must not have overwritten the winner
    assert db.load_user_colors(db.garments, user) == {"shirt.jpeg": ["#B5C29A"]}


def test_the_constraint_is_scoped_to_one_user(real_db):
    user, other = real_db

    db.add_photo(db.garments, user, "shirt.jpeg", ["#B5C29A"], storage_key="shirt.jpeg")
    db.add_photo(db.garments, other, "shirt.jpeg", ["#111111"], storage_key="shirt.jpeg")

    assert db.load_user_colors(db.garments, user) == {"shirt.jpeg": ["#B5C29A"]}
    assert db.load_user_colors(db.garments, other) == {"shirt.jpeg": ["#111111"]}


def test_a_read_only_returns_the_asking_users_rows(real_db):
    user, other = real_db
    db.add_photo(db.garments, user, "mine.jpeg", ["#B5C29A"], storage_key="mine.jpeg")
    db.add_photo(db.garments, other, "theirs.jpeg", ["#111111"], storage_key="theirs.jpeg")

    assert list(db.load_user_colors(db.garments, user)) == ["mine.jpeg"]


def test_the_two_tables_are_separate(real_db):
    user, _ = real_db

    db.add_photo(db.garments, user, "shirt.jpeg", ["#B5C29A"], storage_key="shirt.jpeg")
    db.add_photo(db.palettes, user, "shirt.jpeg", ["#E4A8C0"], storage_key="shirt.jpeg")

    assert db.load_user_colors(db.garments, user) == {"shirt.jpeg": ["#B5C29A"]}
    assert db.load_user_colors(db.palettes, user) == {"shirt.jpeg": ["#E4A8C0"]}


def test_an_empty_closet_reads_as_an_empty_dict(real_db):
    # the shape the JSON store had for "nothing saved yet"; several callers
    # branch on the dict being falsy rather than on None
    user, _ = real_db

    assert db.load_user_colors(db.garments, user) == {}
