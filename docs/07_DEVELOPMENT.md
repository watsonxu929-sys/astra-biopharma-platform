# 开发说明

## 目录结构

- `app/`：FastAPI 应用、路由、模板、静态资源和业务服务。
- `app/services/`：业务逻辑优先放在这里，网页路由和 API 共用。
- `app/api/v1/`：对外 API，不新增重复数据表。
- `app/templates/`：Jinja2 用户页面模板。
- `scripts/`：迁移、验证、导入、备份和巡检脚本。
- `docs/`：安装、验收、回滚和开发文档。
- `data/`：本地 SQLite 数据文件，禁止纳入补丁包。

## 开发原则

- 优先复用现有模型、服务和权限。
- 不修改数据库中的英文机器枚举值。
- 不在模板中复制复杂业务规则。
- 用户可见页面保持中文，API 字段名保持兼容。
- 修改前先定位相关路由、服务、模板和脚本，避免全仓无关重构。

## 常用验证

```bat
verify_all_windows.bat
```

```bat
verify_v05m_windows.bat
```

```bat
.venv\Scripts\python.exe scripts\check_all_templates.py
.venv\Scripts\python.exe scripts\check_mojibake.py
.venv\Scripts\python.exe scripts\verify_core_pages.py
```

## 数据保护

不得删除或重建 `data/app.db`。涉及迁移、回滚或修复前，必须先备份数据库和关键代码文件。
