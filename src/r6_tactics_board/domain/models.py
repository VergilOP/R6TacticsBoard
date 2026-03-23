from dataclasses import dataclass, field
from enum import Enum


class TeamSide(str, Enum):
    ATTACK = "attack"
    DEFENSE = "defense"


class OperatorDisplayMode(str, Enum):
    ICON = "icon"
    CUSTOM_NAME = "custom_name"


@dataclass(slots=True)
class Point2D:
    x: float
    y: float


@dataclass(slots=True)
class MapInfo:
    key: str
    name: str
    image_path: str = ""


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


@dataclass(slots=True)
class OperatorState:
    id: str
    operator_key: str
    custom_name: str
    side: TeamSide
    position: Point2D
    rotation: float = 0.0
    display_mode: OperatorDisplayMode = OperatorDisplayMode.ICON


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
    operator_order: list[str] = field(default_factory=list)
    current_keyframe_index: int = 0
    transition_duration_ms: int = 700


def resolve_operator_state(
    definition: OperatorDefinition,
    frame: OperatorFrameState,
) -> OperatorState:
    return OperatorState(
        id=definition.id,
        operator_key=definition.operator_key,
        custom_name=definition.custom_name,
        side=definition.side,
        position=Point2D(x=frame.position.x, y=frame.position.y),
        rotation=frame.rotation,
        display_mode=frame.display_mode,
    )
