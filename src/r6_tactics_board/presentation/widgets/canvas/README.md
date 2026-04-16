# Canvas Widgets

这里放编辑器相关的场景、视图和图元。

## 文件分工

- [map_view.py](map_view.py)
  2D 视图层，负责缩放和平移。
- [map_scene.py](map_scene.py)
  2D 战术画布总控。
- [map_debug_scene.py](map_debug_scene.py)
  地图 Debug 编辑场景。
- [operator_item.py](operator_item.py)
  干员图元。
- [map_gadget_item.py](map_gadget_item.py)
  通用道具和技能道具图元。
- [map_surface_item.py](map_surface_item.py)
  软墙和 Hatch 面图元。
- [map_interaction_item.py](map_interaction_item.py)
  楼梯等互动点图元。
- [overview_scene.py](overview_scene.py)
  2.5D 数据驱动。
- [overview_view.py](overview_view.py)
  2.5D 视图。

## 修改约定

- 继承语义不要在图元层处理，图元层只吃“已解析好的状态”。
- 点击范围如果与显示范围有关，优先检查 `boundingRect()` 和 `shape()` 是否一致。
- 任何“拖动后写回关键帧”的逻辑，优先放在 `map_scene.py` 和页面层之间处理，不要让图元自己改时间轴。

## 当前最关键的边界

- `map_scene.py` 负责用户交互和图元同步。
- `editor_scene_sync.py` 负责画布选中态、拖拽写回和时间轴同步。
- `editor_timeline.py` / `editor_playback.py` 负责时间轴状态解析和播放过程。
- `overview_scene.py` 负责把解析后的状态转换成 2.5D 表达。

## 当前注意事项

- 通用道具 / 技能道具的图标显示只吃解析后的当前状态，不在图元层判断“一次性 / 保留”。
- 软墙与 `Hatch` 面是地图资源图元，战术状态由工程文件叠加。
- 楼梯是互动点图元，当前已经支持起点、终点和折线轨迹。
