from __future__ import annotations

import json
from pathlib import Path

from r6_tactics_board.infrastructure.assets.asset_models import GadgetAsset
from r6_tactics_board.infrastructure.assets.asset_paths import (
    ATTACK_GADGETS_DIR,
    DEFENSE_GADGETS_DIR,
    GADGETS_DIR,
)
from r6_tactics_board.infrastructure.assets.asset_utils import (
    default_gadget_persistence,
    list_image_files,
    resolve_asset_path,
)


class GadgetAssetRegistry:
    """Global gadget definition loading and write-back."""

    def __init__(self) -> None:
        self._gadget_assets_cache: dict[str | None, list[GadgetAsset]] = {}

    def list_gadget_assets(self, side: str | None = None) -> list[GadgetAsset]:
        if side in self._gadget_assets_cache:
            return list(self._gadget_assets_cache[side])

        entries = self._load_indexed_gadgets(side)
        if not entries:
            entries = self._fallback_gadget_assets(side)

        self._gadget_assets_cache[side] = entries
        return list(entries)

    def find_gadget_asset(self, side: str, key: str) -> GadgetAsset | None:
        for asset in self.list_gadget_assets(side):
            if asset.key == key:
                return asset
        return None

    def save_gadget_count(self, side: str, gadget_key: str, count: int) -> None:
        def updater(item: dict) -> None:
            item["max_count"] = max(0, int(count))

        if self._update_gadget_item(side, gadget_key, updater):
            self.invalidate_cache()

    def save_gadget_persistence(self, side: str, gadget_key: str, persists_on_map: bool) -> None:
        def updater(item: dict) -> None:
            item["persists_on_map"] = bool(persists_on_map)

        if self._update_gadget_item(side, gadget_key, updater):
            self.invalidate_cache()

    def invalidate_cache(self) -> None:
        self._gadget_assets_cache.clear()

    def _load_indexed_gadgets(self, side: str | None) -> list[GadgetAsset]:
        index_path = GADGETS_DIR / "index.json"
        if not index_path.is_file():
            return []

        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        entries: list[GadgetAsset] = []
        for group_side, items in data.get("groups", {}).items():
            if side is not None and group_side != side:
                continue
            for item in items:
                key = str(item.get("key", ""))
                entries.append(
                    GadgetAsset(
                        key=key,
                        side=str(item.get("side", group_side)),
                        name=str(item.get("name", key)),
                        path=str(resolve_asset_path(index_path.parent, str(item.get("icon_path", "")))),
                        max_count=max(1, int(item.get("max_count", 1))),
                        persists_on_map=bool(
                            item.get("persists_on_map", default_gadget_persistence(key))
                        ),
                    )
                )
        return sorted(entries, key=lambda item: (item.side, item.key))

    def _fallback_gadget_assets(self, side: str | None = None) -> list[GadgetAsset]:
        entries: list[GadgetAsset] = []
        if side in (None, "attack"):
            entries.extend(self._gadget_assets_from_dir(ATTACK_GADGETS_DIR, "attack"))
        if side in (None, "defense"):
            entries.extend(self._gadget_assets_from_dir(DEFENSE_GADGETS_DIR, "defense"))
        return sorted(entries, key=lambda item: (item.side, item.key))

    def _gadget_assets_from_dir(self, directory: Path, side: str) -> list[GadgetAsset]:
        return [
            GadgetAsset(
                key=file.stem,
                side=side,
                name=file.stem.replace("-", " ").title(),
                path=str(file),
                max_count=1,
                persists_on_map=default_gadget_persistence(file.stem),
            )
            for file in list_image_files(directory)
        ]

    def _update_gadget_item(self, side: str, gadget_key: str, updater) -> bool:
        index_path = GADGETS_DIR / "index.json"
        if not index_path.is_file():
            return False

        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False

        groups = data.setdefault("groups", {})
        items = groups.get(side, [])
        updated = False
        for item in items:
            if str(item.get("key", "")) != gadget_key:
                continue
            updater(item)
            updated = True
            break

        if not updated:
            return False

        self._write_json(index_path, data)
        return True

    @staticmethod
    def _write_json(path: Path, data: object) -> None:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
            newline="\n",
        )
