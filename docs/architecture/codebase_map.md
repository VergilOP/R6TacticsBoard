# Codebase Map

这份文档回答两个问题：
1. 某个功能主要改哪里。
2. 当前哪些复杂文件已经拆过，哪些还值得继续拆。

## 顶层入口

- [main.py](../../src/r6_tactics_board/main.py)
  程序主入口。
- [app.py](../../src/r6_tactics_board/app.py)
  Qt 应用初始化、主题和运行时配置。
- [main_window.py](../../src/r6_tactics_board/presentation/shell/main_window.py)
  导航、主窗口和页面挂载。

## 分层结构

- `domain/`
  稳定模型、枚举和解析函数。
- `application/`
  编辑器服务、播放控制、时间轴控制、路径规划。
- `infrastructure/`
  资源索引、工程读写、日志和外部数据读写。
- `presentation/`
  Qt 页面、控件、画布、图元和主题样式。

## 功能线与主要文件

### 战术编辑页

- [editor_page.py](../../src/r6_tactics_board/presentation/pages/editor/editor_page.py)
  编辑器总编排，负责把时间轴、画布、播放、工程状态和多条工作流串起来。
- [editor_properties.py](../../src/r6_tactics_board/presentation/pages/editor/editor_properties.py)
  右侧属性面板刷新链。
- [editor_timeline.py](../../src/r6_tactics_board/presentation/pages/editor/editor_timeline.py)
  时间轴列切换 / 当前上下文同步链。
- [editor_tokens.py](../../src/r6_tactics_board/presentation/pages/editor/editor_tokens.py)
  通用道具 / 技能道具工作流。
- [editor_playback.py](../../src/r6_tactics_board/presentation/pages/editor/editor_playback.py)
  播放 / 过层路线同步链。
- [editor_views.py](../../src/r6_tactics_board/presentation/pages/editor/editor_views.py)
  地图 / 2.5D 双视图同步链。
- [editor_project_state.py](../../src/r6_tactics_board/presentation/pages/editor/editor_project_state.py)
  工程读写与页面状态恢复链。
- [editor_scene_sync.py](../../src/r6_tactics_board/presentation/pages/editor/editor_scene_sync.py)
  画布局部刷新与选中态同步链。
- [editor_models.py](../../src/r6_tactics_board/presentation/pages/editor/editor_models.py)
  编辑器局部状态结构。
- [editor_panels.py](../../src/r6_tactics_board/presentation/widgets/editor/editor_panels.py)
  右侧属性面板和底部播放浮层。
- [timeline_widget.py](../../src/r6_tactics_board/presentation/widgets/timeline/timeline_widget.py)
  时间轴表格、列头、行头和交互反馈。

### 画布与图元

- [map_scene.py](../../src/r6_tactics_board/presentation/widgets/canvas/map_scene.py)
  2D 战术画布。干员、互动点、战术面、通用道具、技能道具都在这里同步。
- [map_view.py](../../src/r6_tactics_board/presentation/widgets/canvas/map_view.py)
  缩放、平移和视图层行为。
- [operator_item.py](../../src/r6_tactics_board/presentation/widgets/canvas/operator_item.py)
  干员图元。
- [map_surface_item.py](../../src/r6_tactics_board/presentation/widgets/canvas/map_surface_item.py)
  软墙与 Hatch 面图元。
- [map_interaction_item.py](../../src/r6_tactics_board/presentation/widgets/canvas/map_interaction_item.py)
  楼梯和其他互动点图元。
- [map_gadget_item.py](../../src/r6_tactics_board/presentation/widgets/canvas/map_gadget_item.py)
  通用道具与技能道具图元。

### 2.5D 总览

- [overview_scene.py](../../src/r6_tactics_board/presentation/widgets/canvas/overview_scene.py)
  2.5D 数据整理和渲染驱动。
- [overview_view.py](../../src/r6_tactics_board/presentation/widgets/canvas/overview_view.py)
  2.5D 视图交互。
- [overview_projection.py](../../src/r6_tactics_board/presentation/widgets/canvas/overview_projection.py)
  2D 到 2.5D 的投影转换。

### 地图 Debug

- [debug_page.py](../../src/r6_tactics_board/presentation/pages/debug/debug_page.py)
  地图元数据编辑入口。
- [map_debug_scene.py](../../src/r6_tactics_board/presentation/widgets/canvas/map_debug_scene.py)
  楼梯、Hatch 面、软墙和互动点的绘制与编辑逻辑。

### 资源与工程

- [asset_registry.py](../../src/r6_tactics_board/infrastructure/assets/asset_registry.py)
  资源索引、查询、数量写回和兼容迁移。
- [asset_paths.py](../../src/r6_tactics_board/infrastructure/assets/asset_paths.py)
  资源目录与运行时路径。
- [project_store.py](../../src/r6_tactics_board/infrastructure/persistence/project_store.py)
  工程文件读写。

### 编辑器服务层

- [editor_session.py](../../src/r6_tactics_board/application/services/editor_session.py)
  页面到资源层 / 工程层的统一调用入口。
- [timeline_editor.py](../../src/r6_tactics_board/application/timeline/timeline_editor.py)
  时间轴增删改。
- [controller.py](../../src/r6_tactics_board/application/playback/controller.py)
  播放状态推进。
- [interaction_routing.py](../../src/r6_tactics_board/application/routing/interaction_routing.py)
  楼梯 / Hatch 的自动寻路与过层分段。

## 常见修改入口

### 改干员属性或时间轴语义

先看：
- [models.py](../../src/r6_tactics_board/domain/models.py)
- [editor_properties.py](../../src/r6_tactics_board/presentation/pages/editor/editor_properties.py)
- [editor_timeline.py](../../src/r6_tactics_board/presentation/pages/editor/editor_timeline.py)

### 改地图元数据或战术面

先看：
- [asset_registry.py](../../src/r6_tactics_board/infrastructure/assets/asset_registry.py)
- [debug_page.py](../../src/r6_tactics_board/presentation/pages/debug/debug_page.py)
- [map_debug_scene.py](../../src/r6_tactics_board/presentation/widgets/canvas/map_debug_scene.py)
- [map_surface_item.py](../../src/r6_tactics_board/presentation/widgets/canvas/map_surface_item.py)

### 改通用道具 / 技能道具逻辑

先看：
- [gadget_counts_page.py](../../src/r6_tactics_board/presentation/pages/assets/gadget_counts_page.py)
- [editor_tokens.py](../../src/r6_tactics_board/presentation/pages/editor/editor_tokens.py)
- [editor_scene_sync.py](../../src/r6_tactics_board/presentation/pages/editor/editor_scene_sync.py)
- [map_gadget_item.py](../../src/r6_tactics_board/presentation/widgets/canvas/map_gadget_item.py)

### 改 2.5D 显示或过层表现

先看：
- [editor_playback.py](../../src/r6_tactics_board/presentation/pages/editor/editor_playback.py)
- [editor_views.py](../../src/r6_tactics_board/presentation/pages/editor/editor_views.py)
- [overview_scene.py](../../src/r6_tactics_board/presentation/widgets/canvas/overview_scene.py)
- [overview_view.py](../../src/r6_tactics_board/presentation/widgets/canvas/overview_view.py)
- [interaction_routing.py](../../src/r6_tactics_board/application/routing/interaction_routing.py)

### 改撤销 / 保存 / 页面恢复

先看：
- [editor_project_state.py](../../src/r6_tactics_board/presentation/pages/editor/editor_project_state.py)
- [project_store.py](../../src/r6_tactics_board/infrastructure/persistence/project_store.py)
- [editor_session.py](../../src/r6_tactics_board/application/services/editor_session.py)

## 当前最需要继续控制复杂度的模块

- [editor_page.py](../../src/r6_tactics_board/presentation/pages/editor/editor_page.py)
  现在已经降到页面级总编排，但仍然是编辑器的主入口。
- [asset_registry.py](../../src/r6_tactics_board/infrastructure/assets/asset_registry.py)
  仍然同时承担索引、查询、写回和迁移逻辑。

## 已完成的低风险拆分

- 道具 / 技能工作流
- 右侧属性面板刷新链
- 时间轴列切换 / 当前上下文同步链
- 播放 / 过层路线同步链
- 地图 / 2.5D 双视图同步链
- 工程读写与页面状态恢复链
- 画布局部刷新与选中态同步链

下一批如果继续拆，优先看：
- `asset_registry.py` 的读写与索引分层
- `map_scene.py` 的 overlay / token / operator 局部刷新分层
