import sys
from pathlib import Path


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            return Path(meipass).resolve()
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


PROJECT_ROOT = _runtime_root()
ASSETS_DIR = PROJECT_ROOT / "assets"
MAPS_DIR = ASSETS_DIR / "maps"
OPERATORS_DIR = ASSETS_DIR / "operators"
ATTACK_OPERATORS_DIR = OPERATORS_DIR / "attack"
DEFENSE_OPERATORS_DIR = OPERATORS_DIR / "defense"
GADGETS_DIR = ASSETS_DIR / "gadgets"
ATTACK_GADGETS_DIR = GADGETS_DIR / "attack"
DEFENSE_GADGETS_DIR = GADGETS_DIR / "defense"


def ensure_asset_directories() -> None:
    for path in (
        ASSETS_DIR,
        MAPS_DIR,
        OPERATORS_DIR,
        ATTACK_OPERATORS_DIR,
        DEFENSE_OPERATORS_DIR,
        GADGETS_DIR,
        ATTACK_GADGETS_DIR,
        DEFENSE_GADGETS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
