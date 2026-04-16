# Assets

这里放资源目录与资源索引能力，是地图、楼层、干员素材、通用道具和技能道具配置的入口。

## 适合放这里的内容

- 资源根目录和默认目录定位。
- 地图、楼层、干员、通用道具资源扫描和索引构建。
- 资源元数据读取和保存。
- 通用道具数量、保留类型与技能道具数量配置写回。
- 旧地图资源结构的兼容迁移。

## 不要放这里的内容

- 页面当前选中了哪个地图。
- 素材缩略图如何排版。
- 互动点寻路和关键帧逻辑。

## 当前文件

- `asset_paths.py`: 资源根目录、默认目录与路径辅助函数。
- `asset_models.py`: 资源层 dataclass，包含地图、楼层、干员、通用道具等结构。
- `asset_utils.py`: 资源路径解析、图片扫描、名称归一化等纯辅助函数。
- `map_registry.py`: 地图资源读取、地图元数据写回、旧 Hatch 互动点迁移。
- `operator_registry.py`: 干员图标、干员总索引、技能数量和干员级道具配置写回。
- `gadget_registry.py`: 通用道具总索引、默认数量和保留类型写回。
- `asset_registry.py`: 对外兼容门面，组合上述 registry，保持旧 import 路径稳定。

## 落点规则

- 只要逻辑核心是“从目录里找到什么”和“把资源信息整理成什么”，放这里。
- 如果逻辑开始依赖编辑器当前工程或 UI 选择状态，应提升到 `application/services/`。
- 如果逻辑开始涉及关键帧继承、画布显示或放置行为，应放到编辑器页面 helper 或画布层，不要塞回资源索引层。

## 当前边界

- 外部代码优先继续从 `asset_registry.py` 导入，避免全项目 import 分散。
- 新增地图资源字段时，优先改 `map_registry.py` 和 `asset_models.py`。
- 新增干员 / 技能资源字段时，优先改 `operator_registry.py` 和 `asset_models.py`。
- 新增通用道具字段时，优先改 `gadget_registry.py` 和 `asset_models.py`。
