#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R6 赛事数据抓取脚本 v3 - 修复 Match 块嵌套解析
"""

import gzip
import json
import logging
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

# ========== 配置 ==========
ROOT_DIR = Path(__file__).resolve().parents[1]
MAPS_DIR = ROOT_DIR / "maps"
LOG_DIR = ROOT_DIR / "logs"
STATE_DIR = ROOT_DIR / "state"
PROCESSED_LOG = STATE_DIR / "processed_events.log"

LIQUIPEDIA_BASE = "https://liquipedia.net/rainbowsix/api.php"
USER_AGENT = "R6EsportsBot/1.0 LittleHerta Research Bot"

MAP_NAME_MAPPING = {
    "bank": "bank",
    "border": "border",
    "brazil": "brazil",
    "chalet": "chalet",
    "clubhouse": "clubhouse",
    "coastline": "coastline",
    "consulate": "consulate",
    "emerald plains": "emerald-plains",
    "fortress": "fortress",
    "kafe dostoyevsky": "kafe-dostoyevsky",
    "kafe": "kafe-dostoyevsky",
    "lair": "lair",
    "nighthaven labs": "nighthaven-labs",
    "oregon": "oregon",
    "outback": "outback",
    "skyscraper": "skyscraper",
    "theme park": "theme-park",
    "themepark": "theme-park",
    "villa": "villa",
}

STAGE_KEYWORDS = ["Grand Final", "Final", "Semifinal", "Lower Bracket", "Upper Bracket"]


def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("r6-scraper")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(LOG_DIR / "r6-scraper.log", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(fh)
        logger.addHandler(sh)
    return logger


logger = setup_logging()


def fetch(url: str, params: dict) -> Optional[dict]:
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{query}", headers={
        "User-Agent": USER_AGENT, "Accept-Encoding": "gzip",
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return json.loads(raw)
        except Exception as e:
            logger.warning(f"请求失败 (尝试 {attempt + 1}/3): {e}")
            time.sleep(2 ** attempt)
    return None


def load_processed() -> set:
    processed = set()
    if PROCESSED_LOG.exists():
        with open(PROCESSED_LOG, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    p = line.split(",")
                    if len(p) >= 2:
                        processed.add((p[0].strip(), p[1].strip()))
    return processed


def append_processed(event_id: str, map_name: str):
    with open(PROCESSED_LOG, "a", encoding="utf-8") as f:
        f.write(f"{event_id},{map_name}\n")


def normalize_map(raw: str) -> Optional[str]:
    raw = raw.lower().strip()
    for k, v in MAP_NAME_MAPPING.items():
        if k in raw or raw in k:
            return v
    return None


def ensure_dirs():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    for m in set(MAP_NAME_MAPPING.values()):
        (MAPS_DIR / m).mkdir(parents=True, exist_ok=True)


def find_match_blocks(wikitext: str) -> list[tuple[str, str, int, int]]:
    """
    找到所有 Match 块: (match_ref, match_text, start, end)
    使用 |{Ref}}={{Match 作为起始标记，|{NextRef}} 或文件末尾作为结束标记
    """
    blocks = []
    # 匹配: |R1M1={{Match 或类似的引用格式
    pattern = r'\|([A-Z0-9a-z_]+)=\{\{Match\n'
    for m in re.finditer(pattern, wikitext):
        ref = m.group(1)
        start = m.start()
        # 找下一个块的开始位置
        remaining = wikitext[m.end():]
        # 下一个块: |{REF}={{Match
        next_match = re.search(r'\n\|[A-Z0-9a-z_]+=\{\{Match', remaining)
        if next_match:
            end = m.end() + next_match.start()
        else:
            end = len(wikitext)
        block_text = wikitext[start:end]
        blocks.append((ref, block_text, start, end))
    return blocks


def parse_match_block(ref: str, text: str, tournament: str) -> list[dict]:
    """解析单个 Match 块"""
    matches_data = []

    # 提取队伍
    t1_m = re.search(r'opponent1=\{\{TeamOpponent\|([^}|]+)', text)
    t2_m = re.search(r'opponent2=\{\{TeamOpponent\|([^}|]+)', text)
    team_a = t1_m.group(1).strip() if t1_m else "Unknown"
    team_b = t2_m.group(1).strip() if t2_m else "Unknown"

    # 提取日期
    date_m = re.search(r'\|date=([\d-]+ [\d:]+)', text)
    match_date = date_m.group(1) if date_m else ""

    # 提取阶段
    stage = "Unknown"
    for kw in STAGE_KEYWORDS:
        if kw.lower() in text.lower():
            stage = kw
            break

    # match_id
    match_id = f"{ref}_{team_a}_vs_{team_b}_{match_date.replace(' ', '_').replace(':', '')}"

    # 提取 MapVeto (ban/pick 信息)
    veto_m = re.search(r'\{\{MapVeto\n(.*?)\n\}\}', text, re.DOTALL)
    veto = {}
    if veto_m:
        veto_text = veto_m.group(1)
        for key in re.findall(r'(t\dmap\d|decider|firstpick)=', veto_text):
            v = re.search(rf'{re.escape(key)}=([^\||\n]+)', veto_text)
            if v:
                veto[key] = v.group(1).strip()

    # 提取各地图详情
    # 格式: |map1={{Map|map=MapName|finished=true\n...}}
    map_pattern = r'\|map(\d+)=\{\{Map\|map=([^\||\n]+)\|finished=([^\||\n]+)(.*?)\n\s*\}\}'
    for map_m in re.finditer(map_pattern, text, re.DOTALL):
        map_num = int(map_m.group(1))
        raw_map = map_m.group(2).strip()
        finished = map_m.group(3).strip()
        map_block = map_m.group(4)

        map_name = normalize_map(raw_map)
        if not map_name:
            continue

        # Ban 信息
        atk_bans, def_bans = [], []
        for n in range(1, 10):
            b = re.search(rf't1ban{n}=([^\||\n]+)', map_block)
            if b and b.group(1).strip():
                atk_bans.append(b.group(1).strip())
            b2 = re.search(rf't2ban{n}=([^\||\n]+)', map_block)
            if b2 and b2.group(1).strip():
                def_bans.append(b2.group(1).strip())

        # 比分
        def get_int(pat):
            m = re.search(pat, map_block)
            return int(m.group(1)) if m and m.group(1) else 0

        t1_atk = get_int(r't1atk=(\d+)')
        t1_def = get_int(r't1def=(\d+)')
        t2_atk = get_int(r't2atk=(\d+)')
        t2_def = get_int(r't2def=(\d+)')

        # 首发进攻方
        fs_m = re.search(r't1firstside=([^\||\n]+)', map_block)
        t1_first = fs_m.group(1).strip() if fs_m else "atk"

        # 计算攻守方和得分
        if t1_first == "atk":
            atk_team, def_team = team_a, team_b
            atk_score = t1_atk
            def_score = t2_def
            atk_deaths = t1_atk + t2_def  # attack rounds = def deaths
            def_deaths = t2_atk + t1_def
        else:
            atk_team, def_team = team_b, team_a
            atk_score = t2_atk
            def_score = t1_def
            atk_deaths = t2_atk + t1_def
            def_deaths = t1_atk + t2_def

        total_deaths = atk_deaths + def_deaths

        # 从 veto 找该地图是谁 pick 的
        pick = ""
        for k, v in veto.items():
            if k.startswith("t1map") and raw_map.lower().replace(" ", "") in v.lower().replace(" ", ""):
                pick = "team_a"
            elif k.startswith("t2map") and raw_map.lower().replace(" ", "") in v.lower().replace(" ", ""):
                pick = "team_b"

        is_flawless = (finished == "true" and total_deaths == 0)

        matches_data.append({
            "match_ref": ref,
            "match_id": match_id,
            "tournament": tournament,
            "stage": stage,
            "date": match_date,
            "map": map_name,
            "map_raw": raw_map,
            "finished": finished,
            "atk_team": atk_team,
            "def_team": def_team,
            "atk_score": atk_score,
            "def_score": def_score,
            "atk_deaths": atk_deaths,
            "def_deaths": def_deaths,
            "total_deaths": total_deaths,
            "atk_bans": atk_bans,
            "def_bans": def_bans,
            "atk_operators": [],
            "def_operators": [],
            "first_attack": t1_first,
            "pick": pick,
            "is_flawless": is_flawless,
            "raw_map_block": map_block[:500],  # 保留原始用于调试
        })

    return matches_data


def scrape_page(tournament: str) -> list[dict]:
    logger.info(f">>> 抓取: {tournament}")

    data = fetch(LIQUIPEDIA_BASE, {
        "action": "query", "titles": tournament,
        "prop": "revisions", "rvprop": "content",
        "rvslots": "main", "format": "json"
    })
    if not data:
        return []

    pages = data.get("query", {}).get("pages", {})
    for page_id, page in pages.items():
        if page_id == "-1":
            logger.error(f"页面不存在: {tournament}")
            return []
        revs = page.get("revisions", [])
        if not revs:
            continue
        wikitext = revs[0].get("slots", {}).get("main", {}).get("*", "")
        if not wikitext:
            return []

        blocks = find_match_blocks(wikitext)
        logger.info(f"  找到 {len(blocks)} 个 Match 块")

        all_maps = []
        for ref, block_text, _, _ in blocks:
            parsed = parse_match_block(ref, block_text, tournament)
            all_maps.extend(parsed)

        logger.info(f"  共提取 {len(all_maps)} 条地图级记录")
        return all_maps

    return []


def save_raw(map_name: str, matches: list):
    path = MAPS_DIR / map_name / "raw_matches.json"
    existing = []
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing = []

    seen = {m["match_id"] for m in existing}
    new = [m for m in matches if m["match_id"] not in seen]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing + new, f, ensure_ascii=False, indent=2)
    logger.info(f"[{map_name}] raw_matches.json: +{len(new)}")


def save_flawless(map_name: str, rounds: list):
    path = MAPS_DIR / map_name / "flawless_report.json"
    existing = []
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing = []
    existing.extend(rounds)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    logger.info(f"[{map_name}] flawless: +{len(rounds)}")


def update_summary(map_name: str):
    raw = MAPS_DIR / map_name / "raw_matches.json"
    flaw = MAPS_DIR / map_name / "flawless_report.json"
    summary = {
        "map": map_name, "last_updated": datetime.now().isoformat(),
        "total_matches": 0, "total_rounds": 0, "flawless_count": 0, "teams": {}
    }
    if raw.exists():
        try:
            with open(raw, "r", encoding="utf-8") as f:
                data = json.load(f)
            summary["total_matches"] = len(data)
            for m in data:
                for t in [m.get("atk_team", ""), m.get("def_team", "")]:
                    if t:
                        summary["teams"][t] = summary["teams"].get(t, 0) + 1
        except (json.JSONDecodeError, IOError):
            pass
    if flaw.exists():
        try:
            with open(flaw, "r", encoding="utf-8") as f:
                summary["flawless_count"] = len(json.load(f))
        except (json.JSONDecodeError, IOError):
            pass
    with open(MAPS_DIR / map_name / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def run(years=None, tournaments=None, maps=None, force=False):
    ensure_dirs()
    if years is None:
        years = [2025, 2026]
    if tournaments is None:
        tournaments = ["Six Invitational/2025", "Six Invitational/2026", "BLAST_Major/2025", "BLAST_Major/2026/May"]

    processed = load_processed() if not force else set()
    stats = {"processed": 0, "skipped": 0, "errors": 0}

    logger.info("=" * 60)
    logger.info("R6 赛事数据抓取任务启动")
    logger.info(f"目标年份: {years}")
    logger.info(f"强制模式: {force}")
    logger.info("=" * 60)

    for tournament in tournaments:
        year = 2026 if "2026" in tournament else 2025
        if year not in years:
            continue

        try:
            all_data = scrape_page(tournament)
            if not all_data:
                logger.warning(f"未获取数据: {tournament}")
                continue

            by_map = {}
            for m in all_data:
                mn = m["map"]
                if maps and mn not in maps:
                    continue
                key = (m["match_id"], mn)
                if not force and key in processed:
                    stats["skipped"] += 1
                    continue
                by_map.setdefault(mn, []).append(m)
                append_processed(m["match_id"], mn)
                processed.add(key)
                stats["processed"] += 1

            for map_name, map_matches in by_map.items():
                save_raw(map_name, map_matches)
                flawless = [x for x in map_matches if x.get("is_flawless")]
                if flawless:
                    save_flawless(map_name, flawless)
                update_summary(map_name)

        except Exception as e:
            logger.error(f"处理 {tournament} 出错: {e}")
            stats["errors"] += 1

        time.sleep(2)

    logger.info(f"\n完成: 处理={stats['processed']} | 跳过={stats['skipped']} | 错误={stats['errors']}")
    logger.info(f"数据目录: {ROOT_DIR}")
    return stats


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--years", type=int, nargs="+", default=[2025, 2026])
    p.add_argument("--tournaments", type=str, nargs="+")
    p.add_argument("--maps", type=str, nargs="+")
    p.add_argument("--force", action="store_true")
    run(**vars(p.parse_args()))
