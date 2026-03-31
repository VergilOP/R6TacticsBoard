# Docs

`docs/` 按主题分目录组织，避免架构、资源、发布说明继续平铺在根目录。

## 目录说明

- `architecture/`: 架构设计、分层说明、核心数据流。
- `resources/`: 资源目录、素材规范、`map.json` 元数据约定。
- `distribution/`: 打包、发布、构建相关说明。

## 新文档落点

- 讲代码边界、模块职责、设计取舍，放 `architecture/`。
- 讲地图、干员、索引、资源格式，放 `resources/`。
- 讲 EXE 打包、发布流程、版本发版，放 `distribution/`。

## 维护规则

- 文档路径变化时，优先同步更新根目录 `README.md` 中的项目结构说明。
- 文档内容以当前仓库真实结构为准，不保留旧目录口径。
- 文本文档统一使用 `UTF-8 + LF`。

## 当前重点文档

- `architecture/overview.md`: 当前代码架构总览。
- `architecture/overview_2_5d_plan.md`: 2.5D 全楼层总览的策划、当前阶段状态和后续开发计划。
- `architecture/roadmap.md`: `v0.6.x` 之后的结构与功能路线整理。

## 文档后续计划

- 为 `2.5D` 补一份更细的互动点渲染说明，明确 `stairs / hatch` 的楼层间展开规则。
- 为电竞数据补一份数据源说明，区分本地 JSON、未来 API 和页面展示层字段。
- 为发布流程补一份版本发布清单，统一版本号、README、打包与 release note 更新步骤。
