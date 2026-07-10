# Taxonomy Domain Rules

## 使用枚举

- 流程状态：pending、running、approved、failed 等。
- 权限角色：admin、operator、reviewer、viewer 等。
- 技术稳定类型：source_type、report_type、signal_level 等。

## 使用可配置分类

- 行业赛道、技术方向、地区层级。
- 资源类型、需求类型、机会类型。
- 内容话题、服务能力、市场标签。

## 中文展示

- API 保留机器值，增加 `*_label`。
- 模板调用统一 helper 或服务输出，不在模板重复翻译。
- 无样本显示“暂无数据”，不要用 `0.0` 误导统计已完成。
