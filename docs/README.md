# Docs

`docs/` 用来放“先看什么、再改什么”的说明，目标是降低阅读和接手成本。

## 建议阅读顺序

1. [架构总览](architecture/overview.md)
2. [代码地图](architecture/codebase_map.md)
3. [编辑器主流程](architecture/editor_workflow.md)
4. [路线图](architecture/roadmap.md)
5. [资源规范](resources/assets.md)

## 目录说明

- `architecture/`
  说明代码分层、主流程、关键模块入口和后续重构方向。
- `resources/`
  说明地图、干员、道具等资源结构与元数据约定。
- `distribution/`
  说明打包和发布流程。

## 当前最重要的文档

- [overview.md](architecture/overview.md)
  说明当前项目的分层结构和职责边界。
- [codebase_map.md](architecture/codebase_map.md)
  说明“哪个功能改哪个文件”。
- [editor_workflow.md](architecture/editor_workflow.md)
  说明战术编辑页的数据流、状态来源和时间轴语义。
- [theme.md](architecture/theme.md)
  说明主题切换和颜色令牌。

## 维护规则

- 文档内容要以当前仓库真实代码为准。
- 新增模块时，优先先补所在目录的 `README.md`。
- 文本文件统一使用 `UTF-8 + LF`。
