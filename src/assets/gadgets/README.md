# R6 通用道具图标库

> 数据来源：官方 Ubisoft CDN `staticctf.ubisoft.com`
> 采集日期：2026-04-14
> 项目内分类：按阵营拆分为 `attack / defense`
> 文本与 JSON 规范：`UTF-8 + LF`

## 目录结构

```text
gadgets/
  attack/
    breach-charge.png
    claymore.png
    emp-impact-grenade.png
    frag-grenade.png
    secondary-breacher.png
    smoke-grenade.png
    stun-grenade.png
  defense/
    barbed-wire.png
    bulletproof-camera.png
    deployable-shield.png
    impact-grenade.png
    nitro-cell.png
    observation-blocker.png
    proximity-alarm.png
  index.json
  download_log.md
  README.md
```

## 说明

- 项目内不再使用 `equipment / throwables` 作为正式分类。
- 统一按阵营拆分为 `attack / defense`，方便后续编辑器直接按进攻方与防守方加载。
- 道具上限数量统一记录在 `index.json` 的 `max_count` 字段中。
- `index.json` 同时承担路径索引与数量上限索引，不再额外维护第二份总表。

## 当前收录

### 进攻方

- `breach-charge`
- `claymore`
- `emp-impact-grenade`
- `frag-grenade`
- `secondary-breacher`
- `smoke-grenade`
- `stun-grenade`

### 防守方

- `barbed-wire`
- `bulletproof-camera`
- `deployable-shield`
- `impact-grenade`
- `nitro-cell`
- `observation-blocker`
- `proximity-alarm`

## 未包含项

- 加固墙、脚洞、对枪洞、过人洞、翻越洞等地图改造类内容不在本目录中。
- 这类内容应继续作为地图 / 战术面状态处理，而不是通用副道具图标。
