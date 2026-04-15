# Editor Page

这里是战术编辑页的页面级入口。

## 文件说明

- [editor_page.py](editor_page.py)
  编辑器总控。负责：
  - 时间轴列切换
  - 右侧属性栏刷新
  - 2D / 2.5D 视图切换
  - 播放控制
  - 工程保存/读取
  - 道具、技能、战术面和互动点的页面级编排
- [editor_models.py](editor_models.py)
  编辑页本地状态和辅助结构。

## 进入这个目录前先知道

- 这里不是纯 UI。
- `editor_page.py` 目前承担了很多编排职责，是当前项目里最复杂的单文件之一。
- 如果要继续扩功能，优先想“拆到 application / widgets”，不要继续把流程都堆在页面里。

## 常见修改入口

### 改右侧属性栏行为

先看：
- [editor_page.py](editor_page.py) 的 `_refresh_property_panel()`
- [editor_panels.py](../../widgets/editor/editor_panels.py)

### 改时间轴切换后的画布效果

先看：
- `_apply_timeline_column(...)`
- `_resolved_state(...)`
- `_sync_scene_placement_target(...)`

### 改道具 / 技能的继承语义

先看：
- `_resolved_frame_state(...)`
- `_resolved_state(...)`
- `_on_gadget_placed(...)`
- `_on_ability_placed(...)`

## 当前风险

- 页面同时管理“显式当前帧数据”和“继承后的解析态”。
- 修改时如果不区分这两者，很容易把一次性道具/技能的显示逻辑弄坏。

这类改动前，建议先读：
- [editor_workflow.md](../../../../../docs/architecture/editor_workflow.md)
