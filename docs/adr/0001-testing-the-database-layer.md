# 1. Test the database layer with a fake, not a real Postgres

Date: 2026-09-21

Status: accepted

## Context

Uploads used to end in a read-modify-write on `data/garments.json`. The test
suite handled that by redirecting the two JSON paths into `tmp_path`: cheap,
total, and nothing outside the temp directory could be touched.

`ingest()` now writes a row instead — `db.add_photo(table, user_id, ...)`, with
a `unique (user_id, filename)` constraint deciding whether an upload is a 409.
There is no path to redirect any more. `db.engine` is built at import from
`DATABASE_URL`, which on a laptop is the Supabase database the real closet
lives in, so "do nothing" is not an option: it would point the suite at
production data.

## Decision

Fake the `db` module in tests, the same way `fake_model` fakes the Anthropic
client.

- `FakeDB` (`src/test/helpers.py`) keeps rows in a dict keyed
  `(table, user_id) -> {filename: [hexes]}` and raises the same 409 on a
  repeat. The `fake_db` fixture monkeypatches `db.add_photo` and
  `db.load_user_colors` onto it; `ingest` calls both through the module, so
  every caller is redirected at once.
- An autouse `no_real_database` fixture replaces `db.engine` with an object
  that raises on `connect()`/`begin()`. A test that reaches the database by
  some path nobody faked fails loudly instead of quietly reading — or
  writing — the real closet.
- One opt-in suite (`src/test/integration/test_db_integration.py`,
  `@pytest.mark.postgres`) runs the real functions against a throwaway
  Postgres. It is deselected by default via `-m "not postgres"` in
  `pyproject.toml`, skips unless `TEST_DATABASE_URL` is set, and calls
  `pytest.fail` if that URL names the same host/port/database as
  `DATABASE_URL`. The schema comes from `alembic upgrade head`, pointed at the
  throwaway by the `ALEMBIC_DATABASE_URL` override added to `migrations/env.py`.

## Alternatives considered

**A throwaway Postgres for every run, via testcontainers-python.** The most
faithful option: Docker starts a real server, Alembic builds the real schema,
and every test exercises the real constraint. Rejected for now because it
makes Docker a hard prerequisite for running any test and adds seconds of
container startup to a suite that currently finishes in about a second. The
opt-in tests above cover the same ground on demand; if the schema grows past
two flat tables — cascades, triggers, row-level security — this is the thing
to revisit.

**SQLite in memory.** Rejected outright. No `text[]`, no
`gen_random_uuid()`, and different constraint semantics, so the schema under
test would not be the schema that ships.

## Consequences

What the fast suite no longer proves:

- That the unique constraint exists, or is on `(user_id, filename)` rather
  than on `filename` alone. `FakeDB`'s conflict is a dict lookup that would
  keep passing if the migration dropped the constraint entirely.
- That `colors` round-trips through `text[]` as an ordered list of strings.
- That the column types, nullability and defaults in `db.py` match the
  migration.
- Anything about connection handling, transactions or rollback.

The postgres-marked tests cover exactly that list, which is why they are
worth keeping even though they are not run by default. Run them after any
migration:

```bash
createdb closetllm_test
TEST_DATABASE_URL=postgresql+psycopg:///closetllm_test uv run pytest -m postgres
```

`src/scripts/import_json.py` is the other thing that exercises real Postgres —
it is a one-shot backfill of the committed JSON, and running it is a real
integration check.

## Open items this turned up

- **The read routes still read JSON.** `/stats`, `/garments`,
  `/color-palettes` and `/color-matches` call `load_data()` on the files;
  only uploads write rows. The two round-trip tests in
  `test_upload_contract.py` are marked `xfail(strict=True)` and will start
  failing — the signal to delete the marker — as soon as the read half moves
  over. `db.load_user_colors` is faked already and ready for them.
- **The photo folders are one namespace shared by every user.** Rows are
  scoped per user, but `garments/shirt.jpeg` is not: two users who both
  upload `shirt.jpeg` get two valid rows and one file. The second upload
  overwrites the first user's photo. Per-user storage keys (the `storage_key`
  column is already there for it) are the fix.
