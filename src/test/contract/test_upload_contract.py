"""POST /upload-garments and /upload-palettes: the upload half of the HTTP surface.

What ingest() does with a photo is covered in unit/test_ingest_unit.py. These
tests care about the envelope — status codes, the JSON body, and that each
route is wired to the job, folder and store it claims to be.

upload_paths is not optional here: without it these tests would write real
photos into garments/ and real entries into data/garments.json.
"""

import pytest

from closetllm.extract import load_data

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

def test_a_garment_lands_in_the_garment_folder_and_store(client, upload_paths, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A"})

    client.post("/upload-garments", files=photo())

    assert (upload_paths.garments / "shirt.jpeg").exists()
    assert load_data(upload_paths.garments_json) == {"shirt.jpeg": ["#B5C29A"]}
    # wrong store would mean the garment shows up as an inspiration palette
    assert load_data(upload_paths.palettes_json) == {}


def test_a_garment_upload_writes_the_web_copy_the_ui_serves(client, upload_paths, fake_model):
    # /img/garments is mounted on the web folder, not on garments/ — an upload
    # that skipped this step would 404 in the browser
    fake_model({"item": "shirt", "color": "#B5C29A"})

    client.post("/upload-garments", files=photo())

    assert (upload_paths.web_garments / "shirt.jpeg").exists()


def test_a_palette_lands_in_the_palette_folder_and_store(client, upload_paths, fake_model):
    fake_model({"colors": ["#B5C29A"]})

    client.post("/upload-palettes", files=photo("inspo.jpeg"))

    assert (upload_paths.palettes / "inspo.jpeg").exists()
    assert load_data(upload_paths.palettes_json) == {"inspo.jpeg": ["#B5C29A"]}
    assert load_data(upload_paths.garments_json) == {}


def test_a_palette_gets_no_web_copy(client, upload_paths, fake_model):
    # palettes are passed web_folder=None; only garments are served to the UI
    fake_model({"colors": ["#B5C29A"]})

    client.post("/upload-palettes", files=photo("inspo.jpeg"))

    assert not upload_paths.web_garments.exists()


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
    assert response.json() == {"detail": "unsupported type"}


@pytest.mark.parametrize("route", ["/upload-garments", "/upload-palettes"])
def test_uploading_the_same_photo_twice_is_409(route, client, upload_paths, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A", "colors": ["#B5C29A"]})

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

    assert load_data(upload_paths.garments_json) == {}
    assert load_data(upload_paths.palettes_json) == {}


# ---------------------------------------------------------- the round trip

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
