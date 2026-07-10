# P2.1 AI Provider

业务层只依赖 `AIProvider`，统一提供 summarize、classify_event、extract_entities、extract_fact_candidates、assess_importance 和 generate_research_outline。当前实现：

- `RuleProvider`：正式可用的确定性规则，版本 `p2.1-rule-v1`；识别融资、获批、合作、临床进展、招聘及常见机构后缀。
- `MockProvider`：仅用于测试，所有结果明确标记 `generated_by=mock`。
- `OpenAIProvider`：惰性适配器，只从 `OPENAI_API_KEY` 和 `OPENAI_MODEL` 读取配置；无 Key 或 SDK 时不发起调用，注册表回退 RuleProvider。

所有输出先经过结构校验。每个候选必须包含类型、值、证据片段和 0–100 置信度；失败记录进 `p2_ai_analysis_runs`。AI 结果只能创建 FactCandidate，不能直接发布产品、修改主体主档或生成商机。
