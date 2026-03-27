# r6_tactics_board 包结构

本目录按 `domain / application / infrastructure / presentation` 分层组织，目标是把“稳定业务概念”“编辑流程逻辑”“外部交互”“Qt 界面”分开维护。

## 分层职责

- `domain/`: 稳定业务模型、枚举、解析函数。这里不放 Qt，也不放页面状态。
- `application/`: 用例级服务、控制器、状态容器。这里回答“编辑器要怎么做”。
- `infrastructure/`: 资源目录、工程文件、日志等外部交互实现。这里回答“和磁盘、目录、运行环境怎么交互”。
- `presentation/`: Qt 界面层。这里放窗口、页面、场景、图元和复用控件。

## 依赖约定

- `domain` 应只依赖标准库，保持稳定和可复用。
- `application` 可以依赖 `domain`，必要时调用 `infrastructure` 提供的读写能力，但不应引入 Qt 视图对象。
- `infrastructure` 可以依赖 `domain` 做模型落盘和还原，但不负责页面流程编排。
- `presentation` 可以依赖 `application`、`domain`，旧代码中少量直接依赖 `infrastructure` 的情况允许保留；新增逻辑优先通过 `application` 进入。

## 新代码落点

- 新增稳定数据结构、枚举、JSON 解析规则，放 `domain/`。
- 新增编辑流程、控制器、纯逻辑变换，放 `application/`。
- 新增资源扫描、文件读写、日志开关，放 `infrastructure/`。
- 新增窗口、页面、Qt Widget、场景图元，放 `presentation/`。

## 典型改动路径

- 新增一种互动点行为：先改 `domain/models.py`，再补 `application/routing/`，最后接到 `presentation/pages/debug/` 或 `presentation/widgets/canvas/`。
- 新增一种时间轴编辑能力：优先改 `application/timeline/`，界面输入再落到 `presentation/widgets/timeline/` 或 `presentation/pages/editor/`。
- 新增一个一级页面：先在 `presentation/pages/` 新建子目录，再由 `presentation/shell/main_window.py` 接入导航。

## 顶层文件

- `app.py`: 创建 Qt 应用、安装运行时日志等初始化逻辑。
- `main.py`: 程序主入口。
- `__main__.py`: 模块执行入口。
