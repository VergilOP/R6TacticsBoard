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
- `OperatorState`: 某一时刻单个干员状态
- `Keyframe`: 某一时刻全场景状态
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

1. 用户在 `MapScene` 中拖拽干员
2. `OperatorItem` 更新场景表现
3. 编辑页将变更同步到 `EditorSession`
4. 保存关键帧时，将当前状态固化为 `Keyframe`
5. 播放时，`PlaybackController` 根据时间计算插值结果
6. 插值结果回写到场景图元，形成动画效果

## 时间轴模型选择

首版采用“全局关键帧”：

- 每个关键帧记录全部干员状态
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
