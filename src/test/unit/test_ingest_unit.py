"""ingest.py: one uploaded photo -> disk, web copy, model call, JSON store.

The route handlers are one line each, so everything worth checking about an
upload lives here. fake_model stands in for the client, so no test spends
money; the uploads carry real JPEG bytes because web_copy and image_block
both open the file they are handed.
"""

import dataclasses
import io

import pytest
from fastapi import HTTPException
from PIL import Image
from starlette.datastructures import UploadFile

from closetllm.extract import garment_job, load_data, palette_job, save_data
from closetllm.ingest import ingest, remove_broken_photo

from helpers import jpeg_bytes


@pytest.fixture
def upload():
    """Build an UploadFile the way Starlette hands one to the route."""

    def make(filename, content=None):
        content = jpeg_bytes() if content is None else content
        return UploadFile(file=io.BytesIO(content), filename=filename)

    return make


@pytest.fixture
def folders(tmp_path):
    """Destination folders, deliberately not created — ingest makes them."""
    from types import SimpleNamespace

    return SimpleNamespace(
        photos=tmp_path / "garments",
        web=tmp_path / "assets" / "garments",
    )


@pytest.fixture
def job(tmp_path):
    """garment_job, pointed at a throwaway JSON store."""
    return dataclasses.replace(garment_job, json_data=tmp_path / "garments.json")


@pytest.fixture
def palette(tmp_path):
    return dataclasses.replace(palette_job, json_data=tmp_path / "colors.json")


# ----------------------------------------------------------- file type gate

@pytest.mark.parametrize("filename", ["notes.txt", "clip.mov", "archive.zip", "noext"])
def test_a_non_photo_is_rejected_as_415(filename, upload, folders, job, fake_model):
    messages = fake_model()  # any model call at all fails the test

    with pytest.raises(HTTPException) as err:
        ingest(upload(filename, b"whatever"), job, folders.photos, None)

    assert err.value.status_code == 415
    assert messages.calls == []
    # the gate has to come before the write, or the folder fills with junk
    assert not folders.photos.exists()


@pytest.mark.parametrize("filename", ["A.JPEG", "b.JPG", "c.PNG"])
def test_an_uppercase_extension_is_accepted(filename, upload, folders, job, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A"})

    result = ingest(upload(filename), job, folders.photos, None)

    assert result["name"] == filename


def test_a_filename_with_a_space_is_kept_verbatim(upload, folders, job, fake_model):
    # the UI builds its src as url_prefix + filename, so any rewrite here is a
    # broken image later
    fake_model({"item": "dress", "color": "#E4A8C0"})

    result = ingest(upload("pink dress.jpeg"), job, folders.photos, None)

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

    result = ingest(upload(filename), job, folders.photos, None)

    assert result["name"] == "evil.jpeg"
    assert (folders.photos / "evil.jpeg").exists()
    assert sorted(p.name for p in folders.photos.iterdir()) == ["evil.jpeg"]


# ------------------------------------------------------------------ conflict

def test_an_existing_photo_is_rejected_as_409(upload, folders, job, fake_model):
    folders.photos.mkdir(parents=True)
    (folders.photos / "shirt.jpeg").write_bytes(b"the original")
    messages = fake_model()

    with pytest.raises(HTTPException) as err:
        ingest(upload("shirt.jpeg"), job, folders.photos, None)

    assert err.value.status_code == 409
    assert "shirt.jpeg" in err.value.detail
    # overwriting would silently replace a photo whose colors are already saved
    assert (folders.photos / "shirt.jpeg").read_bytes() == b"the original"
    assert messages.calls == []


# ------------------------------------------------------------- writing files

def test_the_photo_lands_in_the_folder_byte_for_byte(upload, folders, job, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A"})
    content = jpeg_bytes(color=(228, 168, 192))

    ingest(upload("shirt.jpeg", content), job, folders.photos, None)

    assert (folders.photos / "shirt.jpeg").read_bytes() == content


def test_a_missing_destination_folder_is_created(upload, folders, job, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A"})
    assert not folders.photos.exists()

    ingest(upload("shirt.jpeg"), job, folders.photos, None)

    assert (folders.photos / "shirt.jpeg").exists()


# --------------------------------------------------------------- web copies

def test_a_web_copy_is_written_under_the_same_name(upload, folders, job, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A"})

    ingest(upload("shirt.jpeg"), job, folders.photos, folders.web)

    assert (folders.web / "shirt.jpeg").exists()


def test_the_web_copy_is_downscaled_not_just_duplicated(upload, folders, job, fake_model):
    from closetllm.config import web_max_edge

    fake_model({"item": "shirt", "color": "#B5C29A"})
    big = jpeg_bytes(size=(2000, 1500))

    ingest(upload("shirt.jpeg", big), job, folders.photos, folders.web)

    assert max(Image.open(folders.web / "shirt.jpeg").size) == web_max_edge
    # the original is untouched — it is what offline extraction reads
    assert Image.open(folders.photos / "shirt.jpeg").size == (2000, 1500)


def test_no_web_folder_means_no_web_copy(upload, folders, palette, fake_model):
    # palettes are uploaded with web_folder=None; nothing should be created
    fake_model({"colors": ["#B5C29A"]})

    ingest(upload("inspo.jpeg"), palette, folders.photos, None)

    assert not folders.web.exists()


def test_a_missing_web_folder_is_created(upload, folders, job, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A"})
    assert not folders.web.exists()

    ingest(upload("shirt.jpeg"), job, folders.photos, folders.web)

    assert (folders.web / "shirt.jpeg").exists()


# --------------------------------------------------------- the model's colors

def test_a_single_color_comes_back_wrapped_in_a_list(upload, folders, job, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A"})

    assert ingest(upload("shirt.jpeg"), job, folders.photos, None) == {
        "name": "shirt.jpeg",
        "colors": ["#B5C29A"],
    }


def test_a_palettes_colors_are_all_kept(upload, folders, palette, fake_model):
    fake_model({"colors": ["#B5C29A", "#E4A8C0"]})

    result = ingest(upload("inspo.jpeg"), palette, folders.photos, None)

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

    result = ingest(upload("shirt.jpeg"), job, folders.photos, None)

    assert result["colors"] == [expected]


def test_an_empty_color_list_is_a_502(upload, folders, palette, fake_model):
    # an empty list saves cleanly and then blows up much later inside
    # score_garment's min() — refuse the upload instead
    fake_model({"colors": []})

    with pytest.raises(HTTPException) as err:
        ingest(upload("inspo.jpeg"), palette, folders.photos, None)

    assert err.value.status_code == 502
    assert "inspo.jpeg" in err.value.detail
    assert load_data(palette.json_data) == {}


def test_a_color_that_is_not_hex_is_refused(upload, folders, job, fake_model):
    fake_model({"item": "shirt", "color": "sage green"})

    with pytest.raises(ValueError):
        ingest(upload("shirt.jpeg"), job, folders.photos, None)

    assert load_data(job.json_data) == {}


def test_a_model_failure_leaves_no_orphan_photo(upload, folders, job, fake_model):
    # the file is written before the call; without the cleanup the folder keeps
    # a photo that has no entry in the JSON store, and a retry then 409s
    fake_model(RuntimeError("the model is down"))

    with pytest.raises(RuntimeError):
        ingest(upload("shirt.jpeg"), job, folders.photos, None)

    assert not (folders.photos / "shirt.jpeg").exists()


def test_a_model_failure_also_removes_the_web_copy(upload, folders, job, fake_model):
    # the web copy is written before the call too, and the UI serves that one —
    # leaving it behind means a visible garment with no entry backing it
    fake_model(RuntimeError("the model is down"))

    with pytest.raises(RuntimeError):
        ingest(upload("shirt.jpeg"), job, folders.photos, folders.web)

    assert not (folders.photos / "shirt.jpeg").exists()
    assert not (folders.web / "shirt.jpeg").exists()


def test_a_retry_after_a_model_failure_succeeds(upload, folders, job, fake_model):
    fake_model(RuntimeError("the model is down"), {"item": "shirt", "color": "#B5C29A"})

    with pytest.raises(RuntimeError):
        ingest(upload("shirt.jpeg"), job, folders.photos, None)

    result = ingest(upload("shirt.jpeg"), job, folders.photos, None)
    assert result["colors"] == ["#B5C29A"]


# ------------------------------------------------------------- the JSON store

def test_the_entry_is_written_to_the_jobs_store(upload, folders, job, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A"})

    ingest(upload("shirt.jpeg"), job, folders.photos, None)

    assert load_data(job.json_data) == {"shirt.jpeg": ["#B5C29A"]}


def test_an_upload_does_not_disturb_the_photos_already_saved(
    upload, folders, job, fake_model
):
    save_data({"old.jpeg": ["#123456"]}, job.json_data)
    fake_model({"item": "shirt", "color": "#B5C29A"})

    ingest(upload("shirt.jpeg"), job, folders.photos, None)

    assert load_data(job.json_data) == {
        "old.jpeg": ["#123456"],
        "shirt.jpeg": ["#B5C29A"],
    }


def test_two_uploads_both_land(upload, folders, job, fake_model):
    fake_model({"item": "a", "color": "#B5C29A"}, {"item": "b", "color": "#E4A8C0"})

    ingest(upload("a.jpeg"), job, folders.photos, None)
    ingest(upload("b.jpeg"), job, folders.photos, None)

    assert load_data(job.json_data) == {"a.jpeg": ["#B5C29A"], "b.jpeg": ["#E4A8C0"]}


def test_a_garment_and_a_palette_write_to_different_stores(
    upload, folders, job, palette, fake_model
):
    fake_model({"item": "shirt", "color": "#B5C29A"}, {"colors": ["#E4A8C0"]})

    ingest(upload("shirt.jpeg"), job, folders.photos, None)
    ingest(upload("inspo.jpeg"), palette, folders.photos, None)

    assert load_data(job.json_data) == {"shirt.jpeg": ["#B5C29A"]}
    assert load_data(palette.json_data) == {"inspo.jpeg": ["#E4A8C0"]}


# ------------------------------------------------------------- the model call

def test_the_job_decides_which_model_and_tool_are_used(
    upload, folders, palette, fake_model
):
    messages = fake_model({"colors": ["#B5C29A"]})

    ingest(upload("inspo.jpeg"), palette, folders.photos, None)

    sent = messages.calls[0]
    assert sent["model"] == palette.model
    assert sent["tool_choice"] == {"type": "tool", "name": "extract_colors"}


def test_the_model_sees_the_saved_photo_exactly_once(upload, folders, job, fake_model):
    messages = fake_model({"item": "shirt", "color": "#B5C29A"})

    ingest(upload("shirt.jpeg"), job, folders.photos, None)

    assert len(messages.calls) == 1
    assert messages.calls[0]["messages"][0]["content"][0]["type"] == "image"


# ------------------------------------------------- cleanup on the later steps

def test_an_empty_color_list_removes_both_copies(upload, folders, palette, fake_model):
    # the 502 is raised after the photo and its web copy are on disk, so it has
    # to clean up like any other failure — otherwise a retry hits the 409
    fake_model({"colors": []})

    with pytest.raises(HTTPException):
        ingest(upload("inspo.jpeg"), palette, folders.photos, folders.web)

    assert not (folders.photos / "inspo.jpeg").exists()
    assert not (folders.web / "inspo.jpeg").exists()


def test_a_bad_hex_removes_both_copies(upload, folders, job, fake_model):
    fake_model({"item": "shirt", "color": "sage green"})

    with pytest.raises(ValueError):
        ingest(upload("shirt.jpeg"), job, folders.photos, folders.web)

    assert not (folders.photos / "shirt.jpeg").exists()
    assert not (folders.web / "shirt.jpeg").exists()


def test_a_retry_after_a_502_is_not_blocked_by_a_409(upload, folders, palette, fake_model):
    # the whole point of cleaning up: the second attempt must look like a first
    fake_model({"colors": []}, {"colors": ["#B5C29A"]})

    with pytest.raises(HTTPException) as err:
        ingest(upload("inspo.jpeg"), palette, folders.photos, folders.web)
    assert err.value.status_code == 502

    result = ingest(upload("inspo.jpeg"), palette, folders.photos, folders.web)
    assert result["colors"] == ["#B5C29A"]


def test_a_file_that_is_not_really_a_photo_is_cleaned_up(upload, folders, job, fake_model):
    # the gate checks the extension, not the bytes; PIL is what finds out, and
    # by then the file is already written
    messages = fake_model()
    payload = upload("shirt.jpeg", b"this is not a JPEG")

    with pytest.raises(Exception):
        ingest(payload, job, folders.photos, folders.web)

    assert not (folders.photos / "shirt.jpeg").exists()
    assert not (folders.web / "shirt.jpeg").exists()
    assert messages.calls == []       # web_copy failed before the call
    assert load_data(job.json_data) == {}


def test_a_store_that_cannot_be_written_leaves_no_orphan(upload, folders, tmp_path, fake_model):
    # save_data mkdirs the parent; a file sitting where that directory belongs
    # makes the write fail after the model has already been paid for
    (tmp_path / "blocked").write_text("not a directory")
    job = dataclasses.replace(garment_job, json_data=tmp_path / "blocked" / "garments.json")
    fake_model({"item": "shirt", "color": "#B5C29A"})

    with pytest.raises(OSError):
        ingest(upload("shirt.jpeg"), job, folders.photos, folders.web)

    assert not (folders.photos / "shirt.jpeg").exists()
    assert not (folders.web / "shirt.jpeg").exists()


def test_a_409_does_not_touch_the_photo_already_there(upload, folders, job, fake_model):
    # the conflict is raised before the try, and it must stay there: cleaning up
    # on a 409 would delete the very photo the upload collided with
    folders.photos.mkdir(parents=True)
    folders.web.mkdir(parents=True)
    (folders.photos / "shirt.jpeg").write_bytes(b"the original")
    (folders.web / "shirt.jpeg").write_bytes(b"the original web copy")
    fake_model()

    with pytest.raises(HTTPException) as err:
        ingest(upload("shirt.jpeg"), job, folders.photos, folders.web)

    assert err.value.status_code == 409
    assert (folders.photos / "shirt.jpeg").read_bytes() == b"the original"
    assert (folders.web / "shirt.jpeg").read_bytes() == b"the original web copy"


def test_a_failed_upload_does_not_disturb_the_photos_already_saved(
    upload, folders, job, fake_model
):
    save_data({"old.jpeg": ["#123456"]}, job.json_data)
    folders.photos.mkdir(parents=True)
    (folders.photos / "old.jpeg").write_bytes(jpeg_bytes())
    fake_model(RuntimeError("the model is down"))

    with pytest.raises(RuntimeError):
        ingest(upload("shirt.jpeg"), job, folders.photos, folders.web)

    assert (folders.photos / "old.jpeg").exists()
    assert load_data(job.json_data) == {"old.jpeg": ["#123456"]}


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
