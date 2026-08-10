# Trae任务模板

## 版本

PGF v2.0

## 引用

本模板为PGF v2.0治理框架的Trae任务模板，所有Trae验收任务必须使用此模板。

## 环境

[填写验收环境名称]

## 端口

[填写验收端口，如：8001]

## 数据库

[填写数据库路径，如：data/rehearsal/v06j_app_migrated.db]

## 账号

[填写测试账号信息，如：admin/admin123]

## URL

[填写待测试的URL列表]

## 步骤

[按顺序列出测试步骤]

## HTTP

[记录每个URL的HTTP状态码]

## Console

[记录浏览器控制台日志]

## Network

[记录网络请求和响应]

## 截图

[记录关键页面截图]

## 结论

[填写验收结论：environment_invalid / blocked / conditional_pass / pass_for_formal_migration]

## 禁止修改

[列出禁止修改的内容]

---

## 使用示例

### 环境
演练环境v06L

### 端口
8001

### 数据库
data/rehearsal/v06j_app_migrated.db

### 账号
无（未登录测试）

### URL
- http://127.0.0.1:8001/admin/platform
- http://127.0.0.1:8001/club/apply
- http://127.0.0.1:8001/club/events

### 步骤
1. 确认8001服务已启动，数据库路径正确
2. 访问/admin/platform，验证是否重定向到登录页面
3. 访问/club/apply，验证是否公开访问
4. 填写会员申请表单并提交
5. 验证数据库是否写入记录

### HTTP
- /admin/platform: 302 → /account/login
- /club/apply: 200
- /club/events: 302 → /account/login

### Console
无错误

### Network
- POST /club/apply: 200 OK

### 截图
[截图1：登录页面重定向]
[截图2：会员申请表单]
[截图3：提交成功]

### 结论
conditional_pass

### 禁止修改
- 不修改任何Python代码
- 不修改任何模板
- 不执行迁移
- 不修改数据库结构