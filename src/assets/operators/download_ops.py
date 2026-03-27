#!/usr/bin/env python3
"""Download R6 Siege operator assets from Ubisoft Chinese site."""

import os
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

WORKDIR = Path("/home/node/clawd/little-herta/assets/operators")
BASE_URL = "https://cdn.hommk.com/pcgame/ubi2015/img/gamezone/r6/new/operators"
API_URL = "https://zh-cn.ubisoft.com/r6s/operators/{key}.txt"

# All operators from both lists (from task)
OPERATORS = [
    # Attack
    ("ace", "attack"), ("amaru", "attack"), ("ash", "attack"), ("blackbeard", "attack"),
    ("blitz", "attack"), ("brava", "attack"), ("buck", "attack"), ("capitao", "attack"),
    ("deimos", "attack"), ("dokkaebi", "attack"), ("finka", "attack"), ("flores", "attack"),
    ("fuze", "attack"), ("glaz", "attack"), ("gridlock", "attack"), ("grim", "attack"),
    ("hibana", "attack"), ("iana", "attack"), ("iq", "attack"), ("jackal", "attack"),
    ("kali", "attack"), ("lion", "attack"), ("maverick", "attack"), ("montagne", "attack"),
    ("nomad", "attack"), ("nokk", "attack"), ("osa", "attack"), ("ram", "attack"),
    ("sens", "attack"), ("sledge", "attack"), ("solidsnake", "attack"), ("striker", "attack"),
    ("thatcher", "attack"), ("thermite", "attack"), ("twitch", "attack"), ("ying", "attack"),
    ("zero", "attack"), ("zofia", "attack"),
    # Defense
    ("alibi", "defense"), ("aruni", "defense"), ("azami", "defense"), ("bandit", "defense"),
    ("castle", "defense"), ("caveira", "defense"), ("clash", "defense"), ("denari", "defense"),
    ("doc", "defense"), ("echo", "defense"), ("ela", "defense"), ("fenrir", "defense"),
    ("frost", "defense"), ("goyo", "defense"), ("jager", "defense"), ("kaid", "defense"),
    ("kapkan", "defense"), ("lesion", "defense"), ("maestro", "defense"), ("melusi", "defense"),
    ("mira", "defense"), ("mozzie", "defense"), ("mute", "defense"), ("oryx", "defense"),
    ("pulse", "defense"), ("rauora", "defense"), ("rook", "defense"), ("sentry", "defense"),
    ("skopos", "defense"), ("smoke", "defense"), ("solis", "defense"), ("tachanka", "defense"),
    ("thorn", "defense"), ("thunderbird", "defense"), ("tubarao", "defense"), ("valkyrie", "defense"),
    ("vigil", "defense"), ("wamai", "defense"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://zh-cn.ubisoft.com/",
}

log_errors = []
results = []


def fetch_json(key):
    url = API_URL.format(key=key)
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log_errors.append(f"API fetch error for {key}: {e}")
        return None


def download_file(url, path, desc=""):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return True
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
            return True
    except Exception as e:
        log_errors.append(f"Download error [{desc}] for {url}: {e}")
        return False


def clean_html(text):
    """Remove HTML tags from text."""
    import re
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    return text.strip()


def process_operator(key, side):
    print(f"  Processing {key} ({side})...")
    
    # Create directories
    icon_dir = WORKDIR / side / "icons"
    portrait_dir = WORKDIR / side / "portraits"
    ability_dir = WORKDIR / side / "abilities" / key
    for d in [icon_dir, portrait_dir, ability_dir]:
        os.makedirs(d, exist_ok=True)
    
    # Fetch JSON
    data = fetch_json(key)
    if not data:
        return None
    
    # Override side from API if available and different
    api_side = data.get("side", "")
    if api_side == "atk":
        side = "attack"
    elif api_side == "def":
        side = "defense"
    
    # Download icon
    icon_name = data.get("operator_icon", "")
    icon_path = icon_dir / f"{key}.png"
    if icon_name:
        icon_url = f"{BASE_URL}/{icon_name}"
        download_file(icon_url, str(icon_path), f"icon/{key}")
    
    # Download portrait
    pic_name = data.get("operator_pic", "")
    portrait_path = portrait_dir / f"{key}.png"
    if pic_name:
        portrait_url = f"{BASE_URL}/{pic_name}"
        download_file(portrait_url, str(portrait_path), f"portrait/{key}")
    
    # Download ability icon and save ability info
    ability_name = ""
    ability_desc = clean_html(data.get("unique_abilities", ""))
    ability_pic = ""
    unique_gadgets = data.get("unique_gadget", [])
    if unique_gadgets:
        ability_name = unique_gadgets[0].get("name", "")
        ability_pic = unique_gadgets[0].get("pic", "")
    
    if ability_pic:
        ability_icon_url = f"{BASE_URL}/{ability_pic}"
        download_file(ability_icon_url, str(ability_dir / "icon.png"), f"ability_icon/{key}")
    
    # Save ability name and description
    with open(ability_dir / "name.txt", "w", encoding="utf-8") as f:
        f.write(ability_name)
    with open(ability_dir / "description.txt", "w", encoding="utf-8") as f:
        f.write(ability_desc)
    
    return {
        "key": key,
        "side": side,
        "name": data.get("operator_name", key.capitalize()),
        "icon_path": f"assets/operators/{side}/icons/{key}.png",
        "portrait_path": f"assets/operators/{side}/portraits/{key}.png",
        "ability_icon_path": f"assets/operators/{side}/abilities/{key}/icon.png",
        "ability_name": ability_name,
        "ability_description": ability_desc,
    }


def main():
    os.makedirs(WORKDIR, exist_ok=True)
    os.makedirs(WORKDIR / "attack" / "icons", exist_ok=True)
    os.makedirs(WORKDIR / "attack" / "portraits", exist_ok=True)
    os.makedirs(WORKDIR / "attack" / "abilities", exist_ok=True)
    os.makedirs(WORKDIR / "defense" / "icons", exist_ok=True)
    os.makedirs(WORKDIR / "defense" / "portraits", exist_ok=True)
    os.makedirs(WORKDIR / "defense" / "abilities", exist_ok=True)
    
    all_results = []
    total = len(OPERATORS)
    
    for i, (key, side) in enumerate(OPERATORS):
        print(f"[{i+1}/{total}] Processing {key} ({side})...")
        result = process_operator(key, side)
        if result:
            all_results.append(result)
        time.sleep(0.3)  # Be polite
    
    # Write index.json
    index_path = WORKDIR / "index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\nDone! Processed {len(all_results)} operators.")
    print(f"Errors: {len(log_errors)}")
    for err in log_errors:
        print(f"  ERROR: {err}")
    
    # Write error log
    if log_errors:
        with open(WORKDIR / "errors.log", "w", encoding="utf-8") as f:
            f.write("\n".join(log_errors))
    
    print(f"index.json written to {index_path}")


if __name__ == "__main__":
    main()
