v0.4E-A 主体消歧与别名管理

最短安装顺序：
1. 关闭后端。
2. 将本包中的 app、scripts、docs 和 .cmd 文件复制到项目根目录。
3. 按 patches\main_py_必须追加.txt 修改 app\main.py。
4. 按 patches\base_html_导航追加.txt 修改 app\templates\base.html。
5. 双击 migrate_v04e_windows.cmd。
6. 双击 verify_v04e_windows.cmd。
7. 启动 run_windows.bat。
8. 打开 http://127.0.0.1:8000/review/entities/health。
9. 打开 http://127.0.0.1:8000/review/entities。

安全说明：
- 本阶段只做别名、重复检测和人工判断。
- 不执行主体合并。
- 不删除或停用现有主体。
- 不改写项目、关系、事件、行动和事实库引用。
- 实际合并将在 v0.4E-B 单独实施。
