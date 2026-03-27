from __future__ import annotations

import json
from pathlib import Path

from r6_tactics_board.domain.esports_models import (
    EsportsMapDataset,
    EsportsMapEntry,
    EsportsMapSummary,
    EsportsMatchRecord,
)
from r6_tactics_board.infrastructure.assets.asset_paths import PROJECT_ROOT


class EsportsStore:
    def __init__(self) -> None:
        self.source_name = "local_json"
        self.data_root = self._resolve_data_root()
        self.maps_dir = self.data_root / "maps"

    def is_available(self) -> bool:
        return self.maps_dir.is_dir()

    def list_map_entries(self) -> list[EsportsMapEntry]:
        if not self.maps_dir.is_dir():
            return []

        entries: list[EsportsMapEntry] = []
        for map_dir in sorted(item for item in self.maps_dir.iterdir() if item.is_dir()):
            summary = self._load_summary(map_dir.name)
            raw_matches = self._load_matches(map_dir.name)
            total_matches = summary.total_matches if summary is not None else len(raw_matches)
            if total_matches <= 0:
                continue
            display_name = summary.map_name if summary is not None else self._humanize_map_key(map_dir.name)
            entries.append(
                EsportsMapEntry(
                    map_key=map_dir.name,
                    display_name=display_name,
                    total_matches=total_matches,
                )
            )
        return entries

    def load_map_dataset(self, map_key: str) -> EsportsMapDataset | None:
        map_dir = self.maps_dir / map_key
        if not map_dir.is_dir():
            return None

        summary = self._load_summary(map_key)
        matches = self._load_matches(map_key)

        summary_fields = sorted(summary.raw_data.keys()) if summary is not None else []
        match_fields = sorted({key for item in matches for key in item.raw_data.keys()})

        return EsportsMapDataset(
            source=self.source_name,
            map_key=map_key,
            summary=summary,
            matches=matches,
            summary_fields=summary_fields,
            match_fields=match_fields,
        )

    def _load_summary(self, map_key: str) -> EsportsMapSummary | None:
        path = self.maps_dir / map_key / "summary.json"
        if not path.is_file():
            return None

        try:
            raw_data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        return self._build_summary(map_key, raw_data)

    def _load_matches(self, map_key: str) -> list[EsportsMatchRecord]:
        path = self.maps_dir / map_key / "raw_matches.json"
        if not path.is_file():
            return []

        try:
            raw_items = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        matches: list[EsportsMatchRecord] = []
        for raw_data in raw_items:
            if not isinstance(raw_data, dict):
                continue

            matches.append(self._build_match_record(map_key, raw_data))

        return matches

    def _build_summary(self, map_key: str, raw_data: dict) -> EsportsMapSummary:
        return EsportsMapSummary(
            source=self.source_name,
            map_key=map_key,
            map_name=self._coerce_text(raw_data.get("map", self._humanize_map_key(map_key))),
            last_updated=self._coerce_text(raw_data.get("last_updated", "")),
            total_matches=self._coerce_int(raw_data.get("total_matches", 0)),
            total_rounds=self._coerce_int(raw_data.get("total_rounds", 0)),
            flawless_count=self._coerce_int(raw_data.get("flawless_count", 0)),
            teams={
                self._coerce_text(team): self._coerce_int(count)
                for team, count in dict(raw_data.get("teams", {})).items()
                if self._coerce_text(team)
            },
            raw_data=raw_data,
        )

    def _build_match_record(self, map_key: str, raw_data: dict) -> EsportsMatchRecord:
        return EsportsMatchRecord(
            source=self.source_name,
            map_key=map_key,
            map_name=self._coerce_text(raw_data.get("map", self._humanize_map_key(map_key))),
            date=self._coerce_text(raw_data.get("date", "")),
            tournament=self._coerce_text(raw_data.get("tournament", "")),
            stage=self._coerce_text(raw_data.get("stage", "")),
            match_id=self._coerce_text(raw_data.get("match_id", "")),
            match_ref=self._coerce_text(raw_data.get("match_ref", "")),
            atk_team=self._coerce_text(raw_data.get("atk_team", "")),
            def_team=self._coerce_text(raw_data.get("def_team", "")),
            atk_score=self._coerce_int(raw_data.get("atk_score", 0)),
            def_score=self._coerce_int(raw_data.get("def_score", 0)),
            atk_bans=self._coerce_list(raw_data.get("atk_bans", [])),
            def_bans=self._coerce_list(raw_data.get("def_bans", [])),
            atk_operators=self._coerce_list(raw_data.get("atk_operators", [])),
            def_operators=self._coerce_list(raw_data.get("def_operators", [])),
            atk_deaths=self._coerce_int(raw_data.get("atk_deaths", 0)),
            def_deaths=self._coerce_int(raw_data.get("def_deaths", 0)),
            total_deaths=self._coerce_int(raw_data.get("total_deaths", 0)),
            first_attack=self._coerce_text(raw_data.get("first_attack", "")),
            pick=self._coerce_text(raw_data.get("pick", "")),
            finished=bool(raw_data.get("finished", False)),
            is_flawless=bool(raw_data.get("is_flawless", False)),
            raw_map_block=self._coerce_text(raw_data.get("raw_map_block", "")),
            raw_data=raw_data,
        )

    @staticmethod
    def _resolve_data_root() -> Path:
        candidates = (
            PROJECT_ROOT / "data" / "esports",
            PROJECT_ROOT.parent / "data" / "esports",
        )
        for candidate in candidates:
            if candidate.is_dir():
                return candidate
        return candidates[0]

    @staticmethod
    def _humanize_map_key(map_key: str) -> str:
        return map_key.replace("-", " ").title()

    @staticmethod
    def _coerce_text(value: object) -> str:
        return str(value or "")

    @staticmethod
    def _coerce_int(value: object) -> int:
        return int(value or 0)

    def _coerce_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [self._coerce_text(item) for item in value if self._coerce_text(item)]
