import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from r6_tactics_board.domain.models import (
    MapInteractionPoint,
    MapInteractionType,
    MapSurface,
    MapSurfaceType,
    Point2D,
)
from r6_tactics_board.infrastructure.assets.asset_paths import (
    ATTACK_OPERATORS_DIR,
    DEFENSE_OPERATORS_DIR,
    MAPS_DIR,
    OPERATORS_DIR,
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
class OperatorCatalogEntry:
    key: str
    side: str
    name: str
    icon_path: str
    portrait_path: str = ""
    ability_icon_path: str = ""


@dataclass(slots=True)
class MapFloorAsset:
    key: str
    name: str
    image_path: str
    overview_height: float | None = None


@dataclass(slots=True)
class MapOverview2p5dAsset:
    enabled: bool = True
    default_yaw: float = 215.0
    default_zoom: float = 1.0
    pitch_factor: float = 0.65
    floor_height: float = 180.0
    draw_order: list[str] = field(default_factory=list)
    floor_overrides: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class MapAsset:
    key: str
    name: str
    path: str
    floors: list[MapFloorAsset] = field(default_factory=list)
    interactions: list[MapInteractionPoint] = field(default_factory=list)
    surfaces: list[MapSurface] = field(default_factory=list)
    overview_2p5d: MapOverview2p5dAsset | None = None


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
                overview_data = item.get("overview", {})
                overview_height = overview_data.get("height")
                floors.append(
                    MapFloorAsset(
                        key=item.get("key", image_path.stem),
                        name=item.get("name", image_path.stem),
                        image_path=str(image_path),
                        overview_height=(
                            float(overview_height)
                            if overview_height is not None
                            else None
                        ),
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

        interactions = self._load_interactions(data)
        surfaces = self._load_surfaces(data)
        interactions, surfaces = self._migrate_hatch_interactions_to_surfaces(interactions, surfaces)
        overview_2p5d = self._load_overview_2p5d(data)

        return MapAsset(
            key=data.get("key", path.parent.name),
            name=data.get("name", path.parent.name),
            path=str(path),
            floors=floors,
            interactions=interactions,
            surfaces=surfaces,
            overview_2p5d=overview_2p5d,
        )

    def find_map_asset(self, key: str) -> MapAsset | None:
        for asset in self.list_map_assets():
            if asset.key == key:
                return asset
        return None

    def save_map_interactions(
        self,
        map_json_path: str,
        interactions: list[MapInteractionPoint],
    ) -> None:
        path = Path(map_json_path)
        if not path.is_absolute():
            path = (PROJECT_ROOT / path).resolve()

        data = json.loads(path.read_text(encoding="utf-8"))
        layers = data.setdefault("layers", {})
        serialized = [
            self._serialize_interaction(item)
            for item in interactions
            if item.kind == MapInteractionType.STAIRS
        ]
        layers["interactions"] = serialized
        layers["stairs"] = [item for item in serialized if item.get("kind") == MapInteractionType.STAIRS.value]
        layers["hatches"] = []

        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
            newline="\n",
        )

    def save_map_surfaces(
        self,
        map_json_path: str,
        surfaces: list[MapSurface],
    ) -> None:
        path = Path(map_json_path)
        if not path.is_absolute():
            path = (PROJECT_ROOT / path).resolve()

        data = json.loads(path.read_text(encoding="utf-8"))
        layers = data.setdefault("layers", {})
        serialized = [self._serialize_surface(item) for item in surfaces]
        layers["soft_walls"] = [item for item in serialized if item.get("kind") == MapSurfaceType.SOFT_WALL.value]
        layers["hatch_surfaces"] = [item for item in serialized if item.get("kind") == MapSurfaceType.HATCH.value]
        layers["surfaces"] = serialized

        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
            newline="\n",
        )

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

    def list_operator_catalog(self, side: str | None = None) -> list[OperatorCatalogEntry]:
        index_path = OPERATORS_DIR / "index.json"
        if index_path.is_file():
            try:
                raw_items = json.loads(index_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raw_items = []

            entries: list[OperatorCatalogEntry] = []
            for item in raw_items:
                entry_side = str(item.get("side", ""))
                if side is not None and entry_side != side:
                    continue
                entries.append(
                    OperatorCatalogEntry(
                        key=str(item.get("key", "")),
                        side=entry_side,
                        name=str(item.get("name", "")),
                        icon_path=str(
                            self._resolve_asset_path(index_path.parent, str(item.get("icon_path", "")))
                        ),
                        portrait_path=str(
                            self._resolve_asset_path(index_path.parent, str(item.get("portrait_path", "")))
                        ),
                        ability_icon_path=str(
                            self._resolve_asset_path(
                                index_path.parent,
                                str(item.get("ability_icon_path", "")),
                            )
                        ),
                    )
                )
            if entries:
                return sorted(entries, key=lambda item: (item.side, item.key))

        return [
            OperatorCatalogEntry(
                key=asset.key,
                side=asset.side,
                name=asset.key,
                icon_path=asset.path,
            )
            for asset in self.list_operator_assets(side)
        ]

    def find_operator_catalog_entry(
        self,
        value: str,
        side: str | None = None,
    ) -> OperatorCatalogEntry | None:
        normalized = self._normalize_operator_lookup(value)
        if not normalized:
            return None

        for entry in self.list_operator_catalog(side):
            if normalized in {
                self._normalize_operator_lookup(entry.key),
                self._normalize_operator_lookup(entry.name),
            }:
                return entry
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
    def _load_interactions(data: dict) -> list[MapInteractionPoint]:
        layers = data.get("layers", {})
        raw_items = layers.get("interactions")
        if raw_items is None:
            raw_items = list(layers.get("stairs", [])) + list(layers.get("hatches", []))

        interactions: list[MapInteractionPoint] = []
        for index, item in enumerate(raw_items):
            position = item.get("position", {})
            kind_value = item.get("kind", MapInteractionType.STAIRS.value)
            try:
                kind = MapInteractionType(kind_value)
            except ValueError:
                continue

            interactions.append(
                MapInteractionPoint(
                    id=item.get("id", f"interaction-{index + 1}"),
                    kind=kind,
                    position=Point2D(
                        x=float(position.get("x", 0)),
                        y=float(position.get("y", 0)),
                    ),
                    floor_key=item.get("floor_key", "default"),
                    target_position=(
                        Point2D(
                            x=float(item.get("target_position", {}).get("x", position.get("x", 0))),
                            y=float(item.get("target_position", {}).get("y", position.get("y", 0))),
                        )
                        if kind == MapInteractionType.STAIRS
                        else None
                    ),
                    path_points=[
                        Point2D(
                            x=float(point.get("x", 0)),
                            y=float(point.get("y", 0)),
                        )
                        for point in item.get("path_points", [])
                        if isinstance(point, dict)
                    ],
                    linked_floor_keys=[
                        str(value)
                        for value in item.get("linked_floor_keys", [])
                        if str(value)
                    ],
                    is_bidirectional=bool(item.get("is_bidirectional", kind == MapInteractionType.STAIRS)),
                    label=item.get("label", ""),
                    note=item.get("note", ""),
                )
            )

        return interactions

    @staticmethod
    def _load_surfaces(data: dict) -> list[MapSurface]:
        layers = data.get("layers", {})
        raw_items = layers.get("surfaces")
        if raw_items is None:
            raw_items = list(layers.get("soft_walls", [])) + list(layers.get("hatch_surfaces", []))

        surfaces: list[MapSurface] = []
        for index, item in enumerate(raw_items):
            kind_value = item.get("kind", MapSurfaceType.SOFT_WALL.value)
            try:
                kind = MapSurfaceType(kind_value)
            except ValueError:
                continue
            start = item.get("start", {})
            end = item.get("end", {})
            surfaces.append(
                MapSurface(
                    id=item.get("id", f"surface-{index + 1}"),
                    kind=kind,
                    floor_key=item.get("floor_key", "default"),
                    start=Point2D(
                        x=float(start.get("x", 0)),
                        y=float(start.get("y", 0)),
                    ),
                    end=Point2D(
                        x=float(end.get("x", 0)),
                        y=float(end.get("y", 0)),
                    ),
                    linked_floor_keys=[
                        str(value)
                        for value in item.get("linked_floor_keys", [])
                        if str(value)
                    ],
                    is_bidirectional=bool(item.get("is_bidirectional", False)),
                    label=item.get("label", ""),
                    note=item.get("note", ""),
                )
            )
        return surfaces

    @staticmethod
    def _load_overview_2p5d(data: dict) -> MapOverview2p5dAsset | None:
        raw = data.get("overview_2_5d")
        if not isinstance(raw, dict):
            return None

        floor_overrides: dict[str, float] = {}
        for floor_key, override in raw.get("floor_overrides", {}).items():
            if not isinstance(override, dict):
                continue
            height = override.get("height")
            if height is None:
                continue
            try:
                floor_overrides[str(floor_key)] = float(height)
            except (TypeError, ValueError):
                continue

        draw_order = [
            str(item)
            for item in raw.get("draw_order", [])
            if str(item)
        ]
        return MapOverview2p5dAsset(
            enabled=bool(raw.get("enabled", True)),
            default_yaw=float(raw.get("default_yaw", 215.0)),
            default_zoom=float(raw.get("default_zoom", 1.0)),
            pitch_factor=float(raw.get("pitch_factor", 0.65)),
            floor_height=float(raw.get("floor_height", 180.0)),
            draw_order=draw_order,
            floor_overrides=floor_overrides,
        )

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

    @staticmethod
    def _serialize_interaction(item: MapInteractionPoint) -> dict:
        return {
            "id": item.id,
            "kind": item.kind.value,
            "position": {
                "x": item.position.x,
                "y": item.position.y,
            },
            "target_position": (
                {
                    "x": item.target_position.x,
                    "y": item.target_position.y,
                }
                if item.target_position is not None
                else None
            ),
            "path_points": [
                {
                    "x": point.x,
                    "y": point.y,
                }
                for point in item.path_points
            ],
            "floor_key": item.floor_key,
            "linked_floor_keys": list(item.linked_floor_keys),
            "is_bidirectional": item.is_bidirectional,
            "label": item.label,
            "note": item.note,
        }

    @staticmethod
    def _serialize_surface(item: MapSurface) -> dict:
        return {
            "id": item.id,
            "kind": item.kind.value,
            "floor_key": item.floor_key,
            "start": {
                "x": item.start.x,
                "y": item.start.y,
            },
            "end": {
                "x": item.end.x,
                "y": item.end.y,
            },
            "linked_floor_keys": list(item.linked_floor_keys),
            "is_bidirectional": item.is_bidirectional,
            "label": item.label,
            "note": item.note,
        }

    @staticmethod
    def _migrate_hatch_interactions_to_surfaces(
        interactions: list[MapInteractionPoint],
        surfaces: list[MapSurface],
    ) -> tuple[list[MapInteractionPoint], list[MapSurface]]:
        remaining_interactions: list[MapInteractionPoint] = []
        migrated_surfaces = list(surfaces)
        surface_ids = {surface.id for surface in migrated_surfaces}

        for interaction in interactions:
            if interaction.kind != MapInteractionType.HATCH:
                remaining_interactions.append(interaction)
                continue

            existing = next(
                (
                    surface
                    for surface in migrated_surfaces
                    if surface.kind == MapSurfaceType.HATCH
                    and (
                        surface.id == interaction.id
                        or (
                            surface.floor_key == interaction.floor_key
                            and abs(((surface.start.x + surface.end.x) / 2) - interaction.position.x) <= 2.0
                            and abs(((surface.start.y + surface.end.y) / 2) - interaction.position.y) <= 2.0
                        )
                    )
                ),
                None,
            )
            if existing is not None:
                if not existing.linked_floor_keys:
                    existing.linked_floor_keys = list(interaction.linked_floor_keys)
                existing.is_bidirectional = existing.is_bidirectional or interaction.is_bidirectional
                if not existing.label:
                    existing.label = interaction.label
                if not existing.note:
                    existing.note = interaction.note
                continue

            surface_id = interaction.id if interaction.id not in surface_ids else f"{interaction.id}-surface"
            surface_ids.add(surface_id)
            half_size = 32.0
            migrated_surfaces.append(
                MapSurface(
                    id=surface_id,
                    kind=MapSurfaceType.HATCH,
                    floor_key=interaction.floor_key,
                    start=Point2D(
                        x=interaction.position.x - half_size,
                        y=interaction.position.y - half_size,
                    ),
                    end=Point2D(
                        x=interaction.position.x + half_size,
                        y=interaction.position.y + half_size,
                    ),
                    linked_floor_keys=list(interaction.linked_floor_keys),
                    is_bidirectional=interaction.is_bidirectional,
                    label=interaction.label,
                    note=interaction.note,
                )
            )

        return remaining_interactions, migrated_surfaces

    @staticmethod
    def _normalize_operator_lookup(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        ascii_like = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        return re.sub(r"[^a-z0-9]+", "", ascii_like.lower())
