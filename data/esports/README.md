# Esports Data

这里存放按地图整理的 R6 电竞比赛数据，不属于运行时素材资源。

## 目录结构

```text
data/esports/
├─ maps/
│  └─ <map_key>/
│     ├─ raw_matches.json
│     └─ summary.json
├─ scripts/
│  └─ scrape_liquipedia.py
├─ logs/
└─ state/
```

## 约定

- `maps/<map_key>/` 的目录名尽量与 `src/assets/maps/<map_key>/` 保持一致。
- `raw_matches.json` 保存原始比赛级记录。
- `summary.json` 保存按地图汇总后的统计结果。
- `logs/` 和 `state/processed_events.log` 属于抓取运行产物，默认不纳入版本控制。

## 当前 map key 映射

已经统一到项目内部地图 key，例如：

- `Bank` -> `bank`
- `EmeraldPlains` -> `emerald-plains`
- `Kafe` -> `kafe-dostoyevsky`
- `Nighthaven` -> `nighthaven-labs`
- `ThemePark` -> `theme-park`
