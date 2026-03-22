import json
from pathlib import Path

from r6_tactics_board.domain.models import (
    Keyframe,
    MapInfo,
    OperatorDisplayMode,
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

        keyframes = [
            Keyframe(
                time_ms=item.get("time_ms", 0),
                operator_states=[
                    OperatorState(
                        id=state["id"],
                        operator_key=state.get("operator_key", ""),
                        custom_name=state.get("custom_name", ""),
                        side=TeamSide(state.get("side", TeamSide.ATTACK.value)),
                        position=Point2D(
                            x=state["position"]["x"],
                            y=state["position"]["y"],
                        ),
                        rotation=state.get("rotation", 0.0),
                        display_mode=OperatorDisplayMode(
                            state.get("display_mode", OperatorDisplayMode.ICON.value)
                        ),
                    )
                    for state in item.get("operator_states", [])
                ],
            )
            for item in data.get("timeline", {}).get("keyframes", [])
        ]

        return TacticProject(
            name=data.get("name", project_path.stem),
            map_info=map_info,
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
            "timeline": {
                "keyframes": [
                    {
                        "time_ms": keyframe.time_ms,
                        "operator_states": [
                            {
                                "id": state.id,
                                "operator_key": state.operator_key,
                                "custom_name": state.custom_name,
                                "side": state.side.value,
                                "position": {
                                    "x": state.position.x,
                                    "y": state.position.y,
                                },
                                "rotation": state.rotation,
                                "display_mode": state.display_mode.value,
                            }
                            for state in keyframe.operator_states
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
