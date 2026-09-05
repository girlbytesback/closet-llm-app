"""extract.py in isolation: disk I/O, one model call, and the folder walk.

No test here reaches the network — fake_model replaces the client entirely.
"""

import dataclasses
import json

import pytest

from closetllm import extract
from closetllm.extract import (
    ExtractPhotoDetails,
    garment_job,
    load_data,
    palette_job,
    run,
    save_data,
)

from helpers import FakeBlock, FakeResponse


# ---------------------------------------------------------------- load/save

def test_load_data_returns_empty_dict_when_file_is_missing(tmp_path):
    # "nothing extracted yet" has to be a dict, not None — every caller
    # iterates it or checks it for truthiness
    assert load_data(tmp_path / "never_written.json") == {}


def test_load_data_returns_empty_dict_for_an_empty_file(tmp_path):
    path = tmp_path / "colors.json"
    path.write_text("")
    assert load_data(path) == {}


def test_load_data_returns_empty_dict_for_a_whitespace_only_file(tmp_path):
    path = tmp_path / "colors.json"
    path.write_text("\n  \n")
    assert load_data(path) == {}


def test_load_data_raises_on_corrupt_json(tmp_path):
    # a truncated file is a real failure, not an empty closet — it must not
    # silently read as {} and wipe the store on the next save
    path = tmp_path / "colors.json"
    path.write_text('{"a.jpeg": ["#FFF"')
    with pytest.raises(json.JSONDecodeError):
        load_data(path)


def test_save_data_creates_the_parent_directory(tmp_path):
    path = tmp_path / "data" / "nested" / "colors.json"
    save_data({"a.jpeg": ["#B5C29A"]}, path)
    assert load_data(path) == {"a.jpeg": ["#B5C29A"]}


def test_save_data_is_sorted_and_newline_terminated(tmp_path):
    # sort_keys plus a trailing newline keeps the committed JSON diffable —
    # re-running extraction shouldn't reorder the whole file
    path = tmp_path / "colors.json"
    save_data({"z.jpeg": ["#000000"], "a.jpeg": ["#FFFFFF"]}, path)
    text = path.read_text()
    assert text.index('"a.jpeg"') < text.index('"z.jpeg"')
    assert text.endswith("\n")


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "colors.json"
    data = {"a.jpeg": ["#B5C29A", "#E4A8C0"]}
    save_data(data, path)
    assert load_data(path) == data


# ------------------------------------------------------------ extract_colors

def test_extract_colors_returns_the_tool_input(photo_folder, fake_model):
    fake_model({"item": "shirt", "color": "#B5C29A"})
    photo = photo_folder.add("shirt.jpeg")

    assert extract.extract_colors(photo, garment_job) == {
        "item": "shirt",
        "color": "#B5C29A",
    }


def test_extract_colors_forces_the_job_tool(photo_folder, fake_model):
    messages = fake_model({"item": "shirt", "color": "#B5C29A"})
    extract.extract_colors(photo_folder.add("shirt.jpeg"), garment_job)

    sent = messages.calls[0]
    assert sent["model"] == garment_job.model
    assert sent["tools"] == [garment_job.tool]
    # without tool_choice the model may answer in prose and the parse below fails
    assert sent["tool_choice"] == {"type": "tool", "name": "extract_clothing_colors"}


def test_extract_colors_sends_the_image_before_the_prompt(photo_folder, fake_model):
    messages = fake_model({"colors": ["#B5C29A", "#E4A8C0"]})
    extract.extract_colors(photo_folder.add("palette.jpeg"), palette_job)

    content = messages.calls[0]["messages"][0]["content"]
    assert content[0]["type"] == "image"
    assert content[0]["source"]["media_type"] == "image/jpeg"
    assert content[1] == {"type": "text", "text": palette_job.prompt}


def test_extract_colors_skips_non_tool_blocks(photo_folder, fake_model):
    # the model can emit thinking or text alongside the call; the tool_use
    # block is the one we want, wherever it lands
    fake_model(
        FakeResponse([FakeBlock("text"), FakeBlock("tool_use", {"colors": ["#B5C29A"]})])
    )
    result = extract.extract_colors(photo_folder.add("p.jpeg"), palette_job)
    assert result == {"colors": ["#B5C29A"]}


def test_extract_colors_raises_when_the_reply_was_cut_short(photo_folder, fake_model):
    fake_model(FakeResponse([FakeBlock("text")], stop_reason="max_tokens"))

    with pytest.raises(RuntimeError) as err:
        extract.extract_colors(photo_folder.add("shirt.jpeg"), garment_job)

    # the message has to name the photo and the stop_reason, or a failure
    # halfway through 50 photos is unattributable
    assert "shirt.jpeg" in str(err.value)
    assert "max_tokens" in str(err.value)


# ------------------------------------------------------------------- run()

@pytest.fixture
def job(tmp_path):
    """garment_job, pointed at a throwaway JSON store."""
    return dataclasses.replace(garment_job, json_data=tmp_path / "clothes.json")


def test_run_raises_when_the_folder_is_missing(tmp_path, job):
    with pytest.raises(FileNotFoundError) as err:
        run(tmp_path / "no_such_folder", job)
    assert "no_such_folder" in str(err.value)


def test_run_extracts_every_photo_and_saves_them(photo_folder, fake_model, job):
    photo_folder.add("a.jpeg")
    photo_folder.add("b.jpeg")
    fake_model({"item": "a", "color": "#B5C29A"}, {"item": "b", "color": "#E4A8C0"})

    result = run(photo_folder.path, job)

    assert result == {"a.jpeg": ["#B5C29A"], "b.jpeg": ["#E4A8C0"]}
    assert load_data(job.json_data) == result


def test_run_normalizes_whatever_the_model_returns(photo_folder, fake_model, job):
    # the schema asks for '#RRGGBB' but the model is not bound by it
    photo_folder.add("a.jpeg")
    fake_model({"item": "a", "color": " b5c29a "})

    assert run(photo_folder.path, job) == {"a.jpeg": ["#B5C29A"]}


def test_run_wraps_a_single_color_in_a_list(photo_folder, fake_model, job):
    # palettes come back as a list and garments as a bare string; downstream
    # code only ever sees a list
    photo_folder.add("a.jpeg")
    fake_model({"item": "a", "color": "#B5C29A"})
    assert run(photo_folder.path, job)["a.jpeg"] == ["#B5C29A"]


def test_run_keeps_a_palettes_multiple_colors(photo_folder, fake_model, tmp_path):
    palette = dataclasses.replace(palette_job, json_data=tmp_path / "colors.json")
    photo_folder.add("p.jpeg")
    fake_model({"colors": ["#B5C29A", "#E4A8C0"]})

    assert run(photo_folder.path, palette) == {"p.jpeg": ["#B5C29A", "#E4A8C0"]}


def test_run_does_not_recall_the_model_for_a_saved_photo(photo_folder, fake_model, job):
    photo_folder.add("a.jpeg")
    save_data({"a.jpeg": ["#123456"]}, job.json_data)
    messages = fake_model()  # any call at all fails the test

    assert run(photo_folder.path, job) == {"a.jpeg": ["#123456"]}
    assert messages.calls == []


def test_run_only_calls_the_model_for_the_new_photo(photo_folder, fake_model, job):
    photo_folder.add("a.jpeg")
    photo_folder.add("b.jpeg")
    save_data({"a.jpeg": ["#123456"]}, job.json_data)
    messages = fake_model({"item": "b", "color": "#E4A8C0"})

    run(photo_folder.path, job)

    assert len(messages.calls) == 1


def test_run_ignores_files_that_are_not_photos(photo_folder, fake_model, job):
    photo_folder.add("a.jpeg")
    (photo_folder.path / "notes.txt").write_text("hello")
    (photo_folder.path / ".DS_Store").write_bytes(b"\x00")
    fake_model({"item": "a", "color": "#B5C29A"})

    assert list(run(photo_folder.path, job)) == ["a.jpeg"]


def test_run_accepts_uppercase_extensions(photo_folder, fake_model, job):
    photo_folder.add("A.JPG")
    fake_model({"item": "a", "color": "#B5C29A"})
    assert list(run(photo_folder.path, job)) == ["A.JPG"]


def test_run_rejects_an_empty_color_list(photo_folder, fake_model, tmp_path):
    # an empty list would save cleanly and then blow up much later inside
    # score_garment's min() — fail on the photo that caused it
    palette = dataclasses.replace(palette_job, json_data=tmp_path / "colors.json")
    photo_folder.add("p.jpeg")
    fake_model({"colors": []})

    with pytest.raises(ValueError) as err:
        run(photo_folder.path, palette)
    assert "p.jpeg" in str(err.value)


def test_run_rejects_a_color_that_is_not_hex(photo_folder, fake_model, job):
    photo_folder.add("a.jpeg")
    fake_model({"item": "a", "color": "sage green"})

    with pytest.raises(ValueError):
        run(photo_folder.path, job)


def test_run_keeps_earlier_photos_when_a_later_one_fails(photo_folder, fake_model, job):
    # saving per photo is the point: an interrupt on photo 40 must not throw
    # away the 39 calls already paid for
    photo_folder.add("a.jpeg")
    photo_folder.add("b.jpeg")
    fake_model({"item": "a", "color": "#B5C29A"}, {"item": "b", "color": "not a color"})

    with pytest.raises(ValueError):
        run(photo_folder.path, job)

    assert load_data(job.json_data) == {"a.jpeg": ["#B5C29A"]}


def test_run_processes_photos_in_sorted_order(photo_folder, fake_model, job):
    for name in ("c.jpeg", "a.jpeg", "b.jpeg"):
        photo_folder.add(name)
    fake_model(*({"item": n, "color": "#B5C29A"} for n in "abc"))

    run(photo_folder.path, job)

    assert load_data(job.json_data) == {
        "a.jpeg": ["#B5C29A"],
        "b.jpeg": ["#B5C29A"],
        "c.jpeg": ["#B5C29A"],
    }


def test_run_prints_one_line_per_photo_tagged_new_or_saved(
    photo_folder, fake_model, job, capsys
):
    photo_folder.add("a.jpeg")
    photo_folder.add("b.jpeg")
    save_data({"a.jpeg": ["#123456"]}, job.json_data)
    fake_model({"item": "b", "color": "#E4A8C0"})

    run(photo_folder.path, job)

    out = capsys.readouterr().out
    assert "a.jpeg: #123456 (saved)" in out
    assert "b.jpeg: #E4A8C0 (new)" in out


# ------------------------------------------------------------------ client()

def test_importing_extract_needs_no_api_key():
    # `closetllm match` never calls the API; constructing Anthropic() at module
    # level would make it demand a key anyway. A subprocess is the only honest
    # check — this process already imported the module.
    import os
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    done = subprocess.run(
        [sys.executable, "-c", "import closetllm.extract"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stderr


def test_client_is_built_once_and_reused(monkeypatch):
    built = []

    class FakeAnthropic:
        def __init__(self):
            built.append(1)

    monkeypatch.setattr(extract, "_client", None)
    monkeypatch.setattr(extract, "Anthropic", FakeAnthropic)

    first, second = extract.client(), extract.client()

    assert first is second
    assert len(built) == 1
