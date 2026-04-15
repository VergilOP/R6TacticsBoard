import json
from pathlib import Path

from r6_tactics_board.domain.models import (
    Keyframe,
    MapInfo,
    OperatorDefinition,
    OperatorDisplayMode,
    OperatorFrameState,
    OperatorTransitionMode,
    Point2D,
    SurfaceOpeningType,
    TacticalSurfaceState,
    TacticProject,
    TeamSide,
    Timeline,
)


class ProjectStore:
    """JSON persistence for tactic projects."""

    @staticmethod
    def _display_flags(raw_state: dict) -> tuple[bool, bool]:
        if "show_icon" in raw_state or "show_name" in raw_state:
            show_icon = bool(raw_state.get("show_icon", True))
            show_name = bool(raw_state.get("show_name", False))
        else:
            legacy_mode = raw_state.get("display_mode", OperatorDisplayMode.ICON.value)
            show_icon = legacy_mode != OperatorDisplayMode.CUSTOM_NAME.value
            show_name = legacy_mode == OperatorDisplayMode.CUSTOM_NAME.value
        if not show_icon and not show_name:
            show_icon = True
        return show_icon, show_name

    @staticmethod
    def _display_mode_from_flags(show_icon: bool, show_name: bool) -> OperatorDisplayMode:
        return (
            OperatorDisplayMode.CUSTOM_NAME
            if show_name and not show_icon
            else OperatorDisplayMode.ICON
        )

    def load(self, path: str) -> TacticProject:
        project_path = Path(path).resolve()
        data = json.loads(project_path.read_text(encoding="utf-8"))

        map_info = None
        if data.get("map_info") is not None:
            image_path = data["map_info"].get("image_path", "")
            metadata_path = data["map_info"].get("metadata_path", "")
            map_info = MapInfo(
                key=data["map_info"].get("key", ""),
                name=data["map_info"].get("name", ""),
                image_path=self._resolve_path(project_path.parent, image_path),
                metadata_path=self._resolve_path(project_path.parent, metadata_path),
                current_floor_key=data["map_info"].get("current_floor_key", ""),
            )

        operators = self._load_operator_definitions(data)
        keyframes = [
            Keyframe(
                time_ms=item.get("time_ms", 0),
                name=item.get("name", ""),
                note=item.get("note", ""),
                operator_frames=[
                    self._load_operator_frame_state(state)
                    for state in item.get("operator_frames", item.get("operator_states", []))
                ],
            )
            for item in data.get("timeline", {}).get("keyframes", [])
        ]

        return TacticProject(
            name=data.get("name", project_path.stem),
            map_info=map_info,
            operators=operators,
            timeline=Timeline(keyframes=keyframes),
            surface_states=[
                TacticalSurfaceState(
                    surface_id=item.get("surface_id", ""),
                    reinforced=bool(item.get("reinforced", False)),
                    opening_type=(
                        SurfaceOpeningType(item["opening_type"])
                        if item.get("opening_type")
                        else None
                    ),
                    foot_hole=bool(item.get("foot_hole", False)),
                    gun_hole=bool(item.get("gun_hole", False)),
                )
                for item in data.get("surface_states", [])
                if item.get("surface_id")
            ],
            operator_order=data.get("operator_order", []),
            current_keyframe_index=data.get("current_keyframe_index", 0),
            transition_duration_ms=data.get("transition_duration_ms", 700),
            operator_scale=float(data.get("operator_scale", 1.0)),
        )

    def save(self, path: str, project: TacticProject) -> None:
        project_path = Path(path).resolve()
        data = {
            "name": project.name,
            "map_info": None
            if project.map_info is None
            else {
                "key": project.map_info.key,
                "name": project.map_info.name,
                "image_path": self._serialize_path(project_path.parent, project.map_info.image_path),
                "metadata_path": self._serialize_path(project_path.parent, project.map_info.metadata_path),
                "current_floor_key": project.map_info.current_floor_key,
            },
            "operators": [
                {
                    "id": operator.id,
                    "custom_name": operator.custom_name,
                    "side": operator.side.value,
                    "operator_key": operator.operator_key,
                    "gadget_key": operator.gadget_key,
                }
                for operator in project.operators
            ],
            "timeline": {
                "keyframes": [
                    {
                        "time_ms": keyframe.time_ms,
                        "name": keyframe.name,
                        "note": keyframe.note,
                        "operator_frames": [
                            self._serialize_operator_frame_state(state)
                            for state in keyframe.operator_frames
                        ],
                    }
                    for keyframe in project.timeline.keyframes
                ]
            },
            "surface_states": [
                {
                    "surface_id": state.surface_id,
                    "reinforced": state.reinforced,
                    "opening_type": state.opening_type.value if state.opening_type is not None else "",
                    "foot_hole": state.foot_hole,
                    "gun_hole": state.gun_hole,
                }
                for state in project.surface_states
            ],
            "operator_order": project.operator_order,
            "current_keyframe_index": project.current_keyframe_index,
            "transition_duration_ms": project.transition_duration_ms,
            "operator_scale": project.operator_scale,
        }
        project_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
            newline="\n",
        )

    @staticmethod
    def _resolve_path(base_dir: Path, raw_path: str) -> str:
        if not raw_path:
            return ""

        candidate = Path(raw_path)
        if candidate.is_absolute():
            return str(candidate)

        return str((base_dir / candidate).resolve())

    @staticmethod
    def _serialize_path(base_dir: Path, raw_path: str) -> str:
        if not raw_path:
            return ""

        candidate = Path(raw_path).resolve()
        try:
            return candidate.relative_to(base_dir).as_posix()
        except ValueError:
            return str(candidate)

    @staticmethod
    def _load_operator_definitions(data: dict) -> list[OperatorDefinition]:
        if data.get("operators"):
            return [
                OperatorDefinition(
                    id=item["id"],
                    custom_name=item.get("custom_name", ""),
                    side=TeamSide(item.get("side", TeamSide.ATTACK.value)),
                    operator_key=item.get("operator_key", ""),
                    gadget_key=item.get("gadget_key", ""),
                )
                for item in data.get("operators", [])
            ]

        inferred: dict[str, OperatorDefinition] = {}
        for keyframe in data.get("timeline", {}).get("keyframes", []):
            for state in keyframe.get("operator_states", []):
                operator_id = state["id"]
                if operator_id in inferred:
                    continue
                inferred[operator_id] = OperatorDefinition(
                    id=operator_id,
                    custom_name=state.get("custom_name", ""),
                    side=TeamSide(state.get("side", TeamSide.ATTACK.value)),
                    operator_key=state.get("operator_key", ""),
                    gadget_key=state.get("gadget_key", ""),
                )

        return list(inferred.values())

    def _load_operator_frame_state(self, state: dict) -> OperatorFrameState:
        show_icon, show_name = self._display_flags(state)
        gadget_positions = self._load_optional_points(state, "gadget_positions", "gadget_positions_explicit")
        ability_positions = self._load_optional_points(state, "ability_positions", "ability_positions_explicit")
        return OperatorFrameState(
            id=state["id"],
            position=Point2D(
                x=state["position"]["x"],
                y=state["position"]["y"],
            ),
            rotation=state.get("rotation", 0.0),
            display_mode=self._display_mode_from_flags(show_icon, show_name),
            show_icon=show_icon,
            show_name=show_name,
            floor_key=state.get("floor_key", ""),
            transition_mode=OperatorTransitionMode(
                state.get("transition_mode", OperatorTransitionMode.AUTO.value)
            ),
            manual_interaction_ids=[
                str(item)
                for item in state.get("manual_interaction_ids", [])
                if str(item)
            ],
            gadget_used_count=(
                int(state["gadget_used_count"])
                if state.get("gadget_used_count") is not None
                else None
            ),
            ability_used_count=(
                int(state["ability_used_count"])
                if state.get("ability_used_count") is not None
                else None
            ),
            gadget_positions=gadget_positions,
            ability_positions=ability_positions,
        )

    @staticmethod
    def _serialize_points(points: list[Point2D]) -> list[dict[str, float]]:
        return [
            {
                "x": point.x,
                "y": point.y,
            }
            for point in points
        ]

    def _serialize_operator_frame_state(self, state: OperatorFrameState) -> dict:
        payload = {
            "id": state.id,
            "position": {
                "x": state.position.x,
                "y": state.position.y,
            },
            "rotation": state.rotation,
            "display_mode": self._display_mode_from_flags(state.show_icon, state.show_name).value,
            "show_icon": state.show_icon,
            "show_name": state.show_name,
            "floor_key": state.floor_key,
            "transition_mode": state.transition_mode.value,
            "manual_interaction_ids": list(state.manual_interaction_ids),
            "gadget_used_count": state.gadget_used_count,
            "ability_used_count": state.ability_used_count,
            "gadget_positions_explicit": state.gadget_positions is not None,
            "ability_positions_explicit": state.ability_positions is not None,
        }
        if state.gadget_positions is not None:
            payload["gadget_positions"] = self._serialize_points(state.gadget_positions)
        if state.ability_positions is not None:
            payload["ability_positions"] = self._serialize_points(state.ability_positions)
        return payload

    @staticmethod
    def _load_optional_points(state: dict, key: str, explicit_key: str) -> list[Point2D] | None:
        if explicit_key in state:
            if not bool(state.get(explicit_key, False)):
                return None
            raw_points = state.get(key, [])
        else:
            raw_points = state.get(key)
            if not raw_points:
                return None

        return [
            Point2D(
                x=float(point.get("x", 0)),
                y=float(point.get("y", 0)),
            )
            for point in raw_points
            if isinstance(point, dict)
        ]
