#downscale garment photos into web-sized copies for deployment.
from pathlib import Path

from PIL import Image

from closetllm.config import garment_folder, img_types, web_garment_folder, web_max_edge

# JPEG can't hold transparency; anything with alpha gets flattened onto white
# rather than the black you'd get from a bare convert("RGB").
WHITE = (255, 255, 255)


def web_copy(photo: Path, out_dir: Path) -> tuple[int, int]:
    """Write a downscaled copy of `photo` into `out_dir`. Returns (before, after) bytes."""
    img = Image.open(photo)

    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        flat = Image.new("RGB", img.size, WHITE)
        flat.paste(img, mask=img.split()[-1])
        img = flat
    else:
        img = img.convert("RGB")

    # thumbnail() scales in place, preserves aspect ratio, and never upscales
    img.thumbnail((web_max_edge, web_max_edge))

    # The filename must match the key in clothes.json exactly — the UI builds
    # its src as url_prefix + filename, so a renamed file is a broken image.
    out_path = out_dir / photo.name
    img.save(out_path, format="JPEG", quality=85, optimize=True)

    return photo.stat().st_size, out_path.stat().st_size


def main() -> None:
    if not garment_folder.exists():
        raise SystemExit(f"no photos to resize: {garment_folder} does not exist")

    web_garment_folder.mkdir(parents=True, exist_ok=True)

    photos = sorted(p for p in garment_folder.iterdir() if p.suffix.lower() in img_types)
    if not photos:
        raise SystemExit(f"no images found in {garment_folder}")

    total_before = total_after = 0
    for photo in photos:
        before, after = web_copy(photo, web_garment_folder)
        total_before += before
        total_after += after
        print(f"  {photo.name}: {before // 1024}KB -> {after // 1024}KB")

    print(
        f"\n{len(photos)} photos: "
        f"{total_before // 1_048_576}MB -> {total_after // 1_048_576}MB "
        f"in {web_garment_folder}"
    )


if __name__ == "__main__":
    main()