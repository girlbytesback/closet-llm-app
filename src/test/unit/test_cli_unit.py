"""Argument parsing and dispatch. The commands themselves are stubbed out —
what's under test is which function gets called with which arguments.
"""

from pathlib import Path

import pytest

from closetllm import cli
from closetllm.color import default_cutoff
from closetllm.config import color_palettes_folder, garment_folder, palette_matches


@pytest.fixture
def spy(monkeypatch):
    """Replace the three commands with recorders."""
    calls = {}

    def record(name):
        def fake(*args):
            calls[name] = args
            return {}

        return fake

    monkeypatch.setattr(cli, "run_closet_colors", record("clothes"))
    monkeypatch.setattr(cli, "run_color_palettes", record("palettes"))
    monkeypatch.setattr(cli, "run_matches", record("match"))
    return calls


def invoke(monkeypatch, *argv):
    monkeypatch.setattr("sys.argv", ["closetllm", *argv])
    cli.main()


def test_a_command_is_required(monkeypatch, spy):
    with pytest.raises(SystemExit) as exit_:
        invoke(monkeypatch)
    assert exit_.value.code == 2


def test_an_unknown_command_is_rejected(monkeypatch, spy):
    with pytest.raises(SystemExit) as exit_:
        invoke(monkeypatch, "sew")
    assert exit_.value.code == 2


def test_clothes_defaults_to_the_configured_folder(monkeypatch, spy):
    invoke(monkeypatch, "clothes")
    assert spy["clothes"] == (garment_folder,)


def test_clothes_takes_a_folder_as_a_path(monkeypatch, spy):
    invoke(monkeypatch, "clothes", "/tmp/somewhere")
    assert spy["clothes"] == (Path("/tmp/somewhere"),)


def test_palettes_defaults_to_the_configured_folder(monkeypatch, spy):
    invoke(monkeypatch, "palettes")
    assert spy["palettes"] == (color_palettes_folder,)


def test_palettes_takes_a_folder(monkeypatch, spy):
    invoke(monkeypatch, "palettes", "/tmp/pins")
    assert spy["palettes"] == (Path("/tmp/pins"),)


def test_match_defaults_to_the_shared_cutoff_and_writes_nothing(monkeypatch, spy):
    invoke(monkeypatch, "match")
    assert spy["match"] == (default_cutoff, None, None)


def test_match_takes_a_cutoff_as_a_float(monkeypatch, spy):
    invoke(monkeypatch, "match", "--cutoff", "7.5")
    assert spy["match"][0] == 7.5


def test_match_takes_a_limit_as_an_int(monkeypatch, spy):
    invoke(monkeypatch, "match", "--limit", "3")
    assert spy["match"][1] == 3


def test_a_bare_out_flag_writes_to_the_configured_ui_path(monkeypatch, spy):
    invoke(monkeypatch, "match", "--out")
    assert spy["match"][2] == palette_matches


def test_out_with_a_value_writes_there_instead(monkeypatch, spy):
    invoke(monkeypatch, "match", "--out", "/tmp/mine.json")
    assert spy["match"][2] == Path("/tmp/mine.json")


def test_a_non_numeric_cutoff_is_rejected(monkeypatch, spy):
    with pytest.raises(SystemExit) as exit_:
        invoke(monkeypatch, "match", "--cutoff", "close-ish")
    assert exit_.value.code == 2


def test_a_missing_folder_exits_with_a_message_not_a_traceback(monkeypatch):
    def boom(_folder):
        raise FileNotFoundError("no photos folder at /tmp/nope")

    monkeypatch.setattr(cli, "run_closet_colors", boom)

    with pytest.raises(SystemExit) as exit_:
        invoke(monkeypatch, "clothes", "/tmp/nope")

    assert str(exit_.value) == "closetllm: no photos folder at /tmp/nope"


def test_a_missing_data_file_on_match_exits_the_same_way(monkeypatch):
    def boom(*_args):
        raise FileNotFoundError("no clothes saved yet")

    monkeypatch.setattr(cli, "run_matches", boom)

    with pytest.raises(SystemExit) as exit_:
        invoke(monkeypatch, "match")

    assert "no clothes saved yet" in str(exit_.value)


def test_other_errors_are_not_swallowed(monkeypatch):
    # only FileNotFoundError is user error; a bad hex from the model is a bug
    # and should keep its traceback
    def boom(_folder):
        raise ValueError("not a hex color: 'sage'")

    monkeypatch.setattr(cli, "run_closet_colors", boom)

    with pytest.raises(ValueError):
        invoke(monkeypatch, "clothes")
