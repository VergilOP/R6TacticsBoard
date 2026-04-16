from __future__ import annotations

from dataclasses import dataclass, field

from r6_tactics_board.domain.models import MapInteractionPoint, MapSurface


@dataclass(slots=True)
class OperatorAsset:
    key: str
    side: str
    path: str


@dataclass(slots=True)
class OperatorGadgetOption:
    key: str
    max_count: int = 1


@dataclass(slots=True)
class OperatorCatalogEntry:
    key: str
    side: str
    name: str
    icon_path: str
    portrait_path: str = ""
    ability_icon_path: str = ""
    ability_name: str = ""
    ability_description: str = ""
    ability_max_count: int = 0
    ability_persists_on_map: bool = True
    gadgets: list[OperatorGadgetOption] = field(default_factory=list)


@dataclass(slots=True)
class GadgetAsset:
    key: str
    side: str
    name: str
    path: str
    max_count: int = 1
    persists_on_map: bool = True


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
