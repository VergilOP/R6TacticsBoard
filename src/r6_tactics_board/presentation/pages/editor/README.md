# Editor Page

这里是战术编辑页的页面级入口。当前目标不是继续堆功能，而是把 `editor_page.py` 按功能线拆成更清晰的协作单元。

## 文件说明

- [editor_page.py](editor_page.py)
  编辑器总编排。负责初始化页面、连接信号、组合各条工作流，不再承载每一条细节逻辑。
- [editor_properties.py](editor_properties.py)
  右侧属性面板刷新链。负责：
  - 干员 / 装修 / 关键帧页签切换
  - 控件显隐和可用性分层
  - 手动互动点候选与上下文提示
- [editor_timeline.py](editor_timeline.py)
  时间轴与当前上下文同步链。负责：
  - 单元格 / 列头点击后的上下文切换
  - 当前列应用与楼层跟随
  - 时间轴与底部播放栏刷新
- [editor_tokens.py](editor_tokens.py)
  通用道具 / 技能道具工作流。负责：
  - 放置模式切换
  - 当前帧落点写入
  - 已使用数量显示与清空
  - 同工程同干员的部署清理
- [editor_playback.py](editor_playback.py)
  播放与过层路线同步链。负责：
  - 关键帧间播放推进
  - 自动 / 手动路径分段
  - 楼梯 / Hatch 过层插值
  - 播放时楼层跟随
- [editor_views.py](editor_views.py)
  地图 / 2.5D 双视图同步链。负责：
  - 地图加载与楼层切换
  - 楼层浮层与播放浮层定位
  - 2D / 2.5D 视图模式切换
  - 2.5D 状态和可见楼层同步
- [editor_project_state.py](editor_project_state.py)
  工程读写与页面状态恢复链。负责：
  - `TacticProject` 构建与应用
  - dirty / clean 判定
  - 撤销 / 重做快照恢复
  - 新模板上下文重置
- [editor_scene_sync.py](editor_scene_sync.py)
  画布局部刷新与选中态同步链。负责：
  - 2D 画布预览路径刷新
  - 战术面 overlay 同步
  - 干员 / 道具 / 技能拖拽写回
  - 当前选中对象与时间轴单元格的同步
- [editor_models.py](editor_models.py)
  编辑器页本地状态结构。

## 当前拆分进度

已完成的低风险拆分：
- `editor_tokens.py`
- `editor_properties.py`
- `editor_timeline.py`
- `editor_playback.py`
- `editor_views.py`
- `editor_project_state.py`
- `editor_scene_sync.py`

这意味着目前 `editor_page.py` 已经主要承担页面级编排，而不是继续堆所有业务细节。

## 进入这个目录前先知道

- 这里不是纯 UI 目录，页面状态、时间轴继承和地图 / 2.5D 协调都在这里汇总。
- 当前最需要继续控制复杂度的文件仍然是：
  - [editor_page.py](editor_page.py)
  - [../../../infrastructure/assets/asset_registry.py](../../../infrastructure/assets/asset_registry.py)
- 修改行为前，优先先确认你在改的是：
  - 当前帧显式数据
  - 继承后的解析态
  - 还是页面级上下文

## 常见修改入口

### 改右侧属性面板行为

先看：
- [editor_properties.py](editor_properties.py)
- [../../widgets/editor/editor_panels.py](../../widgets/editor/editor_panels.py)

### 改时间轴切换后的页面反馈

先看：
- [editor_timeline.py](editor_timeline.py)
- [../../widgets/timeline/timeline_widget.py](../../widgets/timeline/timeline_widget.py)

### 改播放 / 过层表现

先看：
- [editor_playback.py](editor_playback.py)
- [../../../../application/routing/interaction_routing.py](../../../../application/routing/interaction_routing.py)

### 改地图 / 2.5D 双视图同步

先看：
- [editor_views.py](editor_views.py)
- [../../widgets/canvas/overview_scene.py](../../widgets/canvas/overview_scene.py)
- [../../widgets/canvas/overview_view.py](../../widgets/canvas/overview_view.py)

### 改道具 / 技能继承与部署

先看：
- [editor_tokens.py](editor_tokens.py)
- [editor_scene_sync.py](editor_scene_sync.py)
- [../../widgets/canvas/map_gadget_item.py](../../widgets/canvas/map_gadget_item.py)

### 改撤销 / 保存 / 工程恢复

先看：
- [editor_project_state.py](editor_project_state.py)
- [../../../../infrastructure/persistence/project_store.py](../../../../infrastructure/persistence/project_store.py)

## 当前风险

- 页面仍然需要同时协调：
  - 时间轴显式数据
  - 继承后的解析态
  - 当前画布选中态
  - 2.5D 同步态
- 后续继续整理时，优先保持“拆模块，不改行为”。
