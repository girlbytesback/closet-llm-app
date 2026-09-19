#downscale garment photos into web-sized copies for deployment.
from pathlib import Path
from PIL import Image

from closetllm.config import garment_folder, img_types, web_garment_folder, web_max_edge
from closetllm.images import web_copy

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