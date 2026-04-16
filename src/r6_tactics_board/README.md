# r6_tactics_board Package

这个包按 `domain / application / infrastructure / presentation` 分层。

目标不是绝对纯净，而是让后续维护时能快速判断：
- 新代码应该放哪里
- 某个 bug 应该先看哪一层
- 哪些文件是高风险总控文件

## 分层职责

### `domain/`

放稳定模型和枚举。

典型文件：
- [models.py](domain/models.py)
- [esports_models.py](domain/esports_models.py)

适合放：
- dataclass
- enum
- 纯解析函数

不适合放：
- Qt 控件
- 文件读写
- 页面状态

### `application/`

放编辑器流程、时间轴、播放、路由等“怎么做”。

典型目录：
- [services/](application/services)
- [timeline/](application/timeline)
- [playback/](application/playback)
- [routing/](application/routing)

### `infrastructure/`

放资源、工程文件、日志和外部数据读写。

典型目录：
- [assets/](infrastructure/assets)
- [persistence/](infrastructure/persistence)
- [diagnostics/](infrastructure/diagnostics)

### `presentation/`

放 Qt 页面、主窗口、场景、图元和样式。

典型目录：
- [pages/](presentation/pages)
- [widgets/](presentation/widgets)
- [shell/](presentation/shell)
- [styles/](presentation/styles)

## 当前最需要先读的文件

- [presentation/pages/editor/editor_page.py](presentation/pages/editor/editor_page.py)
  编辑器页面级总编排。具体功能线已拆到同目录的 `editor_*` helper。
- [presentation/pages/editor/README.md](presentation/pages/editor/README.md)
  编辑器各 helper 的职责索引。
- [infrastructure/assets/asset_registry.py](infrastructure/assets/asset_registry.py)
  资源索引、写回、缓存和兼容迁移集中在这里，是下一批最需要继续拆分的模块。
- [presentation/widgets/canvas/map_scene.py](presentation/widgets/canvas/map_scene.py)
  2D 画布的核心，负责干员、战术面、互动点、道具和技能图元的同步与交互。

## 推荐文档入口

- [docs/README.md](../../docs/README.md)
- [docs/architecture/codebase_map.md](../../docs/architecture/codebase_map.md)
- [docs/architecture/editor_workflow.md](../../docs/architecture/editor_workflow.md)
