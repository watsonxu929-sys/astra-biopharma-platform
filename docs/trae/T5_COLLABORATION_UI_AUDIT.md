# T5 业务协同UI审计报告

## 审计日期
2026-07-14

## 当前状态

### Git状态
- 分支：rescue/trae-4day-usable-mvp
- T4提交：63b48d6
- T4标签：checkpoint-trae-t4-club-usable
- stash@{0}：P5相关WIP（7个文件）
- stash@{1}：fix/p0-p1-stability-domain-unification相关

### 数据库状态
- v06_opportunities：11条数据
- P5增量表（p5_opportunity_participants等）：不存在

## 已提交并可用的P5能力

### 服务层
1. **UnifiedOpportunityService** (`app/services/unified_opportunity_service.py`)
   - 统一机会模型服务
   - 支持列表、详情、创建、阶段更新
   - 支持权限控制（can_access, can_manage）
   - 支持联系人意向转化

2. **BusinessCollaborationService** (`app/services/business_collaboration_service.py`)
   - 完整的商务协同服务
   - 支持线索创建、审核、转化
   - 支持机会阶段推进、参与者管理
   - 支持跟进记录、任务、会议、材料
   - 支持风险计算和仪表盘
   - **注意**：require_schema()检查P5表，当前会返回409错误

### API层
1. **opportunities.py** (`app/api/v1/opportunities.py`)
   - 列表、详情、创建、阶段更新、跟进、任务

## 仅存在于其他分支或stash的能力

### stash@{0}包含
- app/api/v1/opportunities.py 增强
- app/api/v1/router.py 路由注册
- app/main.py 路由注册
- app/routes_platform.py 平台路由
- app/services/unified_opportunity_service.py 增强
- app/templates/platform/opportunities.html

## 缺失能力

1. **导航入口**：业务协同二级菜单未收敛
2. **前端页面**：协同首页、线索、合作机会详情、任务与跟进、会议与材料
3. **P5表**：p5_opportunity_participants、p5_opportunity_stage_history等
4. **线索表**：v04f_lead_records（P5表依赖）
5. **跟进表**：v06_follow_ups
6. **任务表**：v06_collab_tasks

## 当前正式Opportunity入口

- API：GET/POST /api/v1/opportunities
- 模板：app/templates/platform/opportunity_detail.html（存在但可能不完整）

## 当前页面和菜单问题

1. 业务协同菜单未收敛，缺少二级菜单结构
2. 机会列表页面不完整
3. 详情页缺少参与方、阶段历史、跟进时间线
4. 无任务、会议、材料管理页面
5. 无线索管理页面

## 本轮可安全复用的最小范围

### 必选（无需P5表）
1. UnifiedOpportunityService → 机会列表、详情、创建、阶段更新
2. v06_opportunities表已有数据 → 可展示

### 可选（需要兼容处理）
1. BusinessCollaborationService → 需添加try-except处理缺失表
2. 线索功能 → P5表不存在时显示空状态
3. 任务、跟进、会议 → P5表不存在时显示空状态

### 禁止（本轮不做）
1. 执行008迁移
2. 整包恢复stash
3. 重写Opportunity服务
4. 自动转化ClubLead为Opportunity

## 建议策略

1. **导航收敛**：添加业务协同二级菜单（5项）
2. **页面创建**：基于现有服务创建最小可用页面
3. **兼容处理**：P5表不存在时显示空状态，不报错
4. **权限控制**：利用现有权限体系（admin、view_internal、edit_data）
5. **中文化**：替换英文模型名为中文显示