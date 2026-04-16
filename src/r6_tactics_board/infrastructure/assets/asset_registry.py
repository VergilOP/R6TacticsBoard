from __future__ import annotations

from r6_tactics_board.infrastructure.assets.asset_models import (
    GadgetAsset,
    MapAsset,
    MapFloorAsset,
    MapOverview2p5dAsset,
    OperatorAsset,
    OperatorCatalogEntry,
    OperatorGadgetOption,
)
from r6_tactics_board.infrastructure.assets.asset_paths import ensure_asset_directories
from r6_tactics_board.infrastructure.assets.gadget_registry import GadgetAssetRegistry
from r6_tactics_board.infrastructure.assets.map_registry import MapAssetRegistry
from r6_tactics_board.infrastructure.assets.operator_registry import OperatorAssetRegistry


class AssetRegistry:
    """Compatibility facade for map, operator and gadget asset registries."""

    def __init__(self) -> None:
        ensure_asset_directories()
        self._maps = MapAssetRegistry()
        self._operators = OperatorAssetRegistry()
        self._gadgets = GadgetAssetRegistry()

    def list_map_assets(self) -> list[MapAsset]:
        return self._maps.list_map_assets()

    def load_map_asset(self, map_json_path: str) -> MapAsset | None:
        return self._maps.load_map_asset(map_json_path)

    def find_map_asset(self, key: str) -> MapAsset | None:
        return self._maps.find_map_asset(key)

    def save_map_interactions(self, map_json_path: str, interactions) -> None:
        self._maps.save_map_interactions(map_json_path, interactions)

    def save_map_surfaces(self, map_json_path: str, surfaces) -> None:
        self._maps.save_map_surfaces(map_json_path, surfaces)

    def list_operator_assets(self, side: str | None = None) -> list[OperatorAsset]:
        return self._operators.list_operator_assets(side)

    def find_operator_asset(self, side: str, key: str) -> OperatorAsset | None:
        return self._operators.find_operator_asset(side, key)

    def list_operator_catalog(self, side: str | None = None) -> list[OperatorCatalogEntry]:
        return self._operators.list_operator_catalog(side)

    def find_operator_catalog_entry(
        self,
        value: str,
        side: str | None = None,
    ) -> OperatorCatalogEntry | None:
        return self._operators.find_operator_catalog_entry(value, side)

    def list_gadget_assets(self, side: str | None = None) -> list[GadgetAsset]:
        return self._gadgets.list_gadget_assets(side)

    def find_gadget_asset(self, side: str, key: str) -> GadgetAsset | None:
        return self._gadgets.find_gadget_asset(side, key)

    def save_gadget_count(self, side: str, gadget_key: str, count: int) -> None:
        self._gadgets.save_gadget_count(side, gadget_key, count)

    def save_gadget_persistence(self, side: str, gadget_key: str, persists_on_map: bool) -> None:
        self._gadgets.save_gadget_persistence(side, gadget_key, persists_on_map)

    def list_operator_gadget_assets(self, side: str, operator_key: str) -> list[GadgetAsset]:
        entry = self.find_operator_catalog_entry(operator_key, side)
        global_assets = {asset.key: asset for asset in self.list_gadget_assets(side)}
        if entry is None or not entry.gadgets:
            return sorted(global_assets.values(), key=lambda item: (item.side, item.key))

        assets: list[GadgetAsset] = []
        for option in entry.gadgets:
            if option.max_count <= 0:
                continue
            global_asset = global_assets.get(option.key)
            if global_asset is None:
                continue
            assets.append(
                GadgetAsset(
                    key=global_asset.key,
                    side=global_asset.side,
                    name=global_asset.name,
                    path=global_asset.path,
                    max_count=option.max_count,
                    persists_on_map=global_asset.persists_on_map,
                )
            )
        return sorted(assets, key=lambda item: (item.side, item.key))

    def find_operator_gadget_asset(self, side: str, operator_key: str, gadget_key: str) -> GadgetAsset | None:
        for asset in self.list_operator_gadget_assets(side, operator_key):
            if asset.key == gadget_key:
                return asset
        return None

    def save_operator_gadget_count(self, side: str, operator_key: str, gadget_key: str, count: int) -> None:
        self._operators.save_operator_gadget_count(side, operator_key, gadget_key, count)

    def save_operator_ability_count(self, side: str, operator_key: str, count: int) -> None:
        self._operators.save_operator_ability_count(side, operator_key, count)

    def save_operator_ability_persistence(self, side: str, operator_key: str, persists_on_map: bool) -> None:
        self._operators.save_operator_ability_persistence(side, operator_key, persists_on_map)
