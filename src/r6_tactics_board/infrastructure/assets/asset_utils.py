from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from r6_tactics_board.infrastructure.assets.asset_paths import PROJECT_ROOT


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def list_image_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        [
            item
            for item in directory.iterdir()
            if item.is_file()
            and item.name != ".gitkeep"
            and item.suffix.lower() in IMAGE_SUFFIXES
        ]
    )


def resolve_asset_path(base_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    if raw_path.startswith("assets/") or raw_path.startswith("assets\\"):
        return (PROJECT_ROOT / candidate).resolve()
    return (base_dir / candidate).resolve() if raw_path else base_dir


def normalize_operator_lookup(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_like = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", ascii_like.lower())


def default_gadget_persistence(gadget_key: str) -> bool:
    persistent = {
        "barbed-wire",
        "bulletproof-camera",
        "claymore",
        "deployable-shield",
        "observation-blocker",
        "proximity-alarm",
    }
    return gadget_key in persistent
