"""POST /upload-garments and /upload-palettes: the upload half of the HTTP surface.

What ingest() does with a photo is covered in unit/test_ingest_unit.py. These
tests care about the envelope — status codes, the JSON body, and that each
route is wired to the job, table and bucket prefix it claims to be.

upload_paths is not optional here: without it these tests would put real
photos in the bucket and real rows in the database the closet lives in. It
carries both fakes, as upload_paths.db and upload_paths.storage.
"""

import io

import pytest
from PIL import Image

from helpers import jpeg_bytes


def photo(name="shirt.jpeg", content=None, content_type="image/jpeg"):
    """The multipart payload TestClient wants."""
    return {"file": (name, jpeg_bytes() if content is None else content, content_type)}


# ------------------------------------------------------------ the happy path

def test_a_garment_upload_is_201_with_the_name_and_colors(client, upload_paths, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A"})

    response = client.post("/upload-garments", files=photo())

    assert response.status_code == 201
    assert response.json() == {"name": "shirt.jpeg", "colors": ["#B5C29A"]}


def test_a_palette_upload_is_201_with_every_colour(client, upload_paths, fake_model):
    fake_model({"colors": ["#B5C29A", "#E4A8C0"]})

    response = client.post("/upload-palettes", files=photo("inspo.jpeg"))

    assert response.status_code == 201
    assert response.json() == {
        "name": "inspo.jpeg",
        "colors": ["#B5C29A", "#E4A8C0"],
    }


# --------------------------------------------------------------- the wiring

def uploaded(upload_paths):
    """The one object the request put in the bucket, as (key, bytes)."""
    files = upload_paths.storage.files
    assert len(files) == 1, files
    return next(iter(files.items()))


def test_a_garment_lands_under_the_garment_prefix_and_table(client, upload_paths, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A"})

    client.post("/upload-garments", files=photo())

    key, _ = uploaded(upload_paths)
    assert key.startswith("garments/")
    assert upload_paths.db.garments() == {"shirt.jpeg": ["#B5C29A"]}
    # the wrong table would mean the garment shows up as an inspiration palette
    assert upload_paths.db.palettes() == {}


def test_a_garment_upload_stores_the_web_copy_the_ui_serves(client, upload_paths, fake_model):
    # the UI draws garments at ~70px, so the route asks ingest for the
    # downscaled copy; uploading the phone original would be megabytes a tile
    from closetllm.config import web_max_edge

    fake_model({"item": "shirt", "color": "#B5C29A"})

    client.post("/upload-garments", files=photo(content=jpeg_bytes(size=(2000, 1500))))

    _, data = uploaded(upload_paths)
    assert max(Image.open(io.BytesIO(data)).size) == web_max_edge


def test_a_palette_lands_under_the_palette_prefix_and_table(client, upload_paths, fake_model):
    fake_model({"colors": ["#B5C29A"]})

    client.post("/upload-palettes", files=photo("inspo.jpeg"))

    key, _ = uploaded(upload_paths)
    assert key.startswith("palettes/")
    assert upload_paths.db.palettes() == {"inspo.jpeg": ["#B5C29A"]}
    assert upload_paths.db.garments() == {}


def test_a_palette_is_stored_at_full_size(client, upload_paths, fake_model):
    # the route passes needs_web_copy=False: a palette is the thing you look
    # at, not a thumbnail in a grid
    fake_model({"colors": ["#B5C29A"]})
    original = jpeg_bytes(size=(2000, 1500))

    client.post("/upload-palettes", files=photo("inspo.jpeg", original))

    _, data = uploaded(upload_paths)
    assert Image.open(io.BytesIO(data)).size == (2000, 1500)


def test_the_row_is_filed_under_the_signed_in_user(client, upload_paths, fake_model):
    # the handler takes the id from current_user; a hardcoded or missing owner
    # would put every upload in one pile
    from helpers import TEST_USER

    fake_model({"item": "shirt", "color": "#B5C29A"})

    client.post("/upload-garments", files=photo())

    assert [call["user_id"] for call in upload_paths.db.calls] == [TEST_USER]


def test_each_route_uses_its_own_job(client, upload_paths, fake_model):
    # the two jobs name different tools and different models; crossing them
    # would ask for one dominant colour and get a two-colour palette back
    messages = fake_model(
        {"item": "shirt", "color": "#B5C29A"}, {"colors": ["#E4A8C0"]}
    )

    client.post("/upload-garments", files=photo())
    client.post("/upload-palettes", files=photo("inspo.jpeg"))

    garment_call, palette_call = messages.calls
    assert garment_call["tool_choice"]["name"] == "extract_clothing_colors"
    assert palette_call["tool_choice"]["name"] == "extract_colors"


# ---------------------------------------------------------------- the errors

@pytest.mark.parametrize("route", ["/upload-garments", "/upload-palettes"])
def test_a_non_photo_is_415_with_a_detail(route, client, upload_paths, fake_model):
    fake_model()

    response = client.post(route, files=photo("notes.txt", b"hello", "text/plain"))

    assert response.status_code == 415
    assert "unsupported type" in response.json()["detail"]


@pytest.mark.parametrize("route", ["/upload-garments", "/upload-palettes"])
def test_uploading_the_same_photo_twice_is_409(route, client, upload_paths, fake_model):
    # two replies, not one: the unique constraint is what refuses the second
    # upload, and it only speaks once the colors are already back
    reply = {"item": "shirt", "color": "#B5C29A", "colors": ["#B5C29A"]}
    fake_model(reply, reply)

    assert client.post(route, files=photo()).status_code == 201
    response = client.post(route, files=photo())

    assert response.status_code == 409
    assert "shirt.jpeg" in response.json()["detail"]


def test_a_model_that_returns_no_colors_is_502(client, upload_paths, fake_model):
    fake_model({"colors": []})

    response = client.post("/upload-palettes", files=photo("inspo.jpeg"))

    assert response.status_code == 502
    assert "inspo.jpeg" in response.json()["detail"]


@pytest.mark.parametrize("route", ["/upload-garments", "/upload-palettes"])
def test_a_request_with_no_file_is_422(route, client, upload_paths):
    # FastAPI validates the multipart field before ingest() ever runs
    assert client.post(route).status_code == 422


@pytest.mark.parametrize("route", ["/upload-garments", "/upload-palettes"])
def test_a_rejected_upload_leaves_nothing_behind(route, client, upload_paths, fake_model):
    fake_model()

    client.post(route, files=photo("notes.txt", b"hello", "text/plain"))

    assert upload_paths.db.garments() == {}
    assert upload_paths.db.palettes() == {}


# ---------------------------------------------------------- the round trip
#
# These two were xfail while the read routes still served data/garments.json
# and an upload wrote a row, so nothing an upload did was visible to a GET.
# Both halves read the same table now, which is what closes the loop.


def test_an_uploaded_garment_shows_up_in_get_garments(client, upload_paths, fake_model):
    # /garments is a 404 on an empty store, so this closes the loop: the upload
    # is what makes the store non-empty
    fake_model({"item": "shirt", "color": "#B5C29A"})
    assert client.get("/garments").status_code == 404

    client.post("/upload-garments", files=photo())

    response = client.get("/garments")
    assert response.status_code == 200
    assert response.json() == {"count": 1, "garments": {"shirt.jpeg": ["#B5C29A"]}}


def test_an_uploaded_palette_shows_up_in_get_color_palettes(client, upload_paths, fake_model):
    fake_model({"colors": ["#B5C29A"]})

    client.post("/upload-palettes", files=photo("inspo.jpeg"))

    response = client.get("/color-palettes")
    assert response.status_code == 200
    assert response.json()["palettes"] == {"inspo.jpeg": ["#B5C29A"]}


# -------------------------------------------------------------- route surface

@pytest.mark.parametrize("route", ["/upload-garments", "/upload-palettes"])
def test_the_upload_routes_are_documented(route, client):
    assert route in client.app.openapi()["paths"]


@pytest.mark.parametrize("route", ["/upload-garments", "/upload-palettes"])
def test_the_upload_routes_are_post_only(route, client):
    # asserted against the schema rather than a live GET: the catch-all UI
    # mount answers unmatched GETs when src/ui/dist has been built, so the
    # status code is 404 or 405 depending on whether anyone ran `npm run build`
    assert list(client.app.openapi()["paths"][route]) == ["post"]


@pytest.mark.parametrize("route", ["/upload-garments", "/upload-palettes"])
def test_the_upload_routes_document_their_201(route, client):
    # the UI branches on the status code; 201 is the documented success, not 200
    assert "201" in client.app.openapi()["paths"][route]["post"]["responses"]
