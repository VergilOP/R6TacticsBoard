# Editor Page

这里是战术编辑页的页面级入口。

## 文件说明

- [editor_page.py](editor_page.py)
  编辑器总控。负责：
  - 2D / 2.5D 视图切换
  - 播放控制
  - 工程保存/读取
  - 干员、战术面、关键帧三条主流程的页面级编排
- [editor_properties.py](editor_properties.py)
  右侧属性面板工作流。负责：
  - 属性面板刷新
  - 控件可用性分层
  - 手动互动点候选与上下文可见性
  - 右侧页签自动切换的面板侧逻辑
- [editor_timeline.py](editor_timeline.py)
  时间轴与当前上下文同步工作流。负责：
  - 单元格 / 列头点击后的上下文切换
  - 当前列应用与当前楼层跟随
  - 时间轴与底部播放栏刷新
  - 画布选中态与右侧页签的同步
- [editor_tokens.py](editor_tokens.py)
  道具 / 技能工作流拆分模块。负责：
  - 放置模式切换
  - 当前帧道具 / 技能落点写入
  - 已使用数量读取
  - 当前帧清空
  - 全工程同干员道具 / 技能部署清空
- [editor_models.py](editor_models.py)
  编辑页本地状态和辅助结构。

## 进入这个目录前先知道

- 这里不是纯 UI。
- `editor_page.py` 目前承担了很多编排职责，是当前项目里最复杂的单文件之一。
- 如果要继续扩功能，优先想“拆到 application / widgets”，不要继续把流程都堆在页面里。

## 常见修改入口

### 改右侧属性栏行为

先看：
- [editor_properties.py](editor_properties.py)
- [editor_panels.py](../../widgets/editor/editor_panels.py)

### 改时间轴切换后的画布效果

先看：
- [editor_timeline.py](editor_timeline.py)
- `_resolved_state(...)`
- `_sync_scene_placement_target(...)`

### 改道具 / 技能的继承语义

先看：
- [editor_tokens.py](editor_tokens.py)
- `_resolved_frame_state(...)`
- `_resolved_state(...)`

## 当前风险

- 页面同时管理“显式当前帧数据”和“继承后的解析态”。
- 修改时如果不区分这两者，很容易把一次性道具/技能的显示逻辑弄坏。

这类改动前，建议先读：
- [editor_workflow.md](../../../../../docs/architecture/editor_workflow.md)
