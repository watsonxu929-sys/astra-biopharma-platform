from dataclasses import dataclass
from typing import Any

from .models import (
    ActionItem,
    HistoricalEvent,
    Organization,
    Person,
    ProjectPool,
    Relation,
    Resource,
)


@dataclass
class FieldConfig:
    name: str
    label: str
    kind: str = "text"
    required: bool = False
    choices: list[str] | None = None
    help_text: str = ""


@dataclass
class EntityConfig:
    key: str
    title: str
    model: Any
    list_path: str
    fields: list[FieldConfig]


ENTITY_CONFIGS = {
    "organizations": EntityConfig(
        key="organizations",
        title="主体",
        model=Organization,
        list_path="/organizations",
        fields=[
            FieldConfig("standard_name", "标准名称", required=True, help_text="每条记录只对应一家明确机构，不要填写栏目名、企业名录或多家机构。"),
            FieldConfig("org_type", "主体类型"),
            FieldConfig("region", "地域"),
            FieldConfig("industry_tags", "产业标签", "textarea"),
            FieldConfig("resources", "可提供资源", "textarea"),
            FieldConfig("needs", "潜在需求", "textarea"),
            FieldConfig("relationship_source", "关系来源"),
            FieldConfig("visibility", "权限", "select", True, ["公开", "内部", "限制", "本人"]),
            FieldConfig("verification_status", "核验状态", "select", True, ["已确认", "部分待核验", "待核验", "历史对话明确", "已失效"]),
            FieldConfig("source_url", "来源链接"),
            FieldConfig("source_type", "来源类型"),
            FieldConfig("source_title", "来源标题"),
            FieldConfig("source_text", "原始来源正文", "textarea", help_text="用于追溯来源，网页读取后自动保留；正式字段修改不应覆盖原始证据。"),
            FieldConfig("manually_confirmed", "人工确认", "select", False, ["false", "true"]),
        ],
    ),
    "people": EntityConfig(
        key="people",
        title="人物",
        model=Person,
        list_path="/people",
        fields=[
            FieldConfig("name", "姓名", required=True, help_text="每条记录只填写一个真实人物姓名；团队、董事会、专家组应拆成多条。"),
            FieldConfig("public_role", "公开角色", "textarea", help_text="只填写此人的公开职位，不要合并其他人物的职位。"),
            FieldConfig("organization_network", "当前机构/网络", "textarea", help_text="优先填写当前任职机构；教育经历和历史任职请不要全部堆入此字段。"),
            FieldConfig("ability_tags", "能力标签", "textarea"),
            FieldConfig("value_provided", "可提供价值", "textarea", help_text="概括此人的能力、资源或行业经验，不要粘贴多人完整履历。"),
            FieldConfig("relationship_source", "关系来源"),
            FieldConfig("visibility", "权限", "select", True, ["公开", "内部", "限制", "本人"]),
            FieldConfig("verification_status", "核验状态", "select", True, ["已确认", "历史对话明确", "待导入名单", "待核验", "已失效"]),
            FieldConfig("source_url", "来源链接"),
            FieldConfig("source_type", "来源类型"),
            FieldConfig("source_title", "来源标题"),
            FieldConfig("source_text", "原始来源正文", "textarea", help_text="用于追溯来源，网页读取后自动保留；正式字段修改不应覆盖原始证据。"),
            FieldConfig("manually_confirmed", "人工确认", "select", False, ["false", "true"]),
        ],
    ),
    "projects": EntityConfig(
        key="projects",
        title="项目",
        model=ProjectPool,
        list_path="/projects",
        fields=[
            FieldConfig("name", "项目名称", required=True, help_text="每条记录只对应一个明确项目，项目列表请逐条拆分。"),
            FieldConfig("project_type", "类型"),
            FieldConfig("owner_external_id", "归属主体（输入机构编号或名称）"),
            FieldConfig("focus_tags", "重点标签", "textarea"),
            FieldConfig("typical_needs", "典型需求", "textarea"),
            FieldConfig("target_actions", "目标动作", "textarea"),
            FieldConfig("visibility", "权限", "select", True, ["公开", "内部", "限制", "本人"]),
            FieldConfig("status", "状态", "select", True, ["待整理", "重点跟进", "培育中", "已转化", "暂停", "归档"]),
            FieldConfig("source_url", "来源链接"),
            FieldConfig("source_type", "来源类型"),
            FieldConfig("source_title", "来源标题"),
            FieldConfig("source_text", "原始来源正文", "textarea", help_text="用于追溯来源，网页读取后自动保留；正式字段修改不应覆盖原始证据。"),
            FieldConfig("manually_confirmed", "人工确认", "select", False, ["false", "true"]),
        ],
    ),
    "resources": EntityConfig(
        key="resources",
        title="资源",
        model=Resource,
        list_path="/resources",
        fields=[
            FieldConfig("owner_external_id", "提供主体ID", required=True),
            FieldConfig("category", "资源类别"),
            FieldConfig("description", "资源说明", "textarea"),
            FieldConfig("region", "地域"),
            FieldConfig("applicable_to", "适用对象", "textarea"),
            FieldConfig("visibility", "权限", "select", True, ["公开", "内部", "限制", "本人"]),
            FieldConfig("verification_status", "核验状态", "select", True, ["已确认", "部分待核验", "待核验", "已失效"]),
            FieldConfig("source_url", "来源链接"),
            FieldConfig("source_type", "来源类型"),
            FieldConfig("source_title", "来源标题"),
            FieldConfig("source_text", "原始来源正文", "textarea", help_text="用于追溯来源，网页读取后自动保留；正式字段修改不应覆盖原始证据。"),
            FieldConfig("manually_confirmed", "人工确认", "select", False, ["false", "true"]),
        ],
    ),
    "events": EntityConfig(
        key="events",
        title="事件",
        model=HistoricalEvent,
        list_path="/events",
        fields=[
            FieldConfig("event_date", "事件日期"),
            FieldConfig("name", "事件名称", required=True, help_text="每条记录只描述一项事件；新闻列表或多事件综述应拆分。"),
            FieldConfig("event_type", "事件类型"),
            FieldConfig("related_entity", "关联主体ID"),
            FieldConfig("fact_summary", "事实摘要", "textarea"),
            FieldConfig("system_use", "系统用途/机会判断", "textarea"),
            FieldConfig("visibility", "权限", "select", True, ["公开", "内部", "限制", "本人"]),
            FieldConfig("verification_status", "核验状态", "select", True, ["已确认", "待核验", "需补证", "有争议", "已失效"]),
            FieldConfig("source_url", "来源链接"),
            FieldConfig("source_type", "来源类型"),
            FieldConfig("source_title", "来源标题"),
            FieldConfig("source_text", "原始来源正文", "textarea", help_text="用于追溯来源，网页读取后自动保留；正式字段修改不应覆盖原始证据。"),
            FieldConfig("manually_confirmed", "人工确认", "select", False, ["false", "true"]),
        ],
    ),
    "relations": EntityConfig(
        key="relations",
        title="关系",
        model=Relation,
        list_path="/relations",
        fields=[
            FieldConfig("source_external_id", "起点ID", required=True),
            FieldConfig("relation_type", "关系类型", required=True),
            FieldConfig("target_external_id", "终点ID", required=True),
            FieldConfig("period", "时间/期间"),
            FieldConfig("evidence_source", "证据来源", "textarea"),
            FieldConfig("visibility", "权限", "select", True, ["公开", "内部", "限制", "本人"]),
            FieldConfig("verification_status", "核验状态", "select", True, ["已确认", "部分待核验", "待核验", "有争议", "已失效"]),
            FieldConfig("source_url", "来源链接"),
            FieldConfig("source_type", "来源类型"),
            FieldConfig("source_title", "来源标题"),
            FieldConfig("source_text", "原始来源正文", "textarea", help_text="用于追溯来源，网页读取后自动保留；正式字段修改不应覆盖原始证据。"),
            FieldConfig("manually_confirmed", "人工确认", "select", False, ["false", "true"]),
        ],
    ),
    "actions": EntityConfig(
        key="actions",
        title="行动任务",
        model=ActionItem,
        list_path="/actions",
        fields=[
            FieldConfig("task", "任务", required=True),
            FieldConfig("target_external_id", "对象ID"),
            FieldConfig("completion_standard", "完成标准", "textarea"),
            FieldConfig("owner", "负责人"),
            FieldConfig("priority", "优先级", "select", True, ["P0", "P1", "P2", "P3"]),
            FieldConfig("status", "状态", "select", True, ["未开始", "进行中", "已完成", "暂缓"]),
            FieldConfig("suggested_deadline", "建议截止日期"),
            FieldConfig("source_url", "来源链接"),
            FieldConfig("source_type", "来源类型"),
            FieldConfig("source_title", "来源标题"),
            FieldConfig("source_text", "原始来源正文", "textarea", help_text="用于追溯来源，网页读取后自动保留；正式字段修改不应覆盖原始证据。"),
            FieldConfig("manually_confirmed", "人工确认", "select", False, ["false", "true"]),
        ],
    ),
}
