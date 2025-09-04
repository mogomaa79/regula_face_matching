from __future__ import annotations
from pathlib import Path
from typing import Optional, Tuple, List

PASSPORT_HINTS = ("pass", "passport", "doc", "mrz", "bio", "id")
SELFIE_HINTS = ("selfie", "face", "live", "photo", "portrait")

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}

def list_image_files(dir_path: Path) -> List[Path]:
    return [p for p in dir_path.iterdir() if p.suffix.lower() in IMG_EXTS and p.is_file()]

def choose_passport_and_selfie(images: List[Path]) -> Tuple[Optional[Path], Optional[Path]]:
    if not images:
        return None, None
    lower_map = {p: p.name.lower() for p in images}
    passport = next((p for p, n in lower_map.items() if any(h in n for h in PASSPORT_HINTS)), None)
    selfie   = next((p for p, n in lower_map.items() if any(h in n for h in SELFIE_HINTS)), None)

    # fallback: first two images
    if not passport and len(images) >= 1:
        passport = images[0]
    if not selfie and len(images) >= 2:
        selfie = images[1] if images[1] != passport else (images[0] if len(images) > 1 else None)

    if passport is None or selfie is None or passport == selfie:
        # last fallback: try to split by size (passport often larger/wider)
        imgs_sorted = sorted(images, key=lambda p: p.stat().st_size, reverse=True)
        if len(imgs_sorted) >= 2:
            passport, selfie = imgs_sorted[0], imgs_sorted[1]
    return passport, selfie
