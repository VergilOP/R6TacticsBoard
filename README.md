# R6 Tactics Board

[![Bilibili](https://img.shields.io/badge/Bilibili-89590088-00A1D6?logo=bilibili&logoColor=white)](https://space.bilibili.com/89590088)
![Bilibili Followers](https://img.shields.io/badge/dynamic/json?color=00A1D6&label=%E7%B2%89%E4%B8%9D&query=%24.data.follower&url=https%3A%2F%2Fapi.bilibili.com%2Fx%2Frelation%2Fstat%3Fvmid%3D89590088&logo=bilibili&logoColor=white)

一个基于 `PyQt6` 与 `PyQt6-Fluent-Widgets` 的《彩虹六号：围攻》战术板桌面工具，用于地图摆位、阶段式跑位编排与关键帧回放。

## 项目简介

R6 Tactics Board 面向单机桌面编辑场景，目标是把静态摆点升级为可推演的战术过程展示。

当前版本已经具备首个 MVP 所需的核心能力：

- 按整张地图资源导入，支持多楼层切换
- 地图加载、滚轮缩放、中键平移
- 干员节点添加、拖拽、删除、属性编辑
- 图标模式 / 自定义名称模式切换
- 表格式时间轴：横轴关键帧，纵轴干员
- 关键帧记录、列复制、列插入、列删除
- 相邻关键帧之间的平滑播放
- 基于地图互动点的跨楼层自动路径 / 手动路径
- 地图 Debug 模式，可编辑楼梯、舱口等互动点元数据
- 底部悬浮播放栏，支持播放控制、进度拖动与速度调整
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

- `src/assets/maps/`
- `src/assets/operators/attack/`
- `src/assets/operators/defense/`

当前地图资源结构约定为：

```text
src/assets/maps/
├─ index.json
├─ download_all.sh
├─ download_maps.sh
├─ download_blueprints.js
├─ create_json.sh
└─ <map_key>/
   ├─ map.json
   ├─ 1f.png / 2f.png / 3f.png
   ├─ b1.png
   └─ roof.png
```

当前干员资源结构约定为：

```text
src/assets/
├─ maps/
└─ operators/
   ├─ index.json
   ├─ download_ops.py
   ├─ attack/
   │  ├─ icons/
   │  │  └─ <operator_key>.png
   │  ├─ portraits/
   │  │  └─ <operator_key>.png
   │  └─ abilities/
   │     └─ <operator_key>/
   │        ├─ icon.png
   │        ├─ name.txt
   │        └─ description.txt
   └─ defense/
      ├─ icons/
      │  └─ <operator_key>.png
      ├─ portraits/
      │  └─ <operator_key>.png
      └─ abilities/
         └─ <operator_key>/
            ├─ icon.png
            ├─ name.txt
            └─ description.txt
```

资源命名约定：

- 地图文件放入 `src/assets/maps/`
- 地图目录使用 `<map_key>`，当前以英文小写短横线命名
- 每张地图单独维护 `map.json`
- `src/assets/maps/index.json` 作为地图资源总索引
- 楼层图按 `1f.png`、`2f.png`、`3f.png`、`b1.png`、`roof.png` 等方式命名
- 干员标识统一使用英文小写 `operator_key`
- 图标与立绘文件统一命名为 `<operator_key>.png`
- 技能目录名与干员 `operator_key` 保持一致
- `name.txt` 与 `description.txt` 使用 `UTF-8 + LF`
- `src/assets/operators/index.json` 作为干员资源总索引

后续如需批量导入、校验或重建资源索引，以上结构视为项目内固定约定。

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
├─ docs/
│  ├─ README.md
│  ├─ architecture/
│  ├─ resources/
│  └─ distribution/
├─ scripts/
├─ src/
│  ├─ assets/
│  │  ├─ maps/
│  │  └─ operators/
│  │     ├─ attack/
│  │     └─ defense/
│  └─ r6_tactics_board/
│     ├─ app.py
│     ├─ main.py
│     ├─ README.md
│     ├─ domain/
│     ├─ application/
│     │  ├─ services/
│     │  ├─ routing/
│     │  ├─ timeline/
│     │  ├─ state/
│     │  └─ playback/
│     ├─ infrastructure/
│     │  ├─ assets/
│     │  ├─ persistence/
│     │  └─ diagnostics/
│     └─ presentation/
│        ├─ shell/
│        ├─ pages/
│        └─ widgets/
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

### v0.4.0

- 重构源码目录，按 `domain / application / infrastructure / presentation` 分层并细分子目录
- 将编辑器关键逻辑拆分到独立模块，包括会话服务、路径规划、时间轴控制、播放控制和状态容器
- 将主窗口、页面、画布、面板、时间轴控件按职责重新归档，降低 `EditorPage` 的聚合复杂度
- 将资源目录统一迁移到 `src/assets/`，同步修正文档、打包脚本和目录约定
- 为主要目录补充结构 README，明确职责边界、依赖方向和新文件落点规则

### v0.3.0

- 地图资源工作流升级为多楼层整图编辑，新增左侧悬浮楼层切换栏
- 干员关键帧状态接入楼层属性，支持跨楼层摆位、预览与播放跟随
- 新增地图 Debug 模式，可为 `map.json` 编辑楼梯、舱口等互动点元数据
- 播放系统新增基于互动点的跨楼层自动寻路，并支持手动互动点指定
- 底部悬浮播放栏补齐上一项 / 下一项、播放暂停、速度与进度条交互
- 优化手动互动点候选、高亮、下拉框样式与相关稳定性问题

### v0.2.1

- 修复仓库中二进制资源被文本换行规则误处理的问题，补充二进制文件 Git 属性约束
- 回填并替换受影响的地图、图标、立绘与技能图标资源，恢复本地与 GitHub 的正常预览与读取
- 本次为非功能性修复版本，不引入编辑器交互、时间轴或播放流程的功能变更

### v0.2.0

- 新增地图与干员资源资产集，补齐 `src/assets/maps` 与 `src/assets/operators` 目录结构
- 地图加载流程升级为按整张地图资源导入，支持基于 `map.json` 读取楼层与元数据
- 编辑页新增左侧悬浮楼层切换栏，可在多楼层地图间快速切换显示
- 干员关键帧状态新增楼层属性，切换楼层时仅显示当前楼层对应的干员状态
- 播放过程支持按当前选中干员的关键帧楼层自动切换画布楼层
- 优化时间轴放置交互，单元格选中可持续放置，并兼容楼层切换后的继续编辑
- 优化干员图标表现，区分图标朝向与内容朝向，收口圆点、文字与方向三角样式

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

## 地图 Debug 元数据

当前项目已经开始支持地图级自定义元数据编辑。  
在 `测试调试` 页中，可以针对当前地图与楼层设置互动点，并写回对应的 `map.json`。

当前互动点数据写入：
- `layers.interactions`
- `layers.stairs`
- `layers.hatches`

当前支持的互动点类型：
- `stairs`：可配置为双向联通，适合楼梯
- `hatch`：默认单向联通，适合舱口

互动点基础字段包括：
- `id`
- `kind`
- `position`
- `floor_key`
- `linked_floor_keys`
- `is_bidirectional`
- `label`
- `note`

后续墙体、门窗、舱口、爆破点等地图扩展结构，会沿这套 `map.json` 元数据方案继续扩展。

## Star History

<a href="https://www.star-history.com/?repos=VergilOP%2FR6TacticsBoard&type=date&logscale=&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=VergilOP/R6TacticsBoard&type=date&theme=dark&logscale&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=VergilOP/R6TacticsBoard&type=date&logscale&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/image?repos=VergilOP/R6TacticsBoard&type=date&logscale&legend=top-left" />
 </picture>
</a>
