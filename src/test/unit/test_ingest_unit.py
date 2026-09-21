"""ingest.py: one uploaded photo -> disk, web copy, model call, one row.

The route handlers are one line each, so everything worth checking about an
upload lives here. fake_model stands in for the client and fake_db for
Postgres, so no test spends money or touches a real database; the uploads
carry real JPEG bytes because web_copy and image_block both open the file
they are handed.

Which table a photo lands in is passed in rather than carried by the job, so
every call below names one: db.garments or db.palettes.
"""

import io

import pytest
from fastapi import HTTPException
from PIL import Image
from starlette.datastructures import UploadFile

from closetllm import db
from closetllm.extract import garment_job, palette_job
from closetllm.ingest import ingest, remove_broken_photo

from helpers import TEST_USER as USER, jpeg_bytes


@pytest.fixture
def upload():
    """Build an UploadFile the way Starlette hands one to the route."""

    def make(filename, content=None):
        content = jpeg_bytes() if content is None else content
        return UploadFile(file=io.BytesIO(content), filename=filename)

    return make


@pytest.fixture
def folders(tmp_path, fake_db):
    """Destination folders, deliberately not created — ingest makes them.

    fake_db is pulled in here rather than asked for test by test: every call
    to ingest() below writes a row, and an unfaked one would go looking for a
    real database.
    """
    from types import SimpleNamespace

    return SimpleNamespace(
        photos=tmp_path / "garments",
        web=tmp_path / "assets" / "garments",
    )


@pytest.fixture
def job():
    """The garment job: which model, tool and prompt to use.

    Unmodified now — the job used to carry the JSON file to write to, and
    pointing that at tmp_path was the whole reason this fixture existed. The
    destination is the table argument instead.
    """
    return garment_job


@pytest.fixture
def palette():
    return palette_job


# ----------------------------------------------------------- file type gate

@pytest.mark.parametrize("filename", ["notes.txt", "clip.mov", "archive.zip", "noext"])
def test_a_non_photo_is_rejected_as_415(filename, upload, folders, job, fake_model):
    messages = fake_model()  # any model call at all fails the test

    with pytest.raises(HTTPException) as err:
        ingest(upload(filename, b"whatever"), job, db.garments, folders.photos, None, USER)

    assert err.value.status_code == 415
    assert messages.calls == []
    # the gate has to come before the write, or the folder fills with junk
    assert not folders.photos.exists()


@pytest.mark.parametrize("filename", ["A.JPEG", "b.JPG", "c.PNG"])
def test_an_uppercase_extension_is_accepted(filename, upload, folders, job, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A"})

    result = ingest(upload(filename), job, db.garments, folders.photos, None, USER)

    assert result["name"] == filename


def test_a_filename_with_a_space_is_kept_verbatim(upload, folders, job, fake_model):
    # the UI builds its src as url_prefix + filename, so any rewrite here is a
    # broken image later
    fake_model({"item": "dress", "color": "#E4A8C0"})

    result = ingest(upload("pink dress.jpeg"), job, db.garments, folders.photos, None, USER)

    assert result["name"] == "pink dress.jpeg"
    assert (folders.photos / "pink dress.jpeg").exists()


@pytest.mark.parametrize(
    "filename",
    ["../../../etc/evil.jpeg", "/tmp/evil.jpeg", "sub/dir/evil.jpeg"],
)
def test_a_path_in_the_filename_cannot_escape_the_folder(
    filename, upload, folders, job, fake_model
):
    # the client controls this string entirely; only the last component is ours
    fake_model({"item": "shirt", "color": "#B5C29A"})

    result = ingest(upload(filename), job, db.garments, folders.photos, None, USER)

    assert result["name"] == "evil.jpeg"
    assert (folders.photos / "evil.jpeg").exists()
    assert sorted(p.name for p in folders.photos.iterdir()) == ["evil.jpeg"]


# ------------------------------------------------------------------ conflict

def test_a_filename_this_user_already_has_is_409(upload, folders, job, fake_db, fake_model):
    # the row is what makes a filename taken, not the file on disk: a photo
    # sitting in the folder with no row behind it is leftovers, and an upload
    # that matches a row must not overwrite the photo backing it
    fake_db.seed(db.garments, USER, {"shirt.jpeg": ["#123456"]})
    folders.photos.mkdir(parents=True)
    (folders.photos / "shirt.jpeg").write_bytes(b"the original")
    messages = fake_model()

    with pytest.raises(HTTPException) as err:
        ingest(upload("shirt.jpeg"), job, db.garments, folders.photos, None, USER)

    assert err.value.status_code == 409
    assert "shirt.jpeg" in err.value.detail
    assert (folders.photos / "shirt.jpeg").read_bytes() == b"the original"
    assert fake_db.garments() == {"shirt.jpeg": ["#123456"]}
    assert messages.calls == []       # refused before the model is paid for


def test_the_same_filename_under_another_user_is_allowed(upload, folders, job, fake_db, fake_model):
    # rows are owned; two people are each allowed a shirt.jpeg
    fake_db.seed(db.garments, "someone-else", {"shirt.jpeg": ["#123456"]})
    fake_model({"item": "shirt", "color": "#B5C29A"})

    result = ingest(upload("shirt.jpeg"), job, db.garments, folders.photos, None, USER)

    assert result["colors"] == ["#B5C29A"]
    assert fake_db.garments() == {"shirt.jpeg": ["#B5C29A"]}
    assert fake_db.garments("someone-else") == {"shirt.jpeg": ["#123456"]}


# ------------------------------------------------------------- writing files

def test_the_photo_lands_in_the_folder_byte_for_byte(upload, folders, job, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A"})
    content = jpeg_bytes(color=(228, 168, 192))

    ingest(upload("shirt.jpeg", content), job, db.garments, folders.photos, None, USER)

    assert (folders.photos / "shirt.jpeg").read_bytes() == content


def test_a_missing_destination_folder_is_created(upload, folders, job, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A"})
    assert not folders.photos.exists()

    ingest(upload("shirt.jpeg"), job, db.garments, folders.photos, None, USER)

    assert (folders.photos / "shirt.jpeg").exists()


# --------------------------------------------------------------- web copies

def test_a_web_copy_is_written_under_the_same_name(upload, folders, job, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A"})

    ingest(upload("shirt.jpeg"), job, db.garments, folders.photos, folders.web, USER)

    assert (folders.web / "shirt.jpeg").exists()


def test_the_web_copy_is_downscaled_not_just_duplicated(upload, folders, job, fake_model):
    from closetllm.config import web_max_edge

    fake_model({"item": "shirt", "color": "#B5C29A"})
    big = jpeg_bytes(size=(2000, 1500))

    ingest(upload("shirt.jpeg", big), job, db.garments, folders.photos, folders.web, USER)

    assert max(Image.open(folders.web / "shirt.jpeg").size) == web_max_edge
    # the original is untouched — it is what offline extraction reads
    assert Image.open(folders.photos / "shirt.jpeg").size == (2000, 1500)


def test_no_web_folder_means_no_web_copy(upload, folders, palette, fake_model):
    # palettes are uploaded with web_folder=None; nothing should be created
    fake_model({"colors": ["#B5C29A"]})

    ingest(upload("inspo.jpeg"), palette, db.palettes, folders.photos, None, USER)

    assert not folders.web.exists()


def test_a_missing_web_folder_is_created(upload, folders, job, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A"})
    assert not folders.web.exists()

    ingest(upload("shirt.jpeg"), job, db.garments, folders.photos, folders.web, USER)

    assert (folders.web / "shirt.jpeg").exists()


# --------------------------------------------------------- the model's colors

def test_a_single_color_comes_back_wrapped_in_a_list(upload, folders, job, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A"})

    assert ingest(upload("shirt.jpeg"), job, db.garments, folders.photos, None, USER) == {
        "name": "shirt.jpeg",
        "colors": ["#B5C29A"],
    }


def test_a_palettes_colors_are_all_kept(upload, folders, palette, fake_model):
    fake_model({"colors": ["#B5C29A", "#E4A8C0"]})

    result = ingest(upload("inspo.jpeg"), palette, db.palettes, folders.photos, None, USER)

    assert result["colors"] == ["#B5C29A", "#E4A8C0"]


@pytest.mark.parametrize(
    "returned, expected",
    [(" b5c29a ", "#B5C29A"), ("#abc", "#AABBCC"), ("#b5c29a", "#B5C29A")],
)
def test_the_colors_are_normalized_before_they_are_saved(
    returned, expected, upload, folders, job, fake_model
):
    # the schema asks for '#RRGGBB' but the model is not bound by it, and
    # match.py compares these strings against the committed data
    fake_model({"item": "shirt", "color": returned})

    result = ingest(upload("shirt.jpeg"), job, db.garments, folders.photos, None, USER)

    assert result["colors"] == [expected]


def test_an_empty_color_list_is_a_502(upload, folders, palette, fake_db, fake_model):
    # an empty list saves cleanly and then blows up much later inside
    # score_garment's min() — refuse the upload instead
    fake_model({"colors": []})

    with pytest.raises(HTTPException) as err:
        ingest(upload("inspo.jpeg"), palette, db.palettes, folders.photos, None, USER)

    assert err.value.status_code == 502
    assert "inspo.jpeg" in err.value.detail
    assert fake_db.palettes() == {}


def test_a_color_that_is_not_hex_is_refused(upload, folders, job, fake_db, fake_model):
    fake_model({"item": "shirt", "color": "sage green"})

    with pytest.raises(ValueError):
        ingest(upload("shirt.jpeg"), job, db.garments, folders.photos, None, USER)

    assert fake_db.garments() == {}


def test_a_model_failure_leaves_no_orphan_photo(upload, folders, job, fake_model):
    # the file is written before the call; without the cleanup the folder keeps
    # a photo that has no entry in the JSON store, and a retry then 409s
    fake_model(RuntimeError("the model is down"))

    with pytest.raises(RuntimeError):
        ingest(upload("shirt.jpeg"), job, db.garments, folders.photos, None, USER)

    assert not (folders.photos / "shirt.jpeg").exists()


def test_a_model_failure_also_removes_the_web_copy(upload, folders, job, fake_model):
    # the web copy is written before the call too, and the UI serves that one —
    # leaving it behind means a visible garment with no entry backing it
    fake_model(RuntimeError("the model is down"))

    with pytest.raises(RuntimeError):
        ingest(upload("shirt.jpeg"), job, db.garments, folders.photos, folders.web, USER)

    assert not (folders.photos / "shirt.jpeg").exists()
    assert not (folders.web / "shirt.jpeg").exists()


def test_a_retry_after_a_model_failure_succeeds(upload, folders, job, fake_model):
    fake_model(RuntimeError("the model is down"), {"item": "shirt", "color": "#B5C29A"})

    with pytest.raises(RuntimeError):
        ingest(upload("shirt.jpeg"), job, db.garments, folders.photos, None, USER)

    result = ingest(upload("shirt.jpeg"), job, db.garments, folders.photos, None, USER)
    assert result["colors"] == ["#B5C29A"]


# ----------------------------------------------------------------- the row

def test_the_row_is_written_for_the_uploading_user(upload, folders, job, fake_db, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A"})

    ingest(upload("shirt.jpeg"), job, db.garments, folders.photos, None, USER)

    assert fake_db.garments() == {"shirt.jpeg": ["#B5C29A"]}
    assert fake_db.calls == [
        {
            "table": "garments",
            "user_id": USER,
            "filename": "shirt.jpeg",
            "colors": ["#B5C29A"],
            # the photo is stored under its own name; the column exists so the
            # bytes can move to object storage later without renaming anything
            "storage_key": "shirt.jpeg",
        }
    ]


def test_an_upload_does_not_disturb_the_photos_already_saved(
    upload, folders, job, fake_db, fake_model
):
    fake_db.seed(db.garments, USER, {"old.jpeg": ["#123456"]})
    fake_model({"item": "shirt", "color": "#B5C29A"})

    ingest(upload("shirt.jpeg"), job, db.garments, folders.photos, None, USER)

    assert fake_db.garments() == {
        "old.jpeg": ["#123456"],
        "shirt.jpeg": ["#B5C29A"],
    }


def test_two_uploads_both_land(upload, folders, job, fake_db, fake_model):
    fake_model({"item": "a", "color": "#B5C29A"}, {"item": "b", "color": "#E4A8C0"})

    ingest(upload("a.jpeg"), job, db.garments, folders.photos, None, USER)
    ingest(upload("b.jpeg"), job, db.garments, folders.photos, None, USER)

    assert fake_db.garments() == {"a.jpeg": ["#B5C29A"], "b.jpeg": ["#E4A8C0"]}


def test_a_garment_and_a_palette_write_to_different_tables(
    upload, folders, job, palette, fake_db, fake_model
):
    # the table is the argument that routes them; crossing it would file a
    # garment as an inspiration palette
    fake_model({"item": "shirt", "color": "#B5C29A"}, {"colors": ["#E4A8C0"]})

    ingest(upload("shirt.jpeg"), job, db.garments, folders.photos, None, USER)
    ingest(upload("inspo.jpeg"), palette, db.palettes, folders.photos, None, USER)

    assert fake_db.garments() == {"shirt.jpeg": ["#B5C29A"]}
    assert fake_db.palettes() == {"inspo.jpeg": ["#E4A8C0"]}


# ------------------------------------------------------------- the model call

def test_the_job_decides_which_model_and_tool_are_used(
    upload, folders, palette, fake_model
):
    messages = fake_model({"colors": ["#B5C29A"]})

    ingest(upload("inspo.jpeg"), palette, db.palettes, folders.photos, None, USER)

    sent = messages.calls[0]
    assert sent["model"] == palette.model
    assert sent["tool_choice"] == {"type": "tool", "name": "extract_colors"}


def test_the_model_sees_the_saved_photo_exactly_once(upload, folders, job, fake_model):
    messages = fake_model({"item": "shirt", "color": "#B5C29A"})

    ingest(upload("shirt.jpeg"), job, db.garments, folders.photos, None, USER)

    assert len(messages.calls) == 1
    assert messages.calls[0]["messages"][0]["content"][0]["type"] == "image"


# ------------------------------------------------- cleanup on the later steps

def test_an_empty_color_list_removes_both_copies(upload, folders, palette, fake_model):
    # the 502 is raised after the photo and its web copy are on disk, so it has
    # to clean up like any other failure — otherwise a retry hits the 409
    fake_model({"colors": []})

    with pytest.raises(HTTPException):
        ingest(upload("inspo.jpeg"), palette, db.palettes, folders.photos, folders.web, USER)

    assert not (folders.photos / "inspo.jpeg").exists()
    assert not (folders.web / "inspo.jpeg").exists()


def test_a_bad_hex_removes_both_copies(upload, folders, job, fake_model):
    fake_model({"item": "shirt", "color": "sage green"})

    with pytest.raises(ValueError):
        ingest(upload("shirt.jpeg"), job, db.garments, folders.photos, folders.web, USER)

    assert not (folders.photos / "shirt.jpeg").exists()
    assert not (folders.web / "shirt.jpeg").exists()


def test_a_retry_after_a_502_is_not_blocked_by_a_409(upload, folders, palette, fake_model):
    # the whole point of cleaning up: the second attempt must look like a first
    fake_model({"colors": []}, {"colors": ["#B5C29A"]})

    with pytest.raises(HTTPException) as err:
        ingest(upload("inspo.jpeg"), palette, db.palettes, folders.photos, folders.web, USER)
    assert err.value.status_code == 502

    result = ingest(upload("inspo.jpeg"), palette, db.palettes, folders.photos, folders.web, USER)
    assert result["colors"] == ["#B5C29A"]


def test_a_file_that_is_not_really_a_photo_is_cleaned_up(upload, folders, job, fake_db, fake_model):
    # the gate checks the extension, not the bytes; PIL is what finds out, and
    # by then the file is already written
    messages = fake_model()
    payload = upload("shirt.jpeg", b"this is not a JPEG")

    with pytest.raises(Exception):
        ingest(payload, job, db.garments, folders.photos, folders.web, USER)

    assert not (folders.photos / "shirt.jpeg").exists()
    assert not (folders.web / "shirt.jpeg").exists()
    assert messages.calls == []       # PIL failed while building the image block
    assert fake_db.garments() == {}


def test_an_insert_that_fails_leaves_no_orphan(upload, folders, monkeypatch, fake_model):
    # the insert is the last thing to run and the model has already been paid
    # for by then; a photo left behind would have nothing pointing at it
    def boom(*args, **kwargs):
        raise OSError("the database is unreachable")

    monkeypatch.setattr(db, "add_photo", boom)
    fake_model({"item": "shirt", "color": "#B5C29A"})

    with pytest.raises(OSError):
        ingest(upload("shirt.jpeg"), garment_job, db.garments, folders.photos, folders.web, USER)

    assert not (folders.photos / "shirt.jpeg").exists()
    assert not (folders.web / "shirt.jpeg").exists()
    assert list(folders.photos.iterdir()) == []      # not even the staged copy


def test_a_409_from_the_constraint_does_not_touch_the_photo_already_there(
    upload, folders, job, fake_db, monkeypatch, fake_model
):
    # the pre-check is only a fast path — two requests can both pass it, and the
    # loser finds out from the unique constraint after its photo is written. It
    # is written under a staging name for exactly this reason: cleaning up must
    # not delete the photo the upload collided with.
    folders.photos.mkdir(parents=True)
    folders.web.mkdir(parents=True)
    (folders.photos / "shirt.jpeg").write_bytes(b"the original")
    (folders.web / "shirt.jpeg").write_bytes(b"the original web copy")
    monkeypatch.setattr(db, "load_user_colors", lambda table, user_id: {})   # lose the race
    fake_db.seed(db.garments, USER, {"shirt.jpeg": ["#123456"]})
    fake_model({"item": "shirt", "color": "#B5C29A"})

    with pytest.raises(HTTPException) as err:
        ingest(upload("shirt.jpeg"), job, db.garments, folders.photos, folders.web, USER)

    assert err.value.status_code == 409
    assert (folders.photos / "shirt.jpeg").read_bytes() == b"the original"
    assert (folders.web / "shirt.jpeg").read_bytes() == b"the original web copy"
    assert sorted(p.name for p in folders.photos.iterdir()) == ["shirt.jpeg"]
    assert fake_db.garments() == {"shirt.jpeg": ["#123456"]}


def test_a_failed_upload_does_not_disturb_the_photos_already_saved(
    upload, folders, job, fake_db, fake_model
):
    fake_db.seed(db.garments, USER, {"old.jpeg": ["#123456"]})
    folders.photos.mkdir(parents=True)
    (folders.photos / "old.jpeg").write_bytes(jpeg_bytes())
    fake_model(RuntimeError("the model is down"))

    with pytest.raises(RuntimeError):
        ingest(upload("shirt.jpeg"), job, db.garments, folders.photos, folders.web, USER)

    assert (folders.photos / "old.jpeg").exists()
    assert fake_db.garments() == {"old.jpeg": ["#123456"]}


# ------------------------------------------------------- remove_broken_photo

def test_remove_broken_photo_deletes_the_photo(tmp_path):
    photo = tmp_path / "shirt.jpeg"
    photo.write_bytes(jpeg_bytes())

    remove_broken_photo(photo, None)

    assert not photo.exists()


def test_remove_broken_photo_deletes_the_web_copy_under_the_same_name(tmp_path):
    photo = tmp_path / "garments" / "shirt.jpeg"
    web = tmp_path / "assets"
    photo.parent.mkdir()
    web.mkdir()
    photo.write_bytes(jpeg_bytes())
    (web / "shirt.jpeg").write_bytes(jpeg_bytes())

    remove_broken_photo(photo, web)

    assert not photo.exists()
    assert not (web / "shirt.jpeg").exists()


def test_remove_broken_photo_tolerates_a_photo_that_was_never_written(tmp_path):
    # the caller does not know how far it got, so both deletes have to be safe
    remove_broken_photo(tmp_path / "never.jpeg", None)


def test_remove_broken_photo_tolerates_a_missing_web_copy(tmp_path):
    # the common case: the failure happened before web_copy ran at all
    photo = tmp_path / "shirt.jpeg"
    photo.write_bytes(jpeg_bytes())

    remove_broken_photo(photo, tmp_path / "assets")

    assert not photo.exists()


def test_remove_broken_photo_leaves_the_other_photos_alone(tmp_path):
    keep = tmp_path / "keep.jpeg"
    drop = tmp_path / "drop.jpeg"
    keep.write_bytes(jpeg_bytes())
    drop.write_bytes(jpeg_bytes())

    remove_broken_photo(drop, None)

    assert keep.exists()
