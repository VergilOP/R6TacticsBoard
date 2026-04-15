from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from r6_tactics_board.domain.models import (
    Keyframe,
    MapInfo,
    OperatorDefinition,
    OperatorFrameState,
    SurfaceOpeningType,
    TacticalSurfaceState,
    TacticProject,
    Timeline,
)
from r6_tactics_board.infrastructure.assets.asset_registry import (
    AssetRegistry,
    GadgetAsset,
    MapAsset,
    MapFloorAsset,
    OperatorAsset,
)
from r6_tactics_board.infrastructure.persistence.project_store import ProjectStore


@dataclass(slots=True)
class LoadedMapSelection:
    asset: MapAsset
    floor: MapFloorAsset


class EditorSessionService:
    def __init__(
        self,
        *,
        asset_registry: AssetRegistry | None = None,
        project_store: ProjectStore | None = None,
    ) -> None:
        self._asset_registry = asset_registry or AssetRegistry()
        self._project_store = project_store or ProjectStore()

    def load_map_selection(self, map_asset_path: str, floor_key: str = "") -> LoadedMapSelection | None:
        asset = self._asset_registry.load_map_asset(map_asset_path)
        if asset is None or not asset.floors:
            return None
        selected_floor = next(
            (floor for floor in asset.floors if floor.key == floor_key),
            asset.floors[0],
        )
        return LoadedMapSelection(asset=asset, floor=selected_floor)

    def load_project(self, file_path: str) -> TacticProject:
        return self._project_store.load(file_path)

    def save_project(self, file_path: str, project: TacticProject) -> str:
        normalized = self.normalize_project_path(file_path)
        self._project_store.save(normalized, project)
        return normalized

    @staticmethod
    def normalize_project_path(file_path: str) -> str:
        return file_path if file_path.endswith(".r6tb.json") else f"{file_path}.r6tb.json"

    @staticmethod
    def project_name_from_path(file_path: str) -> str:
        file_name = Path(file_path).name
        if file_name.endswith(".r6tb.json"):
            return file_name[: -len(".r6tb.json")]
        return Path(file_name).stem

    def list_operator_assets(self, side: str) -> list[OperatorAsset]:
        return self._asset_registry.list_operator_assets(side)

    def find_operator_asset(self, side: str, operator_key: str) -> OperatorAsset | None:
        return self._asset_registry.find_operator_asset(side, operator_key)

    def find_operator_catalog_entry(self, value: str, side: str | None = None):
        return self._asset_registry.find_operator_catalog_entry(value, side)

    def list_operator_catalog(self, side: str | None = None):
        return self._asset_registry.list_operator_catalog(side)

    def list_gadget_assets(self, side: str) -> list[GadgetAsset]:
        return self._asset_registry.list_gadget_assets(side)

    def find_gadget_asset(self, side: str, gadget_key: str) -> GadgetAsset | None:
        return self._asset_registry.find_gadget_asset(side, gadget_key)

    def save_gadget_count(self, side: str, gadget_key: str, count: int) -> None:
        self._asset_registry.save_gadget_count(side, gadget_key, count)

    def save_gadget_persistence(self, side: str, gadget_key: str, persists_on_map: bool) -> None:
        self._asset_registry.save_gadget_persistence(side, gadget_key, persists_on_map)

    def list_operator_gadget_assets(self, side: str, operator_key: str) -> list[GadgetAsset]:
        return self._asset_registry.list_operator_gadget_assets(side, operator_key)

    def find_operator_gadget_asset(self, side: str, operator_key: str, gadget_key: str) -> GadgetAsset | None:
        return self._asset_registry.find_operator_gadget_asset(side, operator_key, gadget_key)

    def save_operator_gadget_count(self, side: str, operator_key: str, gadget_key: str, count: int) -> None:
        self._asset_registry.save_operator_gadget_count(side, operator_key, gadget_key, count)

    def save_operator_ability_count(self, side: str, operator_key: str, count: int) -> None:
        self._asset_registry.save_operator_ability_count(side, operator_key, count)

    def save_operator_ability_persistence(self, side: str, operator_key: str, persists_on_map: bool) -> None:
        self._asset_registry.save_operator_ability_persistence(side, operator_key, persists_on_map)

    def build_project(
        self,
        *,
        project_path: str,
        current_map_asset: MapAsset | None,
        current_map_asset_path: str,
        current_map_floor_key: str,
        map_image_path: str,
        operator_order: list[str],
        operator_definitions: dict[str, OperatorDefinition],
        keyframe_columns: list[dict[str, OperatorFrameState]],
        keyframe_names: list[str],
        keyframe_notes: list[str],
        surface_states: dict[str, TacticalSurfaceState],
        current_keyframe_index: int,
        transition_duration_ms: int,
        operator_scale: float,
    ) -> TacticProject:
        map_info = None
        if map_image_path:
            map_path = Path(map_image_path)
            if current_map_asset is not None:
                map_info = MapInfo(
                    key=current_map_asset.key,
                    name=current_map_asset.name,
                    image_path=str(map_path),
                    metadata_path=current_map_asset_path,
                    current_floor_key=current_map_floor_key,
                )
            else:
                map_info = MapInfo(key=map_path.stem, name=map_path.name, image_path=str(map_path))

        operators = [
            deepcopy(operator_definitions[operator_id])
            for operator_id in operator_order
            if operator_id in operator_definitions
        ]
        keyframes = [
            Keyframe(
                time_ms=index * transition_duration_ms,
                name=keyframe_names[index] if index < len(keyframe_names) else "",
                note=keyframe_notes[index] if index < len(keyframe_notes) else "",
                operator_frames=[
                    deepcopy(frame[operator_id])
                    for operator_id in operator_order
                    if operator_id in frame
                ],
            )
            for index, frame in enumerate(keyframe_columns)
        ]
        return TacticProject(
            name=(
                self.project_name_from_path(project_path)
                if project_path
                else current_map_asset.name
                if current_map_asset is not None
                else map_path.stem
                if map_image_path
                else "untitled"
            ),
            map_info=map_info,
            operators=operators,
            timeline=Timeline(keyframes=keyframes),
            surface_states=[
                deepcopy(surface_states[surface_id])
                for surface_id in sorted(surface_states)
            ],
            operator_order=list(operator_order),
            current_keyframe_index=current_keyframe_index,
            transition_duration_ms=transition_duration_ms,
            operator_scale=operator_scale,
        )
