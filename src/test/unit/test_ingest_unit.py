"""ingest.py: one uploaded photo -> a model call, one row, one object in the bucket.

The route handlers are one line each, so everything worth checking about an
upload lives here. fake_model stands in for the client, fake_db for Postgres
and fake_storage for the bucket, so no test spends money, touches a real
database or puts a file in the real bucket; the uploads carry real JPEG bytes
because web_copy and image_block both open the file they are handed.

Nothing an upload writes survives locally any more — ingest stages the photo in
a TemporaryDirectory and uploads from there — so "did it clean up?" is asserted
against the bucket and the rows rather than against a folder.

Which table a photo lands in is passed in rather than carried by the job, so
every call below names one: db.garments or db.palettes.
"""

import io

import pytest
from fastapi import HTTPException
from PIL import Image
from starlette.datastructures import UploadFile

from closetllm import db, storage
from closetllm.extract import garment_job, palette_job
from closetllm.ingest import ingest

from helpers import TEST_USER as USER, jpeg_bytes


@pytest.fixture
def upload():
    """Build an UploadFile the way Starlette hands one to the route."""

    def make(filename, content=None):
        content = jpeg_bytes() if content is None else content
        return UploadFile(file=io.BytesIO(content), filename=filename)

    return make


@pytest.fixture(autouse=True)
def stores(fake_db, fake_storage):
    """The two places an upload writes, faked for every test in this module.

    Pulled in autouse rather than test by test: every call to ingest() below
    writes a row and puts an object, and an unfaked one would go looking for
    the real database and the real bucket.
    """
    from types import SimpleNamespace

    return SimpleNamespace(db=fake_db, storage=fake_storage)


@pytest.fixture
def job():
    """The garment job: which model, tool and prompt to use."""
    return garment_job


@pytest.fixture
def palette():
    return palette_job


def only_key(fake_storage) -> str:
    """The single object in the bucket — most tests upload exactly one."""
    assert len(fake_storage.files) == 1, fake_storage.files
    return next(iter(fake_storage.files))


def stored_image(fake_storage, key=None) -> Image.Image:
    return Image.open(io.BytesIO(fake_storage.files[key or only_key(fake_storage)]))


# ----------------------------------------------------------- file type gate

@pytest.mark.parametrize("filename", ["notes.txt", "clip.mov", "archive.zip", "noext"])
def test_a_non_photo_is_rejected_as_415(filename, upload, job, stores, fake_model):
    messages = fake_model()  # any model call at all fails the test

    with pytest.raises(HTTPException) as err:
        ingest(upload(filename, b"whatever"), job, db.garments, USER, False)

    assert err.value.status_code == 415
    assert messages.calls == []
    # the gate has to come before the upload, or the bucket fills with junk
    assert stores.storage.files == {}
    assert stores.db.garments() == {}


@pytest.mark.parametrize("filename", ["A.JPEG", "b.JPG", "c.PNG"])
def test_an_uppercase_extension_is_accepted(filename, upload, job, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A"})

    result = ingest(upload(filename), job, db.garments, USER, False)

    assert result["name"] == filename


def test_a_filename_with_a_space_is_kept_verbatim(upload, job, stores, fake_model):
    # the filename is what the UI labels the photo with and what the unique
    # constraint is scoped to, so any rewrite here is a different garment
    fake_model({"item": "dress", "color": "#E4A8C0"})

    result = ingest(upload("pink dress.jpeg"), job, db.garments, USER, False)

    assert result["name"] == "pink dress.jpeg"
    assert stores.db.garments() == {"pink dress.jpeg": ["#E4A8C0"]}


@pytest.mark.parametrize(
    "filename",
    ["../../../etc/evil.jpeg", "/tmp/evil.jpeg", "sub/dir/evil.jpeg"],
)
def test_a_path_in_the_filename_cannot_escape(filename, upload, job, stores, fake_model):
    # the client controls this string entirely; only the last component is ours
    fake_model({"item": "shirt", "color": "#B5C29A"})

    result = ingest(upload(filename), job, db.garments, USER, False)

    assert result["name"] == "evil.jpeg"
    assert list(stores.db.garments()) == ["evil.jpeg"]
    # and it cannot climb out of this user's prefix in the bucket either
    assert only_key(stores.storage).startswith(f"garments/{USER}/")


# ------------------------------------------------------------------ conflict

def test_a_filename_this_user_already_has_is_409(upload, job, stores, fake_model):
    # the row is what makes a filename taken. The photo behind the existing row
    # must survive the collision — a retry that overwrote it would swap one
    # garment's picture for another's.
    stores.db.seed(db.garments, USER, {"shirt.jpeg": ["#123456"]})
    existing_key = stores.db.load_user_keys(db.garments, USER)["shirt.jpeg"]
    stores.storage.put(existing_key, b"the original", "image/jpeg")
    fake_model({"item": "shirt", "color": "#B5C29A"})

    with pytest.raises(HTTPException) as err:
        ingest(upload("shirt.jpeg"), job, db.garments, USER, False)

    assert err.value.status_code == 409
    assert "shirt.jpeg" in err.value.detail
    assert stores.db.garments() == {"shirt.jpeg": ["#123456"]}
    assert stores.storage.files == {existing_key: b"the original"}


def test_the_same_filename_under_another_user_is_allowed(upload, job, stores, fake_model):
    # rows are owned; two people are each allowed a shirt.jpeg
    stores.db.seed(db.garments, "someone-else", {"shirt.jpeg": ["#123456"]})
    fake_model({"item": "shirt", "color": "#B5C29A"})

    result = ingest(upload("shirt.jpeg"), job, db.garments, USER, False)

    assert result["colors"] == ["#B5C29A"]
    assert stores.db.garments() == {"shirt.jpeg": ["#B5C29A"]}
    assert stores.db.garments("someone-else") == {"shirt.jpeg": ["#123456"]}


# ------------------------------------------------------------ the object key

def test_the_photo_is_uploaded_byte_for_byte(upload, palette, stores, fake_model):
    # palettes are uploaded as-is; the garment path downscales first, below
    fake_model({"colors": ["#B5C29A"]})
    content = jpeg_bytes(color=(228, 168, 192))

    ingest(upload("inspo.jpeg", content), palette, db.palettes, USER, False)

    assert stores.storage.files[only_key(stores.storage)] == content


def test_the_key_is_the_one_recorded_on_the_row(upload, job, stores, fake_model):
    # a row pointing at a key nobody uploaded is a broken image in the UI
    fake_model({"item": "shirt", "color": "#B5C29A"})

    ingest(upload("shirt.jpeg"), job, db.garments, USER, False)

    assert stores.db.load_user_keys(db.garments, USER) == {
        "shirt.jpeg": only_key(stores.storage)
    }


def test_the_key_is_scoped_to_the_table_and_the_user(upload, job, stores, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A"})

    ingest(upload("shirt.jpeg"), job, db.garments, USER, False)

    key = only_key(stores.storage)
    assert key.startswith(f"garments/{USER}/")
    assert key.endswith(".jpeg")
    # not the filename: the bucket is one flat namespace, and the same person
    # is allowed a shirt.jpeg in each table
    assert "shirt" not in key


def test_two_users_uploading_the_same_name_get_different_keys(upload, job, stores, fake_model):
    fake_model({"item": "a", "color": "#B5C29A"}, {"item": "b", "color": "#E4A8C0"})

    ingest(upload("shirt.jpeg"), job, db.garments, USER, False)
    ingest(upload("shirt.jpeg"), job, db.garments, "someone-else", False)

    assert len(stores.storage.files) == 2


def test_the_content_type_is_set_from_the_extension(upload, job, stores, fake_model):
    # the browser renders the signed link inline; served as octet-stream it
    # downloads instead
    fake_model({"item": "shirt", "color": "#B5C29A"})

    ingest(upload("shirt.jpeg"), job, db.garments, USER, False)

    assert stores.storage.content_types[only_key(stores.storage)] == "image/jpeg"


# --------------------------------------------------------------- web copies

def test_a_garment_is_downscaled_before_it_is_uploaded(upload, job, stores, fake_model):
    from closetllm.config import web_max_edge

    fake_model({"item": "shirt", "color": "#B5C29A"})
    big = jpeg_bytes(size=(2000, 1500))

    ingest(upload("shirt.jpeg", big), job, db.garments, USER, True)

    assert max(stored_image(stores.storage).size) == web_max_edge


def test_a_palette_is_uploaded_at_full_size(upload, palette, stores, fake_model):
    # only garments get the web copy: the UI draws them at ~70px, while a
    # palette is the thing you actually look at
    fake_model({"colors": ["#B5C29A"]})
    big = jpeg_bytes(size=(2000, 1500))

    ingest(upload("inspo.jpeg", big), palette, db.palettes, USER, False)

    assert stored_image(stores.storage).size == (2000, 1500)


def test_only_one_object_is_uploaded_per_photo(upload, job, stores, fake_model):
    # the original is staged locally and thrown away; the web copy is the only
    # thing that reaches the bucket
    fake_model({"item": "shirt", "color": "#B5C29A"})

    ingest(upload("shirt.jpeg"), job, db.garments, USER, True)

    assert len(stores.storage.files) == 1


# --------------------------------------------------------- the model's colors

def test_a_single_color_comes_back_wrapped_in_a_list(upload, job, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A"})

    assert ingest(upload("shirt.jpeg"), job, db.garments, USER, False) == {
        "name": "shirt.jpeg",
        "colors": ["#B5C29A"],
    }


def test_a_palettes_colors_are_all_kept(upload, palette, fake_model):
    fake_model({"colors": ["#B5C29A", "#E4A8C0"]})

    result = ingest(upload("inspo.jpeg"), palette, db.palettes, USER, False)

    assert result["colors"] == ["#B5C29A", "#E4A8C0"]


@pytest.mark.parametrize(
    "returned, expected",
    [(" b5c29a ", "#B5C29A"), ("#abc", "#AABBCC"), ("#b5c29a", "#B5C29A")],
)
def test_the_colors_are_normalized_before_they_are_saved(
    returned, expected, upload, job, stores, fake_model
):
    # the schema asks for '#RRGGBB' but the model is not bound by it, and
    # match.py compares these strings against each other
    fake_model({"item": "shirt", "color": returned})

    result = ingest(upload("shirt.jpeg"), job, db.garments, USER, False)

    assert result["colors"] == [expected]
    assert stores.db.garments() == {"shirt.jpeg": [expected]}


def test_an_empty_color_list_is_a_502(upload, palette, stores, fake_model):
    # an empty list saves cleanly and then blows up much later inside
    # score_garment's min() — refuse the upload instead
    fake_model({"colors": []})

    with pytest.raises(HTTPException) as err:
        ingest(upload("inspo.jpeg"), palette, db.palettes, USER, False)

    assert err.value.status_code == 502
    assert "inspo.jpeg" in err.value.detail
    assert stores.db.palettes() == {}
    assert stores.storage.files == {}


def test_a_color_that_is_not_hex_is_refused(upload, job, stores, fake_model):
    fake_model({"item": "shirt", "color": "sage green"})

    with pytest.raises(ValueError):
        ingest(upload("shirt.jpeg"), job, db.garments, USER, False)

    assert stores.db.garments() == {}
    assert stores.storage.files == {}


def test_a_model_failure_writes_nothing(upload, job, stores, fake_model):
    fake_model(RuntimeError("the model is down"))

    with pytest.raises(RuntimeError):
        ingest(upload("shirt.jpeg"), job, db.garments, USER, True)

    assert stores.db.garments() == {}
    assert stores.storage.files == {}


def test_a_retry_after_a_model_failure_succeeds(upload, job, fake_model):
    # the whole point of writing nothing on the way out: the second attempt
    # must look like a first, not hit the 409
    fake_model(RuntimeError("the model is down"), {"item": "shirt", "color": "#B5C29A"})

    with pytest.raises(RuntimeError):
        ingest(upload("shirt.jpeg"), job, db.garments, USER, False)

    result = ingest(upload("shirt.jpeg"), job, db.garments, USER, False)
    assert result["colors"] == ["#B5C29A"]


def test_a_retry_after_a_502_is_not_blocked_by_a_409(upload, palette, fake_model):
    fake_model({"colors": []}, {"colors": ["#B5C29A"]})

    with pytest.raises(HTTPException) as err:
        ingest(upload("inspo.jpeg"), palette, db.palettes, USER, True)
    assert err.value.status_code == 502

    result = ingest(upload("inspo.jpeg"), palette, db.palettes, USER, True)
    assert result["colors"] == ["#B5C29A"]


# ----------------------------------------------------------------- the row

def test_the_row_is_written_for_the_uploading_user(upload, job, stores, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A"})

    ingest(upload("shirt.jpeg"), job, db.garments, USER, False)

    assert stores.db.garments() == {"shirt.jpeg": ["#B5C29A"]}
    assert [
        {k: v for k, v in call.items() if k != "storage_key"}
        for call in stores.db.calls
    ] == [
        {
            "table": "garments",
            "user_id": USER,
            "filename": "shirt.jpeg",
            "colors": ["#B5C29A"],
        }
    ]


def test_an_upload_does_not_disturb_the_photos_already_saved(upload, job, stores, fake_model):
    stores.db.seed(db.garments, USER, {"old.jpeg": ["#123456"]})
    fake_model({"item": "shirt", "color": "#B5C29A"})

    ingest(upload("shirt.jpeg"), job, db.garments, USER, False)

    assert stores.db.garments() == {
        "old.jpeg": ["#123456"],
        "shirt.jpeg": ["#B5C29A"],
    }


def test_two_uploads_both_land(upload, job, stores, fake_model):
    fake_model({"item": "a", "color": "#B5C29A"}, {"item": "b", "color": "#E4A8C0"})

    ingest(upload("a.jpeg"), job, db.garments, USER, False)
    ingest(upload("b.jpeg"), job, db.garments, USER, False)

    assert stores.db.garments() == {"a.jpeg": ["#B5C29A"], "b.jpeg": ["#E4A8C0"]}
    assert len(stores.storage.files) == 2


def test_a_garment_and_a_palette_write_to_different_tables(
    upload, job, palette, stores, fake_model
):
    # the table is the argument that routes them; crossing it would file a
    # garment as an inspiration palette
    fake_model({"item": "shirt", "color": "#B5C29A"}, {"colors": ["#E4A8C0"]})

    ingest(upload("shirt.jpeg"), job, db.garments, USER, False)
    ingest(upload("inspo.jpeg"), palette, db.palettes, USER, False)

    assert stores.db.garments() == {"shirt.jpeg": ["#B5C29A"]}
    assert stores.db.palettes() == {"inspo.jpeg": ["#E4A8C0"]}


def test_the_same_name_in_both_tables_does_not_collide_in_the_bucket(
    upload, job, palette, stores, fake_model
):
    fake_model({"item": "shirt", "color": "#B5C29A"}, {"colors": ["#E4A8C0"]})

    ingest(upload("shirt.jpeg"), job, db.garments, USER, False)
    ingest(upload("shirt.jpeg"), palette, db.palettes, USER, False)

    assert len(stores.storage.files) == 2


# ------------------------------------------------------------- the model call

def test_the_job_decides_which_model_and_tool_are_used(upload, palette, fake_model):
    messages = fake_model({"colors": ["#B5C29A"]})

    ingest(upload("inspo.jpeg"), palette, db.palettes, USER, False)

    sent = messages.calls[0]
    assert sent["model"] == palette.model
    assert sent["tool_choice"] == {"type": "tool", "name": "extract_colors"}


def test_the_model_sees_the_staged_photo_exactly_once(upload, job, fake_model):
    messages = fake_model({"item": "shirt", "color": "#B5C29A"})

    ingest(upload("shirt.jpeg"), job, db.garments, USER, False)

    assert len(messages.calls) == 1
    assert messages.calls[0]["messages"][0]["content"][0]["type"] == "image"


# ------------------------------------------------- cleanup on the later steps

def test_a_file_that_is_not_really_a_photo_is_refused(upload, job, stores, fake_model):
    # the gate checks the extension, not the bytes; PIL is what finds out, and
    # by then the upload is already staged
    messages = fake_model()
    payload = upload("shirt.jpeg", b"this is not a JPEG")

    with pytest.raises(Exception):
        ingest(payload, job, db.garments, USER, True)

    assert messages.calls == []       # PIL failed while building the image block
    assert stores.db.garments() == {}
    assert stores.storage.files == {}


def test_an_insert_that_fails_uploads_nothing(upload, stores, monkeypatch, fake_model):
    # the insert comes before the upload precisely so this is cheap to undo:
    # there is no object to sweep, only a model call already paid for
    def boom(*args, **kwargs):
        raise OSError("the database is unreachable")

    monkeypatch.setattr(db, "add_photo", boom)
    fake_model({"item": "shirt", "color": "#B5C29A"})

    with pytest.raises(OSError):
        ingest(upload("shirt.jpeg"), garment_job, db.garments, USER, True)

    assert stores.storage.files == {}


def test_a_failed_upload_takes_its_row_back_out(upload, job, stores, monkeypatch, fake_model):
    # the row is written first, so a bucket that refuses leaves a row pointing
    # at nothing unless ingest undoes it
    def boom(*args, **kwargs):
        raise OSError("the bucket is unreachable")

    monkeypatch.setattr(storage, "put", boom)
    fake_model({"item": "shirt", "color": "#B5C29A"})

    with pytest.raises(OSError):
        ingest(upload("shirt.jpeg"), job, db.garments, USER, False)

    assert stores.db.garments() == {}
    assert [table for table, _ in stores.db.deleted] == ["garments"]


def test_a_failed_upload_does_not_take_out_anybody_elses_row(
    upload, job, stores, monkeypatch, fake_model
):
    # delete_photo goes by primary key, so the undo must reach exactly the row
    # this request wrote
    stores.db.seed(db.garments, USER, {"old.jpeg": ["#123456"]})

    def boom(*args, **kwargs):
        raise OSError("the bucket is unreachable")

    monkeypatch.setattr(storage, "put", boom)
    fake_model({"item": "shirt", "color": "#B5C29A"})

    with pytest.raises(OSError):
        ingest(upload("shirt.jpeg"), job, db.garments, USER, False)

    assert stores.db.garments() == {"old.jpeg": ["#123456"]}


def test_a_failed_upload_does_not_disturb_the_photos_already_saved(
    upload, job, stores, fake_model
):
    stores.db.seed(db.garments, USER, {"old.jpeg": ["#123456"]})
    fake_model(RuntimeError("the model is down"))

    with pytest.raises(RuntimeError):
        ingest(upload("shirt.jpeg"), job, db.garments, USER, True)

    assert stores.db.garments() == {"old.jpeg": ["#123456"]}
