from dataclasses import dataclass, field
from typing import Generic, TypeVar


HistoryStateT = TypeVar("HistoryStateT")


@dataclass(slots=True)
class UndoRedoHistory(Generic[HistoryStateT]):
    limit: int = 100
    undo_stack: list[HistoryStateT] = field(default_factory=list)
    redo_stack: list[HistoryStateT] = field(default_factory=list)
    clean_snapshot: HistoryStateT | None = None

    def commit(self, before: HistoryStateT, after: HistoryStateT) -> bool:
        if before == after:
            return False
        self.undo_stack.append(before)
        if len(self.undo_stack) > self.limit:
            self.undo_stack = self.undo_stack[-self.limit :]
        self.redo_stack.clear()
        return True

    def reset(self, clean_snapshot: HistoryStateT) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.clean_snapshot = clean_snapshot

    def mark_clean(self, snapshot: HistoryStateT) -> None:
        self.clean_snapshot = snapshot

    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    def undo(self, current: HistoryStateT) -> HistoryStateT | None:
        if not self.undo_stack:
            return None
        snapshot = self.undo_stack.pop()
        self.redo_stack.append(current)
        return snapshot

    def redo(self, current: HistoryStateT) -> HistoryStateT | None:
        if not self.redo_stack:
            return None
        snapshot = self.redo_stack.pop()
        self.undo_stack.append(current)
        return snapshot

    def is_dirty(self, current: HistoryStateT) -> bool:
        return self.clean_snapshot is not None and current != self.clean_snapshot
