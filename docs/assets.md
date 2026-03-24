# 资源结构说明

本文档用于固定项目内的素材目录结构，避免后续导入、脚本整理和程序接入时出现口径不一致。

## 总目录

```text
assets/
├─ maps/
└─ operators/
   ├─ index.json
   ├─ download_ops.py
   ├─ attack/
   │  ├─ icons/
   │  ├─ portraits/
   │  └─ abilities/
   └─ defense/
      ├─ icons/
      ├─ portraits/
      └─ abilities/
```

## 地图资源结构

地图资源按“单地图目录 + 单地图元数据”的方式组织：

```text
assets/maps/
├─ index.json
├─ download_all.sh
├─ download_maps.sh
├─ download_blueprints.js
├─ create_json.sh
└─ <map_key>/
   ├─ map.json
   ├─ 1f.png / 2f.png / 3f.png
   ├─ b1.png
   └─ roof.png
```

其中：

- `<map_key>` 当前使用英文小写短横线命名
- 每张地图必须单独存在一个 `map.json`
- `assets/maps/index.json` 作为地图资源总索引

## 地图元数据约定

每张地图目录内的 `map.json` 用于保存该图的扩展信息，后续可用于：

- 地图基础展示
- 楼层切换
- 墙体、门窗、舱口等结构标注
- 自定义战术层和交互层

当前至少应保留“图片路径 + 楼层信息 + 可扩展层数据”的结构。

楼层图片推荐命名：

- `1f.png`
- `2f.png`
- `3f.png`
- `b1.png`
- `roof.png`

## 干员资源结构

进攻方与防守方使用同一套目录约定：

```text
assets/operators/<side>/
├─ icons/
│  └─ <operator_key>.png
├─ portraits/
│  └─ <operator_key>.png
└─ abilities/
   └─ <operator_key>/
      ├─ icon.png
      ├─ name.txt
      └─ description.txt
```

其中：

- `<side>` 取值为 `attack` 或 `defense`
- `<operator_key>` 使用英文小写

## 命名与格式约定

- 地图目录使用 `<map_key>`
- 地图资源总索引使用 `assets/maps/index.json`
- 地图元数据文件统一命名为 `map.json`
- 楼层图按 `1f` / `2f` / `3f` / `b1` / `roof` 规则命名
- 图标文件使用 `png`
- 立绘文件使用 `png`
- 干员主图标命名为 `<operator_key>.png`
- 干员立绘命名为 `<operator_key>.png`
- 技能目录名与干员 `operator_key` 保持一致
- `name.txt` 与 `description.txt` 使用 `UTF-8 + LF`
- 所有 `json`、`txt` 统一使用 `UTF-8 + LF`

## 索引文件

`assets/maps/index.json` 作为地图资源总索引，建议每个条目至少包含：

- `key`
- `name`
- `path`

`assets/operators/index.json` 作为干员资源总索引，建议每个条目至少包含：

- `key`
- `side`
- `name`
- `icon_path`
- `portrait_path`
- `ability_icon_path`
- `ability_name`
- `ability_description`

## 当前用途

当前版本已经直接使用：

- `maps/` 作为地图资源来源
- `icons/` 作为干员图标资源来源

后续计划接入：

- `map.json` 用于地图元数据、结构层与自定义编辑能力
- `portraits/` 用于更完整的干员信息展示
- `abilities/` 用于技能说明与资料展示
- `index.json` 用于资源总览、筛选与快速读取
