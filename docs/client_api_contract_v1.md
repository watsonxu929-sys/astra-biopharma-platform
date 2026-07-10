# Client API Contract v1

## 认证边界

`/api/v1/client/bootstrap` 和 `/api/v1/client/navigation` 复用当前 Web 会话认证。未登录或无 `view_internal` 权限返回现有 401/403 结构，不新增不可用的 Token 登录接口。

## Bootstrap

`GET /api/v1/client/bootstrap?client=web|app|miniprogram`

返回字段：`schema_version`、`api_version`、`server_time`、`current_user`、`current_person`、`current_membership`、`current_organization`、`current_club`、`authorization_summary`、`available_capabilities`、`counters`、`feature_flags`。

不得返回密码、Token、数据库路径、完整环境变量或服务器内部目录。

## Navigation

`GET /api/v1/client/navigation?client=web|app|miniprogram`

返回字段：`schema_version`、`api_version`、`client`、`items`、`groups`、`server_time`。

`items` 每项包含：`capability_key`、`name`、`category`、`parent_key`、`icon_key`、`route`、`deeplink`、`api_prefix`、`status`、`order`、`badge_count`、`permissions_summary`。

客户端类型只影响展示，不扩大权限；三端共享同一 `capability_key`。

## 分页格式

统一分页建议：`items`、`total`、`page`、`page_size`。

## 错误格式

API 错误应为 JSON，不返回 HTML traceback。建议结构：`error.code`、`error.message`、`error.request_id`、`error.details`。

## 版本兼容

`schema_version` 语义版本向后兼容；新增字段不得破坏旧客户端，删除或改名需升级主版本。

## Token 预留

后续移动端 Token 认证应复用同一权限、能力注册和导航服务，不建立独立业务权限表。
