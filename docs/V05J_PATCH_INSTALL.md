# v0.5J 补丁安装、回滚与验收

## 安装

```powershell
setup_windows.bat
migrate_all_windows.bat
verify_all_windows.bat
verify_v05j_windows.bat
start_windows.bat
```

## 单独迁移

```powershell
migrate_v05j_windows.bat
```

迁移执行前会备份 `data/app.db` 到：

```text
data/backups/app_before_v05j_时间戳.db
```

迁移幂等，不执行 `DROP TABLE`，不清空数据，不修改已有主键，不改写已有英文枚举值，不自动生成专题、不自动生成正式招商评级、不自动转线索。

## 回滚

1. 停止应用和后台 worker。
2. 保留当前 `data/app.db` 作为问题现场。
3. 从 `data/backups/app_before_v05j_时间戳.db` 恢复到 `data/app.db`。
4. 恢复补丁前代码。
5. 运行 `verify_all_windows.bat` 确认旧功能可用。

## 人工验收

### 专题研究

1. 打开 `/research/topics/new`。
2. 创建“细胞与基因治疗”专题。
3. 加入 5 家企业。
4. 刷新专题。
5. 打开驾驶舱、事件、信号和关系网络。
6. 检查统计是否可钻取，事实是否可追溯。

### 企业对比

1. 打开 `/research/companies/compare`。
2. 输入 3 家企业编号。
3. 检查基础、融资、技术、团队、风险和机会。
4. 检查缺失数据显示“无公开信息”或“数据不足”。
5. 检查没有企业总分。

### 招商研判

1. 打开 `/research/investment`。
2. 选择一家企业生成研判。
3. 检查 Q-BAY、钱塘租赁和钱塘拿地匹配拆分。
4. 检查 R 和 UNVERIFIED 场景。
5. 人工批准后转为招商线索。
6. 确认未自动创建行动任务。

### 中文化

1. 登录后查看首页、一级菜单和“产业分析”二级导航。
2. 进入采集、加工、流水线、信号、报告、会员、活动、线索、行动。
3. 确认主要状态、按钮、空状态和错误提示为中文。
4. 确认企业英文名、技术缩写、API 路径等白名单未被错误翻译。
5. 调用 API，确认英文机器字段仍保持稳定且包含中文 label。

