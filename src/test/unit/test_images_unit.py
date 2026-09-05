"""image_block: a file on disk becomes a base64 content block the API accepts."""

import base64
import io

import pytest
from PIL import Image

from closetllm.config import max_edge
from closetllm.images import image_block


def decode(block) -> Image.Image:
    return Image.open(io.BytesIO(base64.standard_b64decode(block["source"]["data"])))


def test_block_has_the_shape_the_messages_api_expects(photo_folder):
    block = image_block(photo_folder.add("a.jpeg"))

    assert block["type"] == "image"
    assert block["source"]["type"] == "base64"
    assert block["source"]["media_type"] == "image/jpeg"
    assert isinstance(block["source"]["data"], str)


def test_data_is_valid_base64_of_a_real_jpeg(photo_folder):
    block = image_block(photo_folder.add("a.jpeg"))
    assert decode(block).format == "JPEG"


def test_a_png_is_re_encoded_as_jpeg(photo_folder):
    # the block always claims image/jpeg, so the bytes had better be JPEG
    block = image_block(photo_folder.add("a.png"))
    assert decode(block).format == "JPEG"


def test_a_large_photo_is_shrunk_to_the_long_edge(photo_folder):
    block = image_block(photo_folder.add("big.jpeg", size=(4000, 3000)))
    width, height = decode(block).size

    assert max(width, height) == max_edge
    # thumbnail preserves aspect ratio; 4000x3000 is 4:3
    assert width / height == pytest.approx(4 / 3, abs=0.01)


def test_a_small_photo_is_left_alone(photo_folder):
    # thumbnail only ever shrinks — upscaling a 40px photo would invent detail
    block = image_block(photo_folder.add("small.jpeg", size=(40, 40)))
    assert decode(block).size == (40, 40)


def test_shrinking_keeps_the_payload_well_under_the_api_limit(photo_folder):
    # Claude rejects images over 5MB; the phone photos in clothes/ exceed it raw
    block = image_block(photo_folder.add("big.jpeg", size=(4000, 3000)))
    assert len(base64.standard_b64decode(block["source"]["data"])) < 5 * 1024 * 1024


def test_a_grayscale_photo_is_converted_to_rgb(tmp_path):
    path = tmp_path / "gray.png"
    Image.new("L", (40, 40), 128).save(path)

    assert decode(image_block(path)).mode == "RGB"


def test_a_transparent_photo_does_not_crash_the_jpeg_save(tmp_path):
    # JPEG has no alpha channel; the convert("RGB") is what makes this work
    path = tmp_path / "alpha.png"
    Image.new("RGBA", (40, 40), (180, 194, 154, 0)).save(path)

    assert decode(image_block(path)).mode == "RGB"


def test_a_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        image_block(tmp_path / "nope.jpeg")
