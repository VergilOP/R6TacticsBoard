# Editor Workflow

这份文档只讲战术编辑页，目标是说明：

1. 编辑器状态从哪里来
2. 哪些数据是全局的，哪些是关键帧局部的
3. 修改一个功能时应该先看哪一层

## 核心入口

- [editor_page.py](../../src/r6_tactics_board/presentation/pages/editor/editor_page.py)

这是编辑器总控。大部分“为什么点一下会连锁刷新多个地方”的答案都在这里。

## 三层状态

### 1. 全局定义

来源：
- [models.py](../../src/r6_tactics_board/domain/models.py) 的 `OperatorDefinition`

内容：
- 干员名称
- 阵营
- 干员 key
- 当前选择的通用道具 key

特点：
- 不属于某一帧
- 改一次，整条轨道都受影响

### 2. 关键帧局部状态

来源：
- [models.py](../../src/r6_tactics_board/domain/models.py) 的 `OperatorFrameState`

内容：
- 位置
- 朝向
- 楼层
- 是否显示图标 / 名字
- 路径模式与手动互动点
- 当前帧显式的道具位置 / 技能位置
- 当前帧显式的已使用数量覆盖

特点：
- 允许留空，靠前一帧继承
- 这是时间轴的核心

### 3. 解析态

来源：
- [editor_page.py](../../src/r6_tactics_board/presentation/pages/editor/editor_page.py) 的 `_resolved_frame_state()` / `_resolved_state()`
- [models.py](../../src/r6_tactics_board/domain/models.py) 的 `resolve_operator_state()`

内容：
- 当前列下真正应该显示和播放的状态

特点：
- 用于画布显示和播放
- 不能直接等同于“当前帧显式保存的数据”

## 一次性和保留型道具的规则

这部分是当前最容易混乱的地方。

### 通用道具 / 技能道具分成两件事

1. `已使用数量`
2. `地图上是否继续显示图标`

### 一次性

- 后续帧继承 `已使用数量`
- 后续帧不继承地图图标
- 当前帧若显式放置，当前帧显示

### 保留型

- 后续帧继承 `已使用数量`
- 后续帧也继承地图图标

### 关键点

- “数量继承”和“图标显隐”必须分开处理
- 不能直接把解析后的继承态回写成当前帧显式状态

这也是为什么当前代码里会区分：
- `_resolved_state(...)`
- `_explicit_current_frame(...)`
- `_current_transition_frame(...)`

## 关键刷新链

编辑器里大部分动作最终都会落到这几步：

1. 修改当前列或全局定义
2. `_apply_timeline_column(...)`
3. `_refresh_property_panel()`
4. `_refresh_timeline()`
5. `_sync_scene_placement_target()` / `_sync_scene_preview_paths()` / `_sync_scene_interaction_overlays()`

如果一个改动引发了明显卡顿，优先检查：
- 是否重复读取资源 JSON
- 是否不必要地全量重建 2D / 2.5D 视图
- 是否把局部改动走成了全量刷新

## 画布相关的职责

### 2D 画布

- [map_scene.py](../../src/r6_tactics_board/presentation/widgets/canvas/map_scene.py)

负责：
- 干员同步
- 道具 / 技能道具放置与拖动
- 战术面和互动点 overlay
- 选择反馈

不负责：
- 时间轴继承计算
- 资源索引查找

### 2.5D 总览

- [overview_scene.py](../../src/r6_tactics_board/presentation/widgets/canvas/overview_scene.py)
- [overview_view.py](../../src/r6_tactics_board/presentation/widgets/canvas/overview_view.py)

负责：
- 用解析后的状态进行展示
- 播放过程中的跨层轨迹表现

## 修改建议

### 想改“时间轴继承”

先看：
- `_resolved_frame_state()`
- `_resolved_state()`
- `ProjectStore` 的显式字段保存规则

### 想改“当前帧放置行为”

先看：
- `_on_gadget_placed()`
- `_on_ability_placed()`
- `_clear_current_frame_gadget_placements()`
- `_clear_current_frame_ability_placements()`

### 想改“右侧属性栏”

先看：
- [editor_panels.py](../../src/r6_tactics_board/presentation/widgets/editor/editor_panels.py)
- `editor_page.py` 中 `_refresh_property_panel()`

## 当前最大的可读性风险

- [editor_page.py](../../src/r6_tactics_board/presentation/pages/editor/editor_page.py)

这个文件目前承担了：
- 页面初始化
- 时间轴状态
- 画布同步
- 右侧面板刷新
- 播放控制
- 道具/技能逻辑
- 战术面逻辑

后续如果继续增加功能，优先把它按“功能线”继续拆出去，而不是继续横向堆方法。
