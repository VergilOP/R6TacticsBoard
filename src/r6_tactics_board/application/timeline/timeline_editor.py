from copy import deepcopy

from r6_tactics_board.domain.models import OperatorDefinition, OperatorFrameState


class TimelineEditorController:
    @staticmethod
    def add_keyframe_column(
        keyframe_columns: list[dict[str, OperatorFrameState]],
        keyframe_names: list[str],
        keyframe_notes: list[str],
    ) -> tuple[list[dict[str, OperatorFrameState]], list[str], list[str], int]:
        columns = list(keyframe_columns)
        names = list(keyframe_names)
        notes = list(keyframe_notes)
        columns.append({})
        names.append("")
        notes.append("")
        return columns, names, notes, len(columns) - 1

    @staticmethod
    def insert_keyframe_column(
        keyframe_columns: list[dict[str, OperatorFrameState]],
        keyframe_names: list[str],
        keyframe_notes: list[str],
        current_keyframe_index: int,
    ) -> tuple[list[dict[str, OperatorFrameState]], list[str], list[str], int]:
        columns = list(keyframe_columns)
        names = list(keyframe_names)
        notes = list(keyframe_notes)
        insert_index = min(current_keyframe_index + 1, len(columns))
        columns.insert(insert_index, {})
        names.insert(insert_index, "")
        notes.insert(insert_index, "")
        return columns, names, notes, insert_index

    @staticmethod
    def duplicate_keyframe_column(
        keyframe_columns: list[dict[str, OperatorFrameState]],
        keyframe_names: list[str],
        keyframe_notes: list[str],
        current_keyframe_index: int,
    ) -> tuple[list[dict[str, OperatorFrameState]], list[str], list[str], int]:
        columns = list(keyframe_columns)
        names = list(keyframe_names)
        notes = list(keyframe_notes)
        duplicate = {
            operator_id: deepcopy(state)
            for operator_id, state in columns[current_keyframe_index].items()
        }
        insert_index = current_keyframe_index + 1
        columns.insert(insert_index, duplicate)
        source_name = names[current_keyframe_index]
        names.insert(insert_index, f"{source_name} 副本" if source_name else "")
        notes.insert(insert_index, notes[current_keyframe_index])
        return columns, names, notes, insert_index

    @staticmethod
    def delete_keyframe_column(
        keyframe_columns: list[dict[str, OperatorFrameState]],
        keyframe_names: list[str],
        keyframe_notes: list[str],
        current_keyframe_index: int,
        column_index: int,
    ) -> tuple[list[dict[str, OperatorFrameState]], list[str], list[str], int, int]:
        if len(keyframe_columns) == 1:
            return [{}], [""], [""], 0, -1

        columns = list(keyframe_columns)
        names = list(keyframe_names)
        notes = list(keyframe_notes)
        del columns[column_index]
        del names[column_index]
        del notes[column_index]
        return columns, names, notes, min(current_keyframe_index, len(columns) - 1), current_keyframe_index

    @staticmethod
    def set_cell(
        keyframe_columns: list[dict[str, OperatorFrameState]],
        column_index: int,
        operator_id: str,
        state: OperatorFrameState,
    ) -> list[dict[str, OperatorFrameState]]:
        columns = list(keyframe_columns)
        frame = dict(columns[column_index])
        frame[operator_id] = state
        columns[column_index] = frame
        return columns

    @staticmethod
    def clear_cell(
        keyframe_columns: list[dict[str, OperatorFrameState]],
        column_index: int,
        operator_id: str,
    ) -> list[dict[str, OperatorFrameState]]:
        columns = list(keyframe_columns)
        frame = dict(columns[column_index])
        frame.pop(operator_id, None)
        columns[column_index] = frame
        return columns

    @staticmethod
    def move_keyframe_column(
        keyframe_columns: list[dict[str, OperatorFrameState]],
        keyframe_names: list[str],
        keyframe_notes: list[str],
        current_keyframe_index: int,
        from_index: int,
        to_index: int,
    ) -> tuple[list[dict[str, OperatorFrameState]], list[str], list[str], int]:
        columns = list(keyframe_columns)
        names = list(keyframe_names)
        notes = list(keyframe_notes)
        column = columns.pop(from_index)
        columns.insert(to_index, column)
        keyframe_name = names.pop(from_index)
        keyframe_note = notes.pop(from_index)
        names.insert(to_index, keyframe_name)
        notes.insert(to_index, keyframe_note)
        return columns, names, notes, TimelineEditorController.moved_index(current_keyframe_index, from_index, to_index)

    @staticmethod
    def move_operator_row(
        operator_order: list[str],
        current_timeline_row: int,
        from_index: int,
        to_index: int,
    ) -> tuple[list[str], int]:
        order = list(operator_order)
        operator_id = order.pop(from_index)
        order.insert(to_index, operator_id)
        return order, TimelineEditorController.moved_index(current_timeline_row, from_index, to_index)

    @staticmethod
    def remove_operator_from_timeline(
        keyframe_columns: list[dict[str, OperatorFrameState]],
        operator_definitions: dict[str, OperatorDefinition],
        operator_id: str,
    ) -> tuple[list[dict[str, OperatorFrameState]], dict[str, OperatorDefinition]]:
        columns = [dict(frame) for frame in keyframe_columns]
        for frame in columns:
            frame.pop(operator_id, None)
        definitions = dict(operator_definitions)
        definitions.pop(operator_id, None)
        return columns, definitions

    @staticmethod
    def update_keyframe_name(
        keyframe_names: list[str],
        current_keyframe_index: int,
        name: str,
    ) -> list[str]:
        names = list(keyframe_names)
        names[current_keyframe_index] = name.strip()
        return names

    @staticmethod
    def update_keyframe_note(
        keyframe_notes: list[str],
        current_keyframe_index: int,
        note: str,
    ) -> list[str]:
        notes = list(keyframe_notes)
        notes[current_keyframe_index] = note.strip()
        return notes

    @staticmethod
    def moved_index(current_index: int, from_index: int, to_index: int) -> int:
        if current_index == from_index:
            return to_index
        if from_index < current_index <= to_index:
            return current_index - 1
        if to_index <= current_index < from_index:
            return current_index + 1
        return current_index
