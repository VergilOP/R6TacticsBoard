# R6 Tactics Board

一个基于 `PyQt6` 与 `PyQt6-Fluent-Widgets` 的《彩虹六号：围攻》战术板桌面工具，用于地图摆位、阶段式跑位编排与关键帧回放。

## 项目简介

R6 Tactics Board 面向单机桌面编辑场景，目标是把静态摆点升级为可推演的战术过程展示。

当前版本已经具备首个 MVP 所需的核心能力：

- 地图加载、滚轮缩放、中键平移
- 干员节点添加、拖拽、删除、属性编辑
- 图标模式 / 自定义名称模式切换
- 表格式时间轴：横轴关键帧，纵轴干员
- 关键帧记录、列复制、列插入、列删除
- 相邻关键帧之间的平滑播放
- 工程保存 / 读取
- 资源页双击加载地图、双击创建干员
- 主题切换、测试调试页、撤销 / 重做

## 界面说明

应用当前包含以下页面：

- `战术编辑`：地图编辑、干员属性、时间轴与播放控制
- `资源管理`：地图与干员图标资源浏览，支持双击快速载入
- `测试调试`：预留给开发期调试工具
- `设置`：主题风格切换，默认深色主题

## 资源目录

项目默认读取以下资源目录：

- `assets/maps/`
- `assets/operators/attack/`
- `assets/operators/defense/`

建议约定：

- 地图文件放入 `assets/maps/`
- 进攻方图标放入 `assets/operators/attack/`
- 防守方图标放入 `assets/operators/defense/`
- 图标文件名使用干员标识，例如 `ash.png`、`thermite.png`、`smoke.png`

## 工程文件

工程文件使用 `*.r6tb.json` 格式保存，内容包括：

- 当前地图路径
- 干员全局定义（名称、阵营、图标 key）
- 干员顺序
- 时间轴显式记录单元格（位置、朝向、显示模式）
- 当前关键帧列
- 播放过渡时长

工程保存时优先使用相对路径，便于在同一工程目录下迁移与共享素材。

## 环境要求

- Windows
- Python `3.12`
- `PyQt6`
- `PyQt6-Fluent-Widgets`
- `PyQt6-Frameless-Window`

## 安装与运行

创建虚拟环境：

```powershell
python -m venv .venv
```

安装依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e .
```

开发运行：

```powershell
.\.venv\Scripts\pythonw.exe -m r6_tactics_board
```

也可以使用安装后的入口：

```powershell
.\.venv\Scripts\r6-tactics-board.exe
```

## 打包

构建 Windows 可执行文件：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1
```

构建产物默认输出到 `dist/R6TacticsBoard/`。

## 项目结构

```text
R6TacticsBoard/
├─ assets/
│  ├─ maps/
│  └─ operators/
│     ├─ attack/
│     └─ defense/
├─ docs/
├─ scripts/
├─ src/
│  └─ r6_tactics_board/
│     ├─ app.py
│     ├─ main.py
│     ├─ domain/
│     ├─ application/
│     ├─ infrastructure/
│     └─ presentation/
└─ pyproject.toml
```

## 文本文件规范

项目统一使用以下文本格式：

- 编码：`UTF-8`
- 换行：`LF`

不使用：

- `GBK` / `ANSI`
- `UTF-8 BOM`
- `CRLF`

## 许可说明

本项目依赖的上游组件 [PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) 为 `GPL-3.0`。如需闭源分发或商业化使用，应先评估依赖许可兼容性。

## 后续计划

- 工程级资源导入与管理
- 更完整的时间轴编辑能力
- 更细的视觉表现与提示反馈
- 首次发布前的导出与发布流程收口

## 更新日志

<details>
<summary>展开查看</summary>

### v0.1.1

- 重构干员数据模型，区分全局属性与关键帧局部状态
- 调整工程文件结构，并兼容旧版 `operator_states` 存档读取
- 新增右侧关键帧属性面板，支持编辑关键帧名称与备注
- 支持拖拽调整关键帧列顺序与干员行顺序
- 优化地图放置交互，支持连续放置、拖拽定向与路径虚线预览
- 优化干员图标样式，缩小圆点与方向三角，文字改为圆心轻量显示
- 补充保存目录忽略规则与架构文档说明

### v0.1.0

- 完成首个桌面 MVP
- 支持地图加载、缩放、平移与视图重置
- 支持干员节点添加、拖拽、删除与属性编辑
- 支持进攻 / 防守资源目录扫描与图标接入
- 支持表格式关键帧时间轴与列级编辑
- 支持关键帧之间的平滑播放与过渡时长控制
- 支持工程保存 / 读取
- 支持撤销 / 重做、未保存提示与删除确认
- 支持默认深色主题、设置页与测试调试页
- 支持 Windows 打包脚本与开发态 / 打包态资源路径兼容

</details>
