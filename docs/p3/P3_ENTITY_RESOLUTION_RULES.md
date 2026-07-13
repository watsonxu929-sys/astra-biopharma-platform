# P3 主体解析规则

## 处理链

来源记录 → 名称/标识规范化 → 强/中/弱特征评分 → `EntityResolutionCandidate` → 人工审核 → 匹配已有主体或明确创建新主体。

候选状态为 pending、matched、create_new、rejected、ambiguous、needs_more_evidence。候选永不直接覆盖正式主档。

## 匹配等级

- 强匹配：已审核的唯一公开标识一致，包括统一社会信用代码、股票代码+市场、官方域名、NMPA/ClinicalTrials.gov 编号、研发代号、ORCID、DOI 和明确 legacy ID。
- 中匹配：正式名称完全一致或已审核别名一致。人物只有在姓名并同时具备机构/职务上下文时才可进入中匹配。
- 弱匹配：仅同名人物、简称相似、跨语言名称、共同出现或语义近似。弱匹配状态保持 ambiguous 或 needs_more_evidence。

## 防误合并

同名人物默认分数上限 0.48；母子公司、品牌与企业、产品与项目、医院院区、企业更名前后均不能仅凭名称自动合并。外部标识冲突会阻止执行合并，不进行静默覆盖。

规范化只处理大小写、空白和常见标点；不会删除有业务含义的公司层级、地区或院区词。

## 来源

服务支持 FactCandidate、FactAssertion、IndustryEvent、RawIntelligence、研究专题、手工录入、导入和会员资料的 `source_record_type/source_record_id` 映射。试点候选必须携带 `is_pilot=1` 和 `pilot_batch_id`。
