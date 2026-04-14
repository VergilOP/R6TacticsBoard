from dataclasses import dataclass, field
from enum import Enum


class TeamSide(str, Enum):
    ATTACK = "attack"
    DEFENSE = "defense"


class OperatorDisplayMode(str, Enum):
    ICON = "icon"
    CUSTOM_NAME = "custom_name"


class OperatorTransitionMode(str, Enum):
    AUTO = "auto"
    MANUAL = "manual"


class MapInteractionType(str, Enum):
    STAIRS = "stairs"
    HATCH = "hatch"


class MapSurfaceType(str, Enum):
    SOFT_WALL = "soft_wall"
    HATCH = "hatch"


class SurfaceOpeningType(str, Enum):
    PASSAGE = "passage"
    CROUCH_PASSAGE = "crouch_passage"
    VAULT = "vault"


@dataclass(slots=True)
class Point2D:
    x: float
    y: float


@dataclass(slots=True)
class MapInfo:
    key: str
    name: str
    image_path: str = ""
    metadata_path: str = ""
    current_floor_key: str = ""


@dataclass(slots=True)
class MapInteractionPoint:
    id: str
    kind: MapInteractionType
    position: Point2D
    floor_key: str
    target_position: Point2D | None = None
    path_points: list[Point2D] = field(default_factory=list)
    linked_floor_keys: list[str] = field(default_factory=list)
    is_bidirectional: bool = False
    label: str = ""
    note: str = ""


@dataclass(slots=True)
class MapSurface:
    id: str
    kind: MapSurfaceType
    floor_key: str
    start: Point2D
    end: Point2D
    linked_floor_keys: list[str] = field(default_factory=list)
    is_bidirectional: bool = False
    label: str = ""
    note: str = ""


@dataclass(slots=True)
class TacticalSurfaceState:
    surface_id: str
    reinforced: bool = False
    opening_type: SurfaceOpeningType | None = None
    foot_hole: bool = False
    gun_hole: bool = False


@dataclass(slots=True)
class OperatorDefinition:
    id: str
    custom_name: str
    side: TeamSide
    operator_key: str = ""


@dataclass(slots=True)
class OperatorFrameState:
    id: str
    position: Point2D
    rotation: float = 0.0
    display_mode: OperatorDisplayMode = OperatorDisplayMode.ICON
    show_icon: bool = True
    show_name: bool = False
    floor_key: str = ""
    transition_mode: OperatorTransitionMode = OperatorTransitionMode.AUTO
    manual_interaction_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class OperatorState:
    id: str
    operator_key: str
    custom_name: str
    side: TeamSide
    position: Point2D
    rotation: float = 0.0
    display_mode: OperatorDisplayMode = OperatorDisplayMode.ICON
    show_icon: bool = True
    show_name: bool = False
    floor_key: str = ""
    transition_mode: OperatorTransitionMode = OperatorTransitionMode.AUTO
    manual_interaction_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Keyframe:
    time_ms: int
    name: str = ""
    note: str = ""
    operator_frames: list[OperatorFrameState] = field(default_factory=list)


@dataclass(slots=True)
class Timeline:
    keyframes: list[Keyframe] = field(default_factory=list)


@dataclass(slots=True)
class TacticProject:
    name: str
    map_info: MapInfo | None = None
    operators: list[OperatorDefinition] = field(default_factory=list)
    timeline: Timeline = field(default_factory=Timeline)
    surface_states: list[TacticalSurfaceState] = field(default_factory=list)
    operator_order: list[str] = field(default_factory=list)
    current_keyframe_index: int = 0
    transition_duration_ms: int = 700
    operator_scale: float = 1.0


def resolve_operator_state(
    definition: OperatorDefinition,
    frame: OperatorFrameState,
) -> OperatorState:
    show_icon = frame.show_icon
    show_name = frame.show_name
    if not show_icon and not show_name:
        show_icon = True
    display_mode = (
        OperatorDisplayMode.CUSTOM_NAME
        if show_name and not show_icon
        else OperatorDisplayMode.ICON
    )
    return OperatorState(
        id=definition.id,
        operator_key=definition.operator_key,
        custom_name=definition.custom_name,
        side=definition.side,
        position=Point2D(x=frame.position.x, y=frame.position.y),
        rotation=frame.rotation,
        display_mode=display_mode,
        show_icon=show_icon,
        show_name=show_name,
        floor_key=frame.floor_key,
        transition_mode=frame.transition_mode,
        manual_interaction_ids=list(frame.manual_interaction_ids),
    )
