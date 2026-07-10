# 排障说明

## 页面出现 Internal Server Error

1. 先运行模板预编译：`.venv\Scripts\python.exe scripts\check_all_templates.py`。
2. 再运行核心页面烟测：`.venv\Scripts\python.exe scripts\verify_core_pages.py`。
3. 查看 `logs/` 中的本地运行日志，定位具体路由或模板。

## 登录页或俱乐部页面报错

优先检查：

- `app/templates/v05a_security.html`
- `app/templates/v04f_club.html`
- `app/templates/v05d_member_portal.html`
- `app/templates/v05d_member_admin.html`

这些页面依赖登录状态、会员资料和导航上下文，修改时需要同时跑核心页面烟测。

## 出现乱码

运行：

```bat
.venv\Scripts\python.exe scripts\check_mojibake.py
```

扫描范围包括模板、静态脚本、用户可见 Python 消息、批处理脚本和文档。发现问题后应修复源码，不要只在页面上做临时替换。

## 验证依赖缺失

如果系统 Python 提示缺少 `jinja2`、`fastapi` 或 `sqlalchemy`，请使用项目虚拟环境：

```bat
.venv\Scripts\python.exe scripts\verify_all.py
```

## 数据异常

不要手动删除数据库。先执行备份脚本，再通过审核、回滚或维护脚本处理异常记录。
