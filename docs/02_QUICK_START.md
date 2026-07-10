# 02 Quick Start

## 启动系统

```bat
run_windows.bat
```

默认访问地址：

```text
http://127.0.0.1:8000/
```

## 常用页面

- 首页：`/`
- 情报列表：`/intelligence`
- 新增情报：`/intelligence/new`
- 主体：`/organizations`
- 人物：`/people`
- 项目：`/projects`
- 资源：`/resources`
- 事件：`/events`
- 关系：`/relations`
- 行动：`/actions`
- 数据审核：`/review`
- 数据接入：`/review/intake`

## 健康检查

```text
/health
/review/health
/review/intake/health
```

## 推荐日常流程

1. 运行 `run_windows.bat`。
2. 从 `/intelligence/new` 录入或粘贴原始情报。
3. 在 `/review/intake` 导入结构化 JSON 或现有原始情报表。
4. 到 `/review` 审核候选事实、冲突和待确认关联。
5. 回到 `/review/intake` 同步已通过且定为事实的记录。
