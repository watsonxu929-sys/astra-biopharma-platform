# v0.5B 完整覆盖补丁安装与回滚

## 安装前

1. 关闭正在运行的后端窗口。
2. 复制整个项目文件夹作为备份。
3. 确认 `data/app.db` 仍在原项目中。

补丁不包含正式数据库、历史日志、虚拟环境或上传图片。

## 覆盖

将补丁压缩包解压到项目根目录，出现同名文件时选择“替换目标中的文件”。

## 安装新依赖

v0.5B 新增 `python-docx`、`Pillow` 和 `xlrd`。

在项目根目录双击：

```bat
setup_windows.bat
```

已有虚拟环境不会被删除，只会补齐依赖并运行自检。

## 安全迁移

```bat
migrate_all_windows.bat
```

迁移前会备份：

```text
data/backups/app_before_migrate_all_YYYYMMDD_HHMMSS.db
```

v0.5B 只新增以下表：

- `v05b_import_jobs`
- `v05b_import_drafts`
- `v05b_media_assets`
- `v05b_member_contacts`
- `v05b_web_image_candidates`

不会删除、重建或清空已有表。

## 验证

```bat
verify_all_windows.bat
```

专项验证脚本为：

```bat
.venv\Scripts\python.exe scripts\verify_v05b.py
```

完整日志：

```text
logs/verify_all_latest.log
```

## 启动与验收

```bat
run_windows.bat
```

打开：

```text
http://127.0.0.1:8000/club/import
```

建议验收：

1. 粘贴两名会员的制表符名单并生成两条草稿；
2. 下载标准 Excel 模板，填写后导入；
3. 上传含照片的 `.docx` 或 `.xlsx`；
4. 核对姓名、机构、职位、联系方式、资源和需求；
5. 批量保存；
6. 打开会员档案确认头像和供需；
7. 再次导入相同手机号，确认出现重复提醒；
8. 使用只读账号确认无法进入智能导入页面。

## 回滚

如需整体回滚：

1. 关闭系统；
2. 恢复安装前的项目文件夹副本；
3. 恢复迁移前数据库备份；
4. 不要删除 `data/uploads/v05b/`，可先保留作为头像文件备份。

如仅回滚代码而保留数据库，新增 v0.5B 表不会影响旧版本运行，但旧页面不会展示头像和导入任务。
