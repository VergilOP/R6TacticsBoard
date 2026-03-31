# Canvas Widgets

这里放地图画布及其图元，是编辑和调试页面共用的图形层。

## 当前文件

- `map_view.py`: 缩放与平移视图容器。
- `map_scene.py`: 主编辑场景。
- `overview_projection.py`: 2.5D/3D 总览的楼层布局和坐标换算。
- `overview_scene.py`: 基于 OpenGL 的总览内容控制器，负责楼层贴图、干员覆盖层、可见楼层和路线。
- `overview_view.py`: 基于 `pyqtgraph.opengl.GLViewWidget` 的总览视图，负责 orbit / pan / zoom 交互和屏幕覆盖层绘制。
- `map_debug_scene.py`: 地图互动点调试场景。
- `map_interaction_item.py`: 地图互动点图元。
- `operator_item.py`: 干员图元。

## 适合放这里的内容

- 画布缩放、平移、拖拽、选中等视图交互。
- 图元绘制、命中、拖动和视觉反馈。
- 编辑场景和调试场景的图形对象管理。

## 不要放这里的内容

- 工程读写。
- 路径插值和关键帧变更算法。
- 页面级菜单、提示框、导航。

## 落点规则

- 如果新功能核心是“画布上怎么显示或怎么交互”，放这里。
- 如果新功能核心是“数据应该如何变化”，先考虑 `application/`。
