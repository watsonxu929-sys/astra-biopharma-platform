# v0.5B 快速验收

1. 运行 `setup_windows.bat` 补齐 Word、图片和旧 Excel 依赖。
2. 运行 `migrate_all_windows.bat`。
3. 运行 `verify_all_windows.bat`。
4. 启动 `run_windows.bat`。
5. 打开 `http://127.0.0.1:8000/club/import`。
6. 粘贴两名会员资料，确认生成两条独立草稿。
7. 下载 Excel 模板并导入，确认表头自动映射。
8. 上传 `.docx` 或 `.xlsx` 中的照片，确认出现在草稿头像区。
9. 批量保存后进入会员档案，核对人物、机构、联系方式、需求、资源和头像。
10. 再次导入相同手机号，确认系统提示现有会员且默认跳过。
