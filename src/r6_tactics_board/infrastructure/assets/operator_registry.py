from __future__ import annotations

import json
from pathlib import Path

from r6_tactics_board.infrastructure.assets.asset_models import (
    OperatorAsset,
    OperatorCatalogEntry,
    OperatorGadgetOption,
)
from r6_tactics_board.infrastructure.assets.asset_paths import (
    ATTACK_OPERATORS_DIR,
    DEFENSE_OPERATORS_DIR,
    OPERATORS_DIR,
)
from r6_tactics_board.infrastructure.assets.asset_utils import (
    list_image_files,
    normalize_operator_lookup,
    resolve_asset_path,
)


class OperatorAssetRegistry:
    """Operator icon/catalog loading and operator-level count write-back."""

    def __init__(self) -> None:
        self._operator_catalog_cache: dict[str | None, list[OperatorCatalogEntry]] = {}

    def list_operator_assets(self, side: str | None = None) -> list[OperatorAsset]:
        assets: list[OperatorAsset] = []
        if side in (None, "attack"):
            assets.extend(self._operator_assets_from_dir(ATTACK_OPERATORS_DIR / "icons", "attack"))
        if side in (None, "defense"):
            assets.extend(self._operator_assets_from_dir(DEFENSE_OPERATORS_DIR / "icons", "defense"))
        return sorted(assets, key=lambda item: (item.side, item.key))

    def find_operator_asset(self, side: str, key: str) -> OperatorAsset | None:
        for asset in self.list_operator_assets(side):
            if asset.key == key:
                return asset
        return None

    def list_operator_catalog(self, side: str | None = None) -> list[OperatorCatalogEntry]:
        if side in self._operator_catalog_cache:
            return list(self._operator_catalog_cache[side])

        entries = self._load_operator_catalog(side)
        if entries:
            self._operator_catalog_cache[side] = entries
            return list(entries)

        fallback_entries = [
            OperatorCatalogEntry(
                key=asset.key,
                side=asset.side,
                name=asset.key,
                icon_path=asset.path,
            )
            for asset in self.list_operator_assets(side)
        ]
        self._operator_catalog_cache[side] = fallback_entries
        return list(fallback_entries)

    def find_operator_catalog_entry(
        self,
        value: str,
        side: str | None = None,
    ) -> OperatorCatalogEntry | None:
        normalized = normalize_operator_lookup(value)
        if not normalized:
            return None

        for entry in self.list_operator_catalog(side):
            if normalized in {
                normalize_operator_lookup(entry.key),
                normalize_operator_lookup(entry.name),
            }:
                return entry
        return None

    def save_operator_gadget_count(self, side: str, operator_key: str, gadget_key: str, count: int) -> None:
        def updater(item: dict) -> None:
            gadgets = [
                {
                    "key": str(gadget.get("key", "")),
                    "max_count": max(0, int(gadget.get("max_count", 0))),
                }
                for gadget in item.get("gadgets", [])
                if str(gadget.get("key", ""))
            ]
            gadgets = [gadget for gadget in gadgets if gadget["key"] != gadget_key]
            if count > 0:
                gadgets.append({"key": gadget_key, "max_count": int(count)})
            gadgets.sort(key=lambda gadget: gadget["key"])
            item["gadgets"] = gadgets

        if self._update_operator_item(side, operator_key, updater):
            self.invalidate_cache()

    def save_operator_ability_count(self, side: str, operator_key: str, count: int) -> None:
        def updater(item: dict) -> None:
            item["ability_max_count"] = max(0, int(count))

        if self._update_operator_item(side, operator_key, updater):
            self.invalidate_cache()

    def save_operator_ability_persistence(self, side: str, operator_key: str, persists_on_map: bool) -> None:
        def updater(item: dict) -> None:
            item["ability_persists_on_map"] = bool(persists_on_map)

        if self._update_operator_item(side, operator_key, updater):
            self.invalidate_cache()

    def invalidate_cache(self) -> None:
        self._operator_catalog_cache.clear()

    def _load_operator_catalog(self, side: str | None) -> list[OperatorCatalogEntry]:
        index_path = OPERATORS_DIR / "index.json"
        if not index_path.is_file():
            return []

        try:
            raw_items = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        entries: list[OperatorCatalogEntry] = []
        for item in raw_items:
            entry_side = str(item.get("side", ""))
            if side is not None and entry_side != side:
                continue
            entries.append(
                OperatorCatalogEntry(
                    key=str(item.get("key", "")),
                    side=entry_side,
                    name=str(item.get("name", "")),
                    icon_path=str(resolve_asset_path(index_path.parent, str(item.get("icon_path", "")))),
                    portrait_path=str(resolve_asset_path(index_path.parent, str(item.get("portrait_path", "")))),
                    ability_icon_path=str(
                        resolve_asset_path(index_path.parent, str(item.get("ability_icon_path", "")))
                    ),
                    ability_name=str(item.get("ability_name", "")),
                    ability_description=str(item.get("ability_description", "")),
                    ability_max_count=max(0, int(item.get("ability_max_count", 0))),
                    ability_persists_on_map=bool(item.get("ability_persists_on_map", True)),
                    gadgets=[
                        OperatorGadgetOption(
                            key=str(gadget.get("key", "")),
                            max_count=max(0, int(gadget.get("max_count", 0))),
                        )
                        for gadget in item.get("gadgets", [])
                        if str(gadget.get("key", ""))
                    ],
                )
            )
        return sorted(entries, key=lambda item: (item.side, item.key))

    def _update_operator_item(self, side: str, operator_key: str, updater) -> bool:
        index_path = OPERATORS_DIR / "index.json"
        if not index_path.is_file():
            return False

        try:
            raw_items = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False

        updated = False
        for item in raw_items:
            if str(item.get("side", "")) != side or str(item.get("key", "")) != operator_key:
                continue
            updater(item)
            updated = True
            break

        if not updated:
            return False

        self._write_json(index_path, raw_items)
        return True

    @staticmethod
    def _operator_assets_from_dir(directory: Path, side: str) -> list[OperatorAsset]:
        return [
            OperatorAsset(key=file.stem, side=side, path=str(file))
            for file in list_image_files(directory)
        ]

    @staticmethod
    def _write_json(path: Path, data: object) -> None:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
            newline="\n",
        )
