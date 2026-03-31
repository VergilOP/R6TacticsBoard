# 资源结构说明

本文档用于固定项目内的素材目录结构，避免后续导入、脚本整理和程序接入时出现口径不一致。

## 总目录

```text
src/assets/
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
src/assets/maps/
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
- `src/assets/maps/index.json` 作为地图资源总索引

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
src/assets/operators/<side>/
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
- 地图资源总索引使用 `src/assets/maps/index.json`
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

`src/assets/maps/index.json` 作为地图资源总索引，建议每个条目至少包含：

- `key`
- `name`
- `path`

`src/assets/operators/index.json` 作为干员资源总索引，建议每个条目至少包含：

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

- `src/assets/maps/` 作为地图资源来源
- `src/assets/operators/*/icons/` 作为干员图标资源来源

后续计划接入：

- `map.json` 用于地图元数据、结构层与自定义编辑能力
- `portraits/` 用于更完整的干员信息展示
- `abilities/` 用于技能说明与资料展示
- `index.json` 用于资源总览、筛选与快速读取

## 地图互动点结构

当前 `map.json` 里的互动点统一写入 `layers.interactions`，并按类型同步拆分到 `layers.stairs` 与 `layers.hatches`。

推荐结构如下：

```json
{
  "id": "interaction-1",
  "kind": "stairs",
  "position": {
    "x": 1024,
    "y": 768
  },
  "floor_key": "1f",
  "linked_floor_keys": ["2f"],
  "is_bidirectional": true,
  "label": "Main Stairs",
  "note": ""
}
```

字段说明：
- `id`：互动点唯一标识
- `kind`：当前支持 `stairs`、`hatch`
- `position`：在地图画布上的坐标
- `floor_key`：源楼层
- `linked_floor_keys`：目标楼层列表
- `is_bidirectional`：是否双向联通
- `label`：可选短名称
- `note`：可选备注

显示规则：
- `stairs` 适合设置为双向联通，会在源楼层和联通楼层显示同一个互动点
- `hatch` 默认单向联通，只在源楼层显示

当前地图 Debug 页面已支持对上述互动点进行放置、移动、删除和保存。

## 2.5D 总览预留字段

为后续的 `2.5D 全楼层总览` 提供地图级调优能力，`map.json` 可以预留一个可选的 `overview_2_5d` 配置块。

推荐结构：

```json
"overview_2_5d": {
  "enabled": true,
  "default_yaw": 35.0,
  "default_zoom": 1.0,
  "pitch_factor": 0.65,
  "floor_height": 180,
  "draw_order": ["b1", "1f", "2f", "roof"],
  "floor_overrides": {
    "roof": {
      "height": 560
    }
  }
}
```

字段说明：

- `enabled`：是否允许该地图进入 2.5D 总览
- `default_yaw`：默认观察角度
- `default_zoom`：默认缩放
- `pitch_factor`：俯视压缩系数
- `floor_height`：默认楼层高度差
- `draw_order`：楼层绘制顺序
- `floor_overrides`：针对个别楼层的高度微调

楼层节点也可预留：

```json
{
  "key": "2f",
  "name": "Second Floor",
  "image": "assets/maps/bank/2f.png",
  "overview": {
    "height": 360
  }
}
```

说明：

- 当前资源层已经会读取 `enabled`、`default_yaw`、`default_zoom`、`pitch_factor`、`floor_height`、`draw_order` 和 `floor_overrides.<floor_key>.height`
- 上述字段仍然是可选项，不要求现有地图立即补齐
- 缺省时会按楼层顺序自动推导高度，默认朝向以当前实现为准
- 后续若加入互动点专用显示点，也应优先写在 `map.json` 内，由资源层统一读取
