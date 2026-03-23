import json
from pathlib import Path

from r6_tactics_board.domain.models import (
    Keyframe,
    MapInfo,
    OperatorDefinition,
    OperatorDisplayMode,
    OperatorFrameState,
    OperatorState,
    Point2D,
    TacticProject,
    TeamSide,
    Timeline,
)


class ProjectStore:
    """JSON persistence for tactic projects."""

    def load(self, path: str) -> TacticProject:
        project_path = Path(path).resolve()
        data = json.loads(project_path.read_text(encoding="utf-8"))

        map_info = None
        if data.get("map_info") is not None:
            image_path = data["map_info"].get("image_path", "")
            map_info = MapInfo(
                key=data["map_info"].get("key", ""),
                name=data["map_info"].get("name", ""),
                image_path=self._resolve_path(project_path.parent, image_path),
            )

        operators = self._load_operator_definitions(data)
        keyframes = [
            Keyframe(
                time_ms=item.get("time_ms", 0),
                name=item.get("name", ""),
                note=item.get("note", ""),
                operator_frames=[
                    OperatorFrameState(
                        id=state["id"],
                        position=Point2D(
                            x=state["position"]["x"],
                            y=state["position"]["y"],
                        ),
                        rotation=state.get("rotation", 0.0),
                        display_mode=OperatorDisplayMode(
                            state.get("display_mode", OperatorDisplayMode.ICON.value)
                        ),
                    )
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
            operator_order=data.get("operator_order", []),
            current_keyframe_index=data.get("current_keyframe_index", 0),
            transition_duration_ms=data.get("transition_duration_ms", 700),
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
            },
            "operators": [
                {
                    "id": operator.id,
                    "custom_name": operator.custom_name,
                    "side": operator.side.value,
                    "operator_key": operator.operator_key,
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
                            {
                                "id": state.id,
                                "position": {
                                    "x": state.position.x,
                                    "y": state.position.y,
                                },
                                "rotation": state.rotation,
                                "display_mode": state.display_mode.value,
                            }
                            for state in keyframe.operator_frames
                        ],
                    }
                    for keyframe in project.timeline.keyframes
                ]
            },
            "operator_order": project.operator_order,
            "current_keyframe_index": project.current_keyframe_index,
            "transition_duration_ms": project.transition_duration_ms,
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
                )

        return list(inferred.values())
