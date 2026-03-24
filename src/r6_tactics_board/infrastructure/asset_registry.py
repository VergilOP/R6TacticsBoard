import json
from dataclasses import dataclass, field
from pathlib import Path

from r6_tactics_board.infrastructure.asset_paths import (
    ATTACK_OPERATORS_DIR,
    DEFENSE_OPERATORS_DIR,
    MAPS_DIR,
    PROJECT_ROOT,
    ensure_asset_directories,
)


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


@dataclass(slots=True)
class OperatorAsset:
    key: str
    side: str
    path: str


@dataclass(slots=True)
class MapFloorAsset:
    key: str
    name: str
    image_path: str


@dataclass(slots=True)
class MapAsset:
    key: str
    name: str
    path: str
    floors: list[MapFloorAsset] = field(default_factory=list)


class AssetRegistry:
    def __init__(self) -> None:
        ensure_asset_directories()

    def list_map_assets(self) -> list[MapAsset]:
        index_path = MAPS_DIR / "index.json"
        if index_path.is_file():
            try:
                raw_items = json.loads(index_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raw_items = []

            assets: list[MapAsset] = []
            for item in raw_items:
                map_path = self._resolve_asset_path(index_path.parent, item.get("path", ""))
                asset = self.load_map_asset(str(map_path))
                if asset is not None:
                    assets.append(asset)
            if assets:
                return assets

        return self._fallback_map_assets()

    def load_map_asset(self, map_json_path: str) -> MapAsset | None:
        path = Path(map_json_path)
        if not path.is_absolute():
            path = (PROJECT_ROOT / path).resolve()
        if not path.is_file():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        floors: list[MapFloorAsset] = []
        for item in data.get("floors", []):
            image_path = self._resolve_asset_path(path.parent, item.get("image", ""))
            if image_path.is_file():
                floors.append(
                    MapFloorAsset(
                        key=item.get("key", image_path.stem),
                        name=item.get("name", image_path.stem),
                        image_path=str(image_path),
                    )
                )

        if not floors:
            image_path = self._resolve_asset_path(path.parent, data.get("image", ""))
            if image_path.is_file():
                floors.append(
                    MapFloorAsset(
                        key="default",
                        name="Default",
                        image_path=str(image_path),
                    )
                )

        if not floors:
            return None

        return MapAsset(
            key=data.get("key", path.parent.name),
            name=data.get("name", path.parent.name),
            path=str(path),
            floors=floors,
        )

    def find_map_asset(self, key: str) -> MapAsset | None:
        for asset in self.list_map_assets():
            if asset.key == key:
                return asset
        return None

    def list_operator_assets(self, side: str | None = None) -> list[OperatorAsset]:
        assets: list[OperatorAsset] = []
        if side in (None, "attack"):
            assets.extend(self._operator_assets_from_dir(ATTACK_OPERATORS_DIR / "icons", "attack"))
        if side in (None, "defense"):
            assets.extend(self._operator_assets_from_dir(DEFENSE_OPERATORS_DIR / "icons", "defense"))
        return sorted(assets, key=lambda item: (item.side, item.key))

    def find_operator_asset(self, side: str, key: str) -> OperatorAsset | None:
        for asset in self.list_operator_assets(side):
            if asset.key == key:
                return asset
        return None

    def _fallback_map_assets(self) -> list[MapAsset]:
        assets: list[MapAsset] = []
        for item in sorted(MAPS_DIR.iterdir()):
            if item.is_dir():
                map_json_path = item / "map.json"
                if map_json_path.is_file():
                    asset = self.load_map_asset(str(map_json_path))
                    if asset is not None:
                        assets.append(asset)
        return assets

    def _operator_assets_from_dir(self, directory: Path, side: str) -> list[OperatorAsset]:
        return [
            OperatorAsset(key=file.stem, side=side, path=str(file))
            for file in self._list_image_files(directory)
        ]

    @staticmethod
    def _list_image_files(directory: Path) -> list[Path]:
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

    @staticmethod
    def _resolve_asset_path(base_dir: Path, raw_path: str) -> Path:
        candidate = Path(raw_path)
        if candidate.is_absolute():
            return candidate
        if raw_path.startswith("assets/") or raw_path.startswith("assets\\"):
            return (PROJECT_ROOT / candidate).resolve()
        return (base_dir / candidate).resolve() if raw_path else base_dir
