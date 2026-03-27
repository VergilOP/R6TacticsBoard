from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EsportsMapSummary:
    source: str
    map_key: str
    map_name: str
    last_updated: str
    total_matches: int
    total_rounds: int
    flawless_count: int
    teams: dict[str, int] = field(default_factory=dict)
    raw_data: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class EsportsMatchRecord:
    source: str
    map_key: str
    map_name: str
    date: str
    tournament: str
    stage: str
    match_id: str
    match_ref: str
    atk_team: str
    def_team: str
    atk_score: int
    def_score: int
    atk_bans: list[str] = field(default_factory=list)
    def_bans: list[str] = field(default_factory=list)
    atk_operators: list[str] = field(default_factory=list)
    def_operators: list[str] = field(default_factory=list)
    atk_deaths: int = 0
    def_deaths: int = 0
    total_deaths: int = 0
    first_attack: str = ""
    pick: str = ""
    finished: bool = False
    is_flawless: bool = False
    raw_map_block: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def winner_team(self) -> str:
        if self.atk_score > self.def_score:
            return self.atk_team
        if self.def_score > self.atk_score:
            return self.def_team
        return ""

    @property
    def loser_team(self) -> str:
        if self.atk_score > self.def_score:
            return self.def_team
        if self.def_score > self.atk_score:
            return self.atk_team
        return ""

    @property
    def scoreline(self) -> str:
        return f"{self.atk_score}:{self.def_score}"


@dataclass(slots=True)
class EsportsMapDataset:
    source: str
    map_key: str
    summary: EsportsMapSummary | None
    matches: list[EsportsMatchRecord] = field(default_factory=list)
    summary_fields: list[str] = field(default_factory=list)
    match_fields: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EsportsMapEntry:
    map_key: str
    display_name: str
    total_matches: int = 0
