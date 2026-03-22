from dataclasses import dataclass
from pathlib import Path

from r6_tactics_board.infrastructure.asset_paths import (
    ATTACK_OPERATORS_DIR,
    DEFENSE_OPERATORS_DIR,
    MAPS_DIR,
    ensure_asset_directories,
)


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


@dataclass(slots=True)
class OperatorAsset:
    key: str
    side: str
    path: str


class AssetRegistry:
    def __init__(self) -> None:
        ensure_asset_directories()

    def list_map_files(self) -> list[Path]:
        return self._list_image_files(MAPS_DIR)

    def list_operator_assets(self, side: str | None = None) -> list[OperatorAsset]:
        assets: list[OperatorAsset] = []
        if side in (None, "attack"):
            assets.extend(self._operator_assets_from_dir(ATTACK_OPERATORS_DIR, "attack"))
        if side in (None, "defense"):
            assets.extend(self._operator_assets_from_dir(DEFENSE_OPERATORS_DIR, "defense"))
        return sorted(assets, key=lambda item: (item.side, item.key))

    def find_operator_asset(self, side: str, key: str) -> OperatorAsset | None:
        for asset in self.list_operator_assets(side):
            if asset.key == key:
                return asset
        return None

    def _operator_assets_from_dir(self, directory: Path, side: str) -> list[OperatorAsset]:
        return [
            OperatorAsset(key=file.stem, side=side, path=str(file))
            for file in self._list_image_files(directory)
        ]

    @staticmethod
    def _list_image_files(directory: Path) -> list[Path]:
        return sorted(
            [
                item
                for item in directory.iterdir()
                if item.is_file()
                and item.name != ".gitkeep"
                and item.suffix.lower() in IMAGE_SUFFIXES
            ]
        )
