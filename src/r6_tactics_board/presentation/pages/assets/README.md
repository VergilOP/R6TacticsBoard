# Assets Pages

这里放资源浏览和资源配置相关页面。

## 文件说明

- [assets_page.py](assets_page.py)
  地图、干员资源浏览和快速导入入口。
- [gadget_counts_page.py](gadget_counts_page.py)
  通用道具和技能道具数量/保留类型配置页。

## 数据写回位置

### 通用道具

写回：
- [src/assets/gadgets/index.json](../../../../../src/assets/gadgets/index.json)

负责：
- 默认上限
- 阵营归属
- 是否保留在地图上

### 技能道具

写回：
- [src/assets/operators/index.json](../../../../../src/assets/operators/index.json)

负责：
- 每个干员技能上限
- 每个干员技能是否保留在地图上

## 当前页面语义

- 上半区按 `进攻方通用道具 / 防守方通用道具` 分组编辑通用道具定义。
- 下半区按 `进攻方技能道具 / 防守方技能道具` 分组编辑干员技能定义。
- 数量配置页只改资源定义，不直接改任何战术工程文件。

## 修改建议

- 资源配置页只负责“资源定义”，不要直接承担时间轴逻辑。
- 编辑器里的显示和限制，应通过 [asset_registry.py](../../../infrastructure/assets/asset_registry.py) 统一读取。
