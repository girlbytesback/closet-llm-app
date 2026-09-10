"""The contract between the tool schemas we send and the code that reads the
result back, plus the config values both sides depend on.

These are the pieces nothing else can catch: a tool schema can be edited to
something perfectly valid that the parsing code no longer understands, and the
failure only shows up as a KeyError after a paid API call.
"""

import pytest

from closetllm import config
from closetllm.extract import ExtractPhotoDetails, garment_job, palette_job

JOBS = [pytest.param(palette_job, id="palette"), pytest.param(garment_job, id="garment")]


@pytest.mark.parametrize("job", JOBS)
def test_tool_name_is_read_off_the_tool_itself(job):
    # tool_choice and the error message both use it; a second copy could drift
    assert job.tool_name == job.tool["name"]


@pytest.mark.parametrize("job", JOBS)
def test_the_schema_declares_the_key_the_code_reads(job):
    # extract.run does result[job.colors_key] — an unlisted key is a KeyError
    assert job.colors_key in job.tool["input_schema"]["properties"]


@pytest.mark.parametrize("job", JOBS)
def test_the_colours_key_is_required_so_it_is_always_present(job):
    assert job.colors_key in job.tool["input_schema"]["required"]


@pytest.mark.parametrize("job", JOBS)
def test_the_schema_is_a_well_formed_object_schema(job):
    schema = job.tool["input_schema"]

    assert schema["type"] == "object"
    assert isinstance(schema["properties"], dict) and schema["properties"]
    assert set(schema["required"]) <= set(schema["properties"])


@pytest.mark.parametrize("job", JOBS)
def test_every_tool_has_a_description(job):
    # the description is what the model reads to decide what to put in the fields
    assert job.tool["description"]
    assert all(p.get("description") for p in job.tool["input_schema"]["properties"].values())


@pytest.mark.parametrize("job", JOBS)
def test_every_job_names_a_model_and_a_prompt(job):
    assert job.model.startswith("claude-")
    assert job.prompt.strip()


def test_the_two_jobs_use_different_tool_names(job=None):
    # they are distinguishable in the transcript and in error messages
    assert palette_job.tool_name != garment_job.tool_name


def test_the_palette_job_asks_for_a_list(): 
    prop = palette_job.tool["input_schema"]["properties"]["colors"]
    assert prop["type"] == "array"
    assert prop["items"]["type"] == "string"


def test_the_garment_job_asks_for_one_string(): 
    assert garment_job.tool["input_schema"]["properties"]["color"]["type"] == "string"


def test_the_garment_prompt_tells_the_model_to_ignore_the_background():
    # the eval showed hangers and floors dominating otherwise
    assert "background" in garment_job.prompt.lower()


def test_the_two_jobs_write_to_different_files():
    assert palette_job.json_data != garment_job.json_data


def test_a_job_is_immutable():
    # jobs are module-level singletons shared by the CLI and the API
    with pytest.raises(Exception):
        garment_job.model = "claude-haiku-4-5-20251001"


def test_a_job_can_be_built_for_a_different_store():
    # dataclasses.replace is how tests and any future caller retarget the JSON
    import dataclasses

    from pathlib import Path

    other = dataclasses.replace(garment_job, json_data=Path("/tmp/x.json"))
    assert isinstance(other, ExtractPhotoDetails)
    assert other.tool_name == garment_job.tool_name


# ------------------------------------------------------------------- config

def test_the_paths_are_anchored_to_the_repo_root_not_the_cwd():
    # the CLI has to work from any directory
    assert config.project_root.is_absolute()
    assert (config.project_root / "pyproject.toml").exists()


def test_the_two_stores_live_under_data():
    assert config.garment_hex_colors.parent == config.project_root / "data"
    assert config.palette_hex_colors.parent == config.project_root / "data"


def test_the_ui_data_file_lands_inside_the_vite_app():
    # Vite only imports from inside src/ui
    assert config.palette_matches.is_relative_to(config.project_root / "src/ui")


def test_url_prefixes_are_absolute_and_unslashed():
    for prefix in (config.garment_url_prefix, config.palette_url_prefix):
        assert prefix.startswith("/") and not prefix.endswith("/")


def test_the_url_prefixes_are_mounted_under_img_and_name_the_photo_folders():
    # /img keeps the image URLs clear of the JSON routes: /garments is already
    # an endpoint, so the photos cannot also live at /garments/<file>.
    assert config.garment_url_prefix == "/img/" + config.garment_folder.name
    assert config.palette_url_prefix == "/img/" + config.color_palettes_folder.name


def test_the_url_prefixes_do_not_collide_with_the_json_routes():
    # the collision this layout exists to prevent — a prefix that shadows an
    # endpoint makes one of the two unreachable
    from fastapi.routing import APIRoute

    from closetllm.api import app

    # APIRoute only: the photo mounts are registered at these exact prefixes, so
    # comparing against every route would flag the correct layout as a collision.
    json_routes = {r.path for r in app.routes if isinstance(r, APIRoute)}
    for prefix in (config.garment_url_prefix, config.palette_url_prefix):
        assert prefix not in json_routes
        # a mount also swallows everything beneath it, so a prefix that is a
        # parent of an endpoint makes that endpoint unreachable too
        assert not any(route.startswith(prefix + "/") for route in json_routes)


def test_the_photo_mounts_are_registered_at_the_configured_prefixes():
    # match.py stamps every "src" with these prefixes, so a mount at any other
    # path serves 404s for photos the UI is already asking for. Skipped per
    # folder when it is absent, because api.py only mounts folders that exist.
    from starlette.routing import Mount

    from closetllm.api import app

    mounts = {r.path for r in app.routes if isinstance(r, Mount)}
    if config.web_garment_folder.exists():
        assert config.garment_url_prefix in mounts
    if config.color_palettes_folder.exists():
        assert config.palette_url_prefix in mounts


def test_image_extensions_are_lowercase_and_dotted():
    # extract.run compares against photo.suffix.lower()
    assert all(ext.startswith(".") and ext == ext.lower() for ext in config.img_types)


def test_max_edge_respects_the_api_downscale_limit():
    # anything larger is downscaled server-side anyway, so we'd pay to upload it
    assert config.max_edge <= 1568
