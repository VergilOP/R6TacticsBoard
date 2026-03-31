from dataclasses import dataclass
from math import hypot

from r6_tactics_board.domain.models import Point2D
from r6_tactics_board.infrastructure.assets.asset_registry import MapAsset, MapFloorAsset


@dataclass(slots=True)
class FloorOverviewLayout:
    width: float
    height: float
    z: float


class OverviewProjection:
    def ordered_floors(self, asset: MapAsset) -> list[MapFloorAsset]:
        overview = asset.overview_2p5d
        if overview is None or not overview.draw_order:
            return list(asset.floors)

        floors_by_key = {floor.key: floor for floor in asset.floors}
        ordered: list[MapFloorAsset] = []
        seen: set[str] = set()
        for floor_key in overview.draw_order:
            floor = floors_by_key.get(floor_key)
            if floor is None or floor.key in seen:
                continue
            ordered.append(floor)
            seen.add(floor.key)
        for floor in asset.floors:
            if floor.key not in seen:
                ordered.append(floor)
        return ordered

    def floor_layouts(
        self,
        asset: MapAsset,
        dimensions: dict[str, tuple[int, int]],
    ) -> dict[str, FloorOverviewLayout]:
        ordered = self.ordered_floors(asset)
        if not ordered:
            return {}

        overview = asset.overview_2p5d
        default_height = overview.floor_height if overview is not None else 180.0
        overrides = overview.floor_overrides if overview is not None else {}
        middle_index = (len(ordered) - 1) / 2.0
        layouts: dict[str, FloorOverviewLayout] = {}
        for index, floor in enumerate(ordered):
            width, height = dimensions.get(floor.key, (1, 1))
            z = (index - middle_index) * default_height
            if floor.overview_height is not None:
                z = floor.overview_height
            if floor.key in overrides:
                z = overrides[floor.key]
            layouts[floor.key] = FloorOverviewLayout(
                width=float(width),
                height=float(height),
                z=float(z),
            )
        return layouts

    def point_to_world(
        self,
        layout: FloorOverviewLayout,
        point: Point2D,
    ) -> tuple[float, float, float]:
        return (
            point.x - layout.width / 2.0,
            layout.height / 2.0 - point.y,
            layout.z,
        )

    def default_distance(self, layouts: dict[str, FloorOverviewLayout]) -> float:
        if not layouts:
            return 1600.0
        max_width = max(layout.width for layout in layouts.values())
        max_height = max(layout.height for layout in layouts.values())
        max_depth = max(abs(layout.z) for layout in layouts.values()) * 2.0
        return max(hypot(max_width, max_height) * 1.3, max_depth * 2.5, 1600.0)

    def default_center(self, layouts: dict[str, FloorOverviewLayout]) -> tuple[float, float, float]:
        if not layouts:
            return (0.0, 0.0, 0.0)
        min_z = min(layout.z for layout in layouts.values())
        max_z = max(layout.z for layout in layouts.values())
        return (0.0, 0.0, (min_z + max_z) / 2.0)
