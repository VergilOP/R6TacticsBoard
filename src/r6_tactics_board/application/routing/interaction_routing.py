from copy import deepcopy
from dataclasses import dataclass
from heapq import heappop, heappush
from math import hypot

from r6_tactics_board.domain.models import (
    MapInteractionPoint,
    OperatorState,
    OperatorTransitionMode,
    Point2D,
)


@dataclass(slots=True)
class PlaybackRouteSegment:
    floor_key: str
    start: Point2D
    end: Point2D
    result_floor_key: str


class InteractionRoutePlanner:
    def __init__(self, interactions: list[MapInteractionPoint] | None = None) -> None:
        self._interactions = list(interactions or [])

    def available_manual_interactions(
        self,
        start_state: OperatorState,
        end_state: OperatorState,
        default_floor_key: str,
    ) -> list[MapInteractionPoint]:
        start_floor = start_state.floor_key or default_floor_key
        end_floor = end_state.floor_key or start_floor
        candidates: list[tuple[MapInteractionPoint, str]] = []
        for interaction in self._interactions:
            target_floor = self.resolve_manual_target_floor(interaction, start_floor)
            if target_floor is None:
                continue
            if not self.can_reach_floor(target_floor, end_floor):
                continue
            candidates.append((interaction, target_floor))
        return sorted(
            [item for item, _ in candidates],
            key=lambda item: (item.floor_key, item.id),
        )

    def can_reach_floor(self, start_floor: str | None, end_floor: str) -> bool:
        if not start_floor:
            return False
        if start_floor == end_floor:
            return True
        seen = {start_floor}
        queue = [start_floor]
        while queue:
            current_floor = queue.pop(0)
            for _, target_floor in self.iter_interaction_transitions(current_floor):
                if target_floor == end_floor:
                    return True
                if target_floor not in seen:
                    seen.add(target_floor)
                    queue.append(target_floor)
        return False

    def build_transition_route(
        self,
        start_state: OperatorState,
        end_state: OperatorState,
        *,
        default_floor_key: str,
        transition_mode: OperatorTransitionMode = OperatorTransitionMode.AUTO,
        manual_interaction_ids: list[str] | None = None,
    ) -> list[PlaybackRouteSegment]:
        start_floor = start_state.floor_key or default_floor_key
        end_floor = end_state.floor_key or start_floor
        if start_floor == end_floor:
            return [
                PlaybackRouteSegment(
                    floor_key=start_floor,
                    start=Point2D(start_state.position.x, start_state.position.y),
                    end=Point2D(end_state.position.x, end_state.position.y),
                    result_floor_key=end_floor,
                )
            ]

        interaction_steps = self.find_interaction_route(
            start_state,
            end_state,
            default_floor_key=default_floor_key,
            transition_mode=transition_mode,
            manual_interaction_ids=manual_interaction_ids or [],
        )
        if not interaction_steps:
            return [
                PlaybackRouteSegment(
                    floor_key=start_floor,
                    start=Point2D(start_state.position.x, start_state.position.y),
                    end=Point2D(end_state.position.x, end_state.position.y),
                    result_floor_key=end_floor,
                )
            ]

        segments: list[PlaybackRouteSegment] = []
        current_floor = start_floor
        current_point = Point2D(start_state.position.x, start_state.position.y)

        for interaction, target_floor in interaction_steps:
            interaction_point = Point2D(interaction.position.x, interaction.position.y)
            segments.append(
                PlaybackRouteSegment(
                    floor_key=current_floor,
                    start=Point2D(current_point.x, current_point.y),
                    end=Point2D(interaction_point.x, interaction_point.y),
                    result_floor_key=target_floor,
                )
            )
            current_floor = target_floor
            current_point = Point2D(interaction_point.x, interaction_point.y)

        segments.append(
            PlaybackRouteSegment(
                floor_key=end_floor,
                start=Point2D(current_point.x, current_point.y),
                end=Point2D(end_state.position.x, end_state.position.y),
                result_floor_key=end_floor,
            )
        )
        return segments

    def find_interaction_route(
        self,
        start_state: OperatorState,
        end_state: OperatorState,
        *,
        default_floor_key: str,
        transition_mode: OperatorTransitionMode,
        manual_interaction_ids: list[str],
    ) -> list[tuple[MapInteractionPoint, str]]:
        if not self._interactions:
            return []

        start_floor = start_state.floor_key or default_floor_key
        end_floor = end_state.floor_key or start_floor
        if start_floor == end_floor:
            return []

        if transition_mode == OperatorTransitionMode.MANUAL and manual_interaction_ids:
            manual_prefix = self.manual_interaction_prefix(start_floor, manual_interaction_ids)
            if manual_prefix is not None:
                route_prefix, current_floor = manual_prefix
                if current_floor == end_floor:
                    return route_prefix

                prefix_point = Point2D(start_state.position.x, start_state.position.y)
                if route_prefix:
                    last_interaction, _ = route_prefix[-1]
                    prefix_point = Point2D(last_interaction.position.x, last_interaction.position.y)

                continuation_start = self.copy_state_with_position(
                    start_state,
                    prefix_point,
                    current_floor,
                )
                suffix = self.find_automatic_interaction_route(
                    continuation_start,
                    end_state,
                    default_floor_key=default_floor_key,
                )
                if suffix:
                    return route_prefix + suffix

        return self.find_automatic_interaction_route(
            start_state,
            end_state,
            default_floor_key=default_floor_key,
        )

    def find_automatic_interaction_route(
        self,
        start_state: OperatorState,
        end_state: OperatorState,
        *,
        default_floor_key: str,
    ) -> list[tuple[MapInteractionPoint, str]]:
        start_floor = start_state.floor_key or default_floor_key
        end_floor = end_state.floor_key or start_floor
        if start_floor == end_floor:
            return []

        goal_key = ("goal", "")
        start_key = ("start", start_floor)
        best_costs: dict[tuple[str, str], float] = {start_key: 0.0}
        parents: dict[tuple[str, str], tuple[tuple[str, str], MapInteractionPoint | None, str]] = {}
        node_positions: dict[tuple[str, str], Point2D] = {
            start_key: Point2D(start_state.position.x, start_state.position.y)
        }
        heap: list[tuple[float, str, str]] = [(0.0, start_key[0], start_key[1])]

        while heap:
            current_cost, current_kind, current_floor = heappop(heap)
            current_key = (current_kind, current_floor)
            if current_cost > best_costs.get(current_key, float("inf")):
                continue
            if current_key == goal_key:
                break

            current_point = node_positions[current_key]
            if current_floor == end_floor:
                goal_cost = current_cost + self.distance_points(current_point, end_state.position)
                if goal_cost < best_costs.get(goal_key, float("inf")):
                    best_costs[goal_key] = goal_cost
                    parents[goal_key] = (current_key, None, end_floor)
                    node_positions[goal_key] = Point2D(end_state.position.x, end_state.position.y)
                    heappush(heap, (goal_cost, goal_key[0], goal_key[1]))

            for interaction, target_floor in self.iter_interaction_transitions(current_floor):
                next_key = (interaction.id, target_floor)
                interaction_point = Point2D(interaction.position.x, interaction.position.y)
                travel_cost = self.distance_points(current_point, interaction_point)
                next_cost = current_cost + travel_cost
                if next_cost >= best_costs.get(next_key, float("inf")):
                    continue
                best_costs[next_key] = next_cost
                parents[next_key] = (current_key, interaction, target_floor)
                node_positions[next_key] = Point2D(interaction.position.x, interaction.position.y)
                heappush(heap, (next_cost, next_key[0], next_key[1]))

        if goal_key not in parents:
            return []

        steps: list[tuple[MapInteractionPoint, str]] = []
        current_key = goal_key
        while current_key != start_key:
            parent_key, interaction, target_floor = parents[current_key]
            if interaction is not None:
                steps.append((interaction, target_floor))
            current_key = parent_key
        steps.reverse()
        return steps

    def manual_interaction_prefix(
        self,
        start_floor: str,
        manual_interaction_ids: list[str],
    ) -> tuple[list[tuple[MapInteractionPoint, str]], str] | None:
        interactions_by_id = {
            interaction.id: interaction
            for interaction in self._interactions
        }
        route: list[tuple[MapInteractionPoint, str]] = []
        current_floor = start_floor

        for interaction_id in manual_interaction_ids:
            interaction = interactions_by_id.get(interaction_id)
            if interaction is None:
                return None
            target_floor = self.resolve_manual_target_floor(interaction, current_floor)
            if target_floor is None:
                return None
            route.append((interaction, target_floor))
            current_floor = target_floor

        return route, current_floor

    def iter_interaction_transitions(self, floor_key: str) -> list[tuple[MapInteractionPoint, str]]:
        transitions: list[tuple[MapInteractionPoint, str]] = []
        for interaction in self._interactions:
            if interaction.floor_key == floor_key:
                for target_floor in interaction.linked_floor_keys:
                    transitions.append((interaction, target_floor))
            elif interaction.is_bidirectional and floor_key in interaction.linked_floor_keys:
                transitions.append((interaction, interaction.floor_key))
        return transitions

    def state_on_route(
        self,
        start_state: OperatorState,
        end_state: OperatorState,
        route: list[PlaybackRouteSegment],
        progress: float,
        *,
        default_floor_key: str,
    ) -> OperatorState:
        total_length = sum(self.route_segment_length(segment) for segment in route)
        if total_length <= 0.001:
            return deepcopy(end_state)

        target_distance = total_length * progress
        traveled = 0.0
        current_floor = start_state.floor_key or default_floor_key
        current_point = Point2D(start_state.position.x, start_state.position.y)

        for segment in route:
            length = self.route_segment_length(segment)
            if length <= 0.001:
                if target_distance <= traveled:
                    return self.copy_state_with_position(
                        start_state,
                        current_point,
                        current_floor,
                    )
                current_floor = segment.result_floor_key or current_floor
                current_point = Point2D(segment.end.x, segment.end.y)
                continue

            if target_distance <= traveled + length or segment is route[-1]:
                local_progress = max(0.0, min(1.0, (target_distance - traveled) / length))
                position = Point2D(
                    x=segment.start.x + (segment.end.x - segment.start.x) * local_progress,
                    y=segment.start.y + (segment.end.y - segment.start.y) * local_progress,
                )
                floor_key = segment.floor_key
                if local_progress >= 1.0 and segment.result_floor_key:
                    floor_key = segment.result_floor_key
                return self.copy_state_with_position(end_state, position, floor_key)

            traveled += length
            current_floor = segment.result_floor_key or current_floor
            current_point = Point2D(segment.end.x, segment.end.y)

        return deepcopy(end_state)

    def preview_segment_on_route(
        self,
        start_state: OperatorState,
        end_state: OperatorState,
        route: list[PlaybackRouteSegment],
        progress: float,
        *,
        current_floor_key: str,
    ) -> tuple[OperatorState, OperatorState] | None:
        if not route:
            if (
                start_state.floor_key
                and start_state.floor_key != current_floor_key
            ) or (
                end_state.floor_key
                and end_state.floor_key != current_floor_key
            ):
                return None
            return (start_state, end_state)

        total_length = sum(self.route_segment_length(segment) for segment in route)
        if total_length <= 0.001:
            return None

        target_distance = total_length * progress
        traveled = 0.0
        for segment in route:
            length = self.route_segment_length(segment)
            if length <= 0.001:
                continue
            if target_distance <= traveled + length or segment is route[-1]:
                if segment.floor_key != current_floor_key:
                    return None
                segment_start = self.copy_state_with_position(start_state, segment.start, segment.floor_key)
                segment_end = self.copy_state_with_position(end_state, segment.end, segment.floor_key)
                return (segment_start, segment_end)
            traveled += length
        return None

    @staticmethod
    def resolve_manual_target_floor(
        interaction: MapInteractionPoint,
        current_floor: str,
    ) -> str | None:
        if interaction.floor_key == current_floor:
            return interaction.linked_floor_keys[0] if interaction.linked_floor_keys else None
        if interaction.is_bidirectional and current_floor in interaction.linked_floor_keys:
            return interaction.floor_key
        return None

    @staticmethod
    def copy_state_with_position(
        template: OperatorState,
        position: Point2D,
        floor_key: str,
    ) -> OperatorState:
        return OperatorState(
            id=template.id,
            operator_key=template.operator_key,
            custom_name=template.custom_name,
            side=template.side,
            position=Point2D(position.x, position.y),
            rotation=template.rotation,
            display_mode=template.display_mode,
            floor_key=floor_key,
        )

    @staticmethod
    def route_segment_length(segment: PlaybackRouteSegment) -> float:
        return hypot(segment.end.x - segment.start.x, segment.end.y - segment.start.y)

    @staticmethod
    def distance_points(first: Point2D, second: Point2D) -> float:
        return hypot(second.x - first.x, second.y - first.y)
