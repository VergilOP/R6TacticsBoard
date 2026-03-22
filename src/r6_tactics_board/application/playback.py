from dataclasses import dataclass


@dataclass(slots=True)
class PlaybackState:
    current_time_ms: int = 0
    is_playing: bool = False


class PlaybackController:
    """Placeholder playback controller for the timeline system."""

    def __init__(self) -> None:
        self.state = PlaybackState()

    def play(self) -> None:
        self.state.is_playing = True

    def pause(self) -> None:
        self.state.is_playing = False

    def seek(self, time_ms: int) -> None:
        self.state.current_time_ms = max(0, time_ms)
