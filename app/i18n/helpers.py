from __future__ import annotations

from typing import Any

from . import zh_cn


def _safe(value: Any) -> str:
    return str(value or "").strip()


def _fallback(key: str) -> str:
    return key if any("\u4e00" <= ch <= "\u9fff" for ch in key) else "未知"


def translate_status(value: Any, domain: str | None = None) -> str:
    key = _safe(value)
    if not key:
        return "未知"
    if domain and key in zh_cn.DOMAIN_STATUS.get(domain, {}):
        return zh_cn.DOMAIN_STATUS[domain][key]
    return zh_cn.STATUS.get(key, _fallback(key))


def translate_type(value: Any, domain: str | None = None) -> str:
    key = _safe(value)
    if not key:
        return "未知"
    if domain == "report" and key == "track":
        return zh_cn.TYPE["track_report"]
    return zh_cn.TYPE.get(key, _fallback(key))


def translate_role(value: Any) -> str:
    return zh_cn.ROLE.get(_safe(value), "未知角色")


def translate_permission(value: Any) -> str:
    return zh_cn.PERMISSION.get(_safe(value), "未知权限")


def translate_error(code: Any) -> str:
    return zh_cn.ERROR.get(_safe(code), zh_cn.ERROR["INTERNAL_ERROR"])


def translate_field(field_name: Any) -> str:
    key = _safe(field_name)
    return zh_cn.FIELD.get(key, key)


def translate_metric(metric_name: Any) -> str:
    key = _safe(metric_name)
    return zh_cn.METRIC.get(key, key)


def translate_enum(value: Any, enum_group: str) -> str:
    key = _safe(value)
    return zh_cn.ENUM_GROUPS.get(enum_group, {}).get(key, translate_status(key))


def format_metric(metric_name: Any, value: Any) -> dict[str, Any]:
    key = _safe(metric_name)
    label = translate_metric(key)
    if value is None:
        return {"key": key, "label": label, "value": None, "display_value": "暂无数据", "unit": ""}
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return {"key": key, "label": label, "value": value, "display_value": str(value), "unit": ""}
    if key.endswith("_rate") or key in {"source_success_rate", "processing_success_rate", "ambiguous_match_rate"}:
        return {"key": key, "label": label, "value": value, "display_value": f"{numeric:.1f}%", "unit": "%"}
    if key in {"candidate_per_item"}:
        return {"key": key, "label": label, "value": value, "display_value": f"{numeric:.2f} 条", "unit": "条"}
    if "duration" in key:
        seconds = numeric / 1000 if numeric > 300 else numeric
        return {"key": key, "label": label, "value": value, "display_value": f"{seconds:.1f} 秒", "unit": "秒"}
    return {"key": key, "label": label, "value": value, "display_value": f"{numeric:g}", "unit": ""}


def with_labels(row: dict[str, Any], *, status_domain: str | None = None, type_fields: tuple[str, ...] = ("subject_type", "topic_type", "report_type", "candidate_type")) -> dict[str, Any]:
    data = dict(row)
    if "status" in data:
        data["status_label"] = translate_status(data.get("status"), status_domain)
    if "review_status" in data:
        data["review_status_label"] = translate_status(data.get("review_status"))
    if "processing_status" in data:
        data["processing_status_label"] = translate_status(data.get("processing_status"))
    if "dedup_status" in data:
        data["dedup_status_label"] = translate_status(data.get("dedup_status"))
    if "change_status" in data:
        data["change_status_label"] = translate_status(data.get("change_status"))
    for field in type_fields:
        if field in data:
            data[f"{field}_label"] = translate_type(data.get(field), "report" if field == "report_type" else None)
    if "signal_level" in data:
        data["signal_level_label"] = translate_status(data.get("signal_level"), "signal_level")
    if "current_stage" in data:
        data["current_stage_label"] = translate_status(data.get("current_stage"), "pipeline")
    if "confidence_level" in data:
        data["confidence_level_label"] = translate_status(data.get("confidence_level"), "confidence")
    return data


def add_labels(value: Any, *, status_domain: str | None = None) -> Any:
    if isinstance(value, list):
        return [add_labels(item, status_domain=status_domain) for item in value]
    if isinstance(value, dict):
        data = with_labels(value, status_domain=status_domain)
        return {key: add_labels(item, status_domain=status_domain) for key, item in data.items()}
    return value
