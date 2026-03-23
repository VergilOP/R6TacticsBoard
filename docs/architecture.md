# 架构设计

## 目标

当前架构优先服务三个核心能力：

- 地图可编辑
- 状态可关键帧化
- 场景可回放

因此，不追求一开始就把系统拆得非常重，而是保持模块边界清晰，支持后续扩展。

## 模块划分

### `domain`

纯业务对象，不依赖 Qt 组件。

- `MapInfo`: 地图资源信息
- `OperatorDefinition`: 干员固有定义，例如名称、阵营、图标 key
- `OperatorFrameState`: 某个时间点的局部状态，例如位置、朝向、显示模式
- `OperatorState`: 由定义 + 局部状态解析出的渲染态
- `Keyframe`: 某一时刻的显式局部状态集合
- `Timeline`: 关键帧集合
- `TacticProject`: 战术工程根对象

### `application`

负责业务流程与状态变换。

- `PlaybackController`: 控制播放、暂停、跳转
- `InterpolationService`: 计算关键帧之间的插值状态
- `EditorSession`: 当前编辑上下文

### `infrastructure`

负责与磁盘或外部资源交互。

- `ProjectStore`: 项目保存/读取
- `AssetRegistry`: 地图和干员资源索引

### `presentation`

负责 Qt 视图与交互。

- `MainWindow`: Fluent 主窗口
- `EditorPage`: 地图编辑页
- `MapScene`: 图元场景
- `MapView`: 缩放与平移容器
- `OperatorItem`: 干员场景图元
- `TimelineWidget`: 时间轴组件

## 关键数据流

1. 用户修改干员名称、阵营、图标等固有属性
2. 编辑页更新 `OperatorDefinition`
3. 用户在地图上放置干员、改朝向或改显示模式
4. 编辑页仅把局部变化写入当前关键帧的 `OperatorFrameState`
5. 需要显示或播放时，用 `OperatorDefinition + OperatorFrameState` 解析出 `OperatorState`
6. `OperatorState` 回写到场景图元，形成静态显示或插值动画

## 数据结构边界

当前版本明确区分三类数据：

### 1. 干员固有属性

全局生效，不应只改某一个时间轴单元格。

- `custom_name`
- `side`
- `operator_key`

这些数据保存在 `OperatorDefinition` 中。

### 2. 时间轴局部属性

只属于某个关键帧单元格。

- `position`
- `rotation`
- `display_mode`

这些数据保存在 `OperatorFrameState` 中。

### 3. 渲染态

场景显示、播放插值、预览路径使用的是解析后的完整状态：

- `OperatorState`

它不是直接编辑源，而是由前两层合成得到。

## 时间轴模型选择

首版采用“按干员行 + 关键帧列”的表格时间轴：

- 每个关键帧列只记录显式修改过的 `OperatorFrameState`
- 空单元格沿用左侧最近一次有效状态
- 回放时在相邻关键帧间做线性插值

优点：

- 模型简单
- 序列化简单
- UI 易实现
- 非常适合当前“战术阶段”表达

后续若需要更强编辑能力，再升级为：

- 多轨时间轴
- 单干员独立关键帧
- 贝塞尔/缓动曲线
- 事件轨道

## 推荐实现顺序

### 第一批

- `domain/models.py`
- `presentation/main_window.py`
- `presentation/widgets/map_view.py`
- `presentation/widgets/map_scene.py`

### 第二批

- `presentation/widgets/operator_item.py`
- `presentation/pages/editor_page.py`
- `application/playback.py`

### 第三批

- `presentation/widgets/timeline_widget.py`
- `infrastructure/project_store.py`

## 风险点

### 1. 时间轴先做太重

如果一开始直接做多轨和复杂曲线，UI 和数据模型会同时失控。

结论：首版坚持全局关键帧。

### 2. 场景状态和数据状态混在一起

如果直接把状态塞进 `QGraphicsItem`，后面序列化和回放会变得难维护。

结论：场景 item 只负责显示，业务状态以 `domain` 模型为准。

### 3. 资源标识不稳定

如果干员或地图资源靠显示名称识别，后期改名会影响存档兼容。

结论：资源统一使用稳定的 `key/id`。
