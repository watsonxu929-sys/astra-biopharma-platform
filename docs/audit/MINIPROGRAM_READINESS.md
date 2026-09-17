# 微信小程序V0.1后端准备度

总体 NEEDS_SMALL_FIX / 认证接入MISSING；不是小程序READY。本轮未开发或部署小程序。READY仅指现有读接口有实现/定向检查，不等于移动端完整签收。

|项|状态|真实依据/边界|
|---|---|---|
|认证|MISSING|PC /login签名cookie与/api/v1/me、auth、client bootstrap已有；无已验证微信code交换/绑定/会话刷新契约。不新建第二用户体系|
|情报列表|READY|/api/v1/intelligence→Unified.list；仅published及既有可见性，隔离viewer 200|
|情报详情|READY|/api/v1/intelligence/{id}复用Unified.detail；本轮private/draft/unknown fail closed；证据接口同步检查|
|搜索|READY|/api/v1/search现有search_all；隔离请求200；并非已完成所有结果类型隐私审计|
|企业列表|READY|/api/v1/subjects?subject_type=organization现有api_subject_service，200；不要把身份管理organizations误当企业目录|
|企业详情|READY|/api/v1/subjects/organization/{id}现有get_subject；实现检查，待小程序真实身份端到端验证|
|人物列表|READY|/api/v1/subjects?subject_type=person，200|
|人物详情|READY|/api/v1/subjects/person/{id}现有get_subject，复用隐私与主体上下文；未对全字段逐一移动端验收|
|收藏/关注|NEEDS_SMALL_FIX|routes_platform /api/v1/favorites/toggle、follows/toggle已有表单接口；watchlists另为运营能力，不等价普通个人收藏。需冻结JSON、幂等、列表与自身权限契约|
|分页|READY|page/page_size有界；情报page=0真实422；正常分页200|
|筛选|NEEDS_SMALL_FIX|q/type/industry可用；R3 view/category/start/end/active未在API完整暴露；不能假称PC一致|
|错误响应|NEEDS_SMALL_FIX|api_common有error结构，但校验422/旧路由仍需统一客户端解析契约；非本轮全面重命名|
|权限|NEEDS_SMALL_FIX|view_internal、viewer写403已验证；private详情P1修复。组织级隔离、真实小程序身份绑定与所有对象授权还需冻结契约|
|API版本|READY|真实prefix /api/v1；客户端bootstrap宣告miniprogram并不代表小程序登录已实现|
|采集/审核/系统治理移动端|NOT_REQUIRED_FOR_V0_1|继续在PC端，不移植后台|

V0.1只做首页、情报流/详情、搜索、企业/人物详情、收藏/关注、我的。API Freeze前完成认证决定与最小读取契约差异；不要为此开展推荐、知识图谱、AI或第二个后端。
