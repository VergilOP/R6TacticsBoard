from dataclasses import dataclass

from r6_tactics_board.domain.models import (
    OperatorDefinition,
    OperatorFrameState,
    OperatorState,
    TacticalSurfaceState,
)


@dataclass(slots=True)
class EditorHistoryState:
    map_asset_path: str
    map_floor_key: str
    map_image_path: str
    scene_states: list[OperatorState]
    selected_operator_id: str
    operator_order: list[str]
    operator_definitions: dict[str, OperatorDefinition]
    keyframe_columns: list[dict[str, OperatorFrameState]]
    keyframe_names: list[str]
    keyframe_notes: list[str]
    current_keyframe_index: int
    current_timeline_row: int
    selected_surface_id: str
    surface_states: dict[str, TacticalSurfaceState]
    transition_duration_ms: int


@dataclass(slots=True)
class EditorProjectState:
    map_reference_path: str
    operator_order: list[str]
    operator_definitions: dict[str, OperatorDefinition]
    keyframe_columns: list[dict[str, OperatorFrameState]]
    keyframe_names: list[str]
    keyframe_notes: list[str]
    surface_states: dict[str, TacticalSurfaceState]
    transition_duration_ms: int
