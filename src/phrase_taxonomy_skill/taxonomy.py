from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


MEASURE_PREFIXES = (
    "加强",
    "强化",
    "提升",
    "开展",
    "组织",
    "完善",
    "健全",
    "落实",
    "推进",
    "建立",
    "制定",
    "签订",
    "压实",
    "督促",
    "约谈",
    "整治",
    "整改",
    "整顿",
    "严查",
    "查处",
    "处罚",
    "处理",
    "要求",
    "责令",
    "推动",
    "配备",
    "提供",
    "增设",
    "升级",
    "确保",
    "规范",
    "依法",
    "消除",
    "通报",
    "召开",
    "发出",
    "查封",
    "关停",
)

MANAGEMENT_ACTION_PREFIXES = (
    "未明确",
    "未落实",
    "未建立",
    "未健全",
    "未制定",
)

MANAGEMENT_ACTION_OBJECTS = (
    "责任",
    "责任人",
    "职责",
    "分工",
    "制度",
    "机制",
    "体系",
    "方案",
    "预案",
    "规程",
    "台账",
)

INCOMPLETE_FRAGMENTS = frozenset(
    {
        "未明确",
        "未落实",
        "未建立",
        "未健全",
        "未制定",
    }
)

NEGATION_PREFIXES = ("未", "无", "缺", "违规", "违章", "擅自", "未按", "未曾", "不", "忽视")

CAUSE_KEYWORDS = (
    "未",
    "无",
    "缺失",
    "失效",
    "损坏",
    "破损",
    "漏电",
    "短路",
    "不规范",
    "不到位",
    "不足",
    "违规",
    "违章",
    "擅自",
    "混存混放",
    "淡薄",
    "错误",
    "缺陷",
)

HUMAN_KEYWORDS = (
    "佩戴",
    "上岗",
    "站立",
    "驾驶员",
    "司机",
    "行人",
    "盲区",
    "冒险",
    "忽视",
    "擅自",
    "违章",
    "违规",
    "未检查",
)

OBJECT_KEYWORDS = (
    "设备",
    "设施",
    "平台",
    "系统",
    "电缆",
    "电箱",
    "钢丝绳",
    "防护栏",
    "模板",
    "支撑",
    "机械",
    "装置",
    "构件",
    "脚手架",
    "配电箱",
    "线路",
)

ENVIRONMENT_KEYWORDS = (
    "环境",
    "区域",
    "地面",
    "夜间",
    "天气",
    "气象",
    "光线",
    "照明",
    "照度",
    "潮湿",
    "位置",
    "井道",
    "路面",
    "场地",
    "周边",
    "作业面",
)

DIRECT_HUMAN_PATTERNS = (
    "未佩戴",
    "未正确佩戴",
    "无证上岗",
    "违规操作",
    "违章操作",
    "错误操作",
    "未观察",
    "未注意",
    "疏忽大意",
    "倒车",
    "行车",
    "冒险作业",
    "擅自作业",
)

ENVIRONMENT_STATE_PATTERNS = (
    "平台不稳",
    "地面不稳",
    "地面湿滑",
    "光线不足",
    "照明不足",
    "照度不足",
    "天气恶劣",
    "大风",
    "暴雨",
    "高温",
)

SUPERVISION_KEYWORDS = (
    "监管",
    "管理",
    "监督",
    "检查",
    "巡查",
    "审核",
    "督促",
    "发现",
    "排查",
    "交底",
    "培训",
    "教育",
    "责任",
    "职责",
    "制度",
    "方案",
    "预案",
    "资质",
    "许可",
)

MANAGEMENT_KEYWORDS = (
    "监管",
    "管理",
    "交底",
    "方案",
    "制度",
    "责任",
    "资质",
    "培训",
    "教育",
    "排查",
    "监督",
    "检查",
    "台账",
    "预案",
    "审批",
    "验收",
    "许可",
    "档案",
)

GENERIC_PHRASES = (
    "不规范",
    "缺失",
    "不到位",
    "不足",
    "安全",
    "管理",
    "监管",
    "教育",
    "培训",
    "作业",
)

GENERIC_PARENT_ANCHORS = (
    "行为",
    "缺失",
    "用品",
    "管理",
    "监管",
    "培训",
    "教育",
    "资质",
    "交底",
)

RESTRICTIVE_MODIFIERS = (
    "临边作业",
    "高处作业",
    "作业人员",
    "操作人员",
    "施工人员",
    "驾驶员",
    "倒车时",
    "行车时",
    "电缆",
    "线路",
    "设备",
    "现场",
    "随意拉接",
    "未及时",
)

CORE_REPLACEMENTS = (
    ("安全防护设施", "防护措施"),
    ("安全防护装置", "防护措施"),
    ("防护设施", "防护措施"),
    ("防护装置", "防护措施"),
    ("无防护设施", "无防护措施"),
    ("无防护装置", "无防护措施"),
    ("无防护", "无防护措施"),
)

SUBJECT_REPLACEMENTS = (
    ("企业主要负责人", "主要负责人"),
    ("企业负责人", "主要负责人"),
    ("安全管理员", "安全管理人员"),
    ("管理人员", "安全管理人员"),
    ("外来作业人员", "作业人员"),
    ("从业人员", "作业人员"),
    ("施工人员", "作业人员"),
    ("操作人员", "作业人员"),
    ("工人", "作业人员"),
    ("员工", "作业人员"),
)

SEMANTIC_REPLACEMENTS = (
    ("不到位", "缺失"),
    ("不足", "缺失"),
    ("管理义务", "管理职责"),
    ("管理责任", "管理职责"),
    ("履行安全管理义务", "履行安全管理职责"),
    ("履行安全管理责任", "履行安全管理职责"),
    ("安全生产意识", "安全意识"),
    ("安全生产教育培训", "安全教育培训"),
    ("安全生产教育", "安全教育"),
)


@dataclass(frozen=True)
class LLMConfig:
    model: str
    api_key: str
    base_url: str | None = None
    temperature: float = 0.1
    timeout: float = 120.0
    max_retries: int = 2


@dataclass
class TaxonomyNode:
    id: str
    text: str
    in_taxonomy: bool | None = None
    layer: str | None = None
    granularity_level: int | None = None
    confidence: float | None = None
    reason: str | None = None
    node_kind: str = "phrase"
    equivalence_signature: str | None = None
    decision_trace: dict[str, Any] = field(default_factory=dict)


def normalize_phrase_text(text: str) -> str:
    normalized = re.sub(r"\s+", "", text.strip())
    normalized = normalized.rstrip("，。；;,.!?？！")
    return normalized


def load_phrase_input(input_path: Path) -> dict[str, Any]:
    raw = json.loads(input_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        task_id = raw.get("task_id") or input_path.stem
        raw_phrases = raw.get("phrases") or []
    elif isinstance(raw, list):
        task_id = input_path.stem
        raw_phrases = raw
    else:
        raise ValueError("Input must be a JSON object or array.")

    seen: set[str] = set()
    phrases: list[dict[str, str]] = []
    next_index = 1
    for item in raw_phrases:
        if isinstance(item, str):
            phrase_text = normalize_phrase_text(item)
            phrase_id = f"p{next_index}"
        elif isinstance(item, dict):
            phrase_text = normalize_phrase_text(str(item.get("text", "")))
            phrase_id = str(item.get("id") or f"p{next_index}")
        else:
            continue

        if not phrase_text or phrase_text in seen:
            continue

        seen.add(phrase_text)
        phrases.append({"id": phrase_id, "text": phrase_text})
        next_index += 1

    return {"task_id": task_id, "phrases": phrases}


def is_incomplete_phrase(text: str) -> bool:
    normalized = normalize_phrase_text(text)
    if not normalized:
        return True
    if normalized in INCOMPLETE_FRAGMENTS:
        return True
    return any(normalized == prefix for prefix in MANAGEMENT_ACTION_PREFIXES)


def is_management_action_phrase(text: str) -> bool:
    normalized = normalize_phrase_text(text)
    return any(
        normalized.startswith(prefix) and any(token in normalized for token in MANAGEMENT_ACTION_OBJECTS)
        for prefix in MANAGEMENT_ACTION_PREFIXES
    )


def stage1_rule_classify(text: str) -> dict[str, Any]:
    normalized = normalize_phrase_text(text)
    if not normalized:
        return {
            "in_taxonomy": False,
            "decision_source": "rule",
            "reason": "空短语不能作为 taxonomy 节点。",
        }

    if is_incomplete_phrase(normalized):
        return {
            "in_taxonomy": False,
            "decision_source": "rule",
            "reason": "短语表达不完整，缺少关键宾语或限定信息，不能直接作为 taxonomy 节点。",
        }

    if is_management_action_phrase(normalized):
        return {
            "in_taxonomy": False,
            "decision_source": "rule",
            "reason": "短语更像责任明确、制度落实等管理动作，不作为事故原因 taxonomy 节点。",
        }

    if normalized.startswith(MEASURE_PREFIXES):
        return {
            "in_taxonomy": False,
            "decision_source": "rule",
            "reason": "短语更像整改、执法、治理或管理动作，默认不纳入原因 taxonomy。",
        }

    if normalized.startswith(NEGATION_PREFIXES) or any(keyword in normalized for keyword in CAUSE_KEYWORDS):
        return {
            "in_taxonomy": None,
            "decision_source": "llm",
            "reason": "短语带有致因特征，但需要模型判断是否可作为原因节点。",
        }

    return {
        "in_taxonomy": None,
        "decision_source": "llm",
        "reason": "规则无法可靠判定，交给模型判断。",
    }


def equivalence_signature(text: str) -> str:
    normalized = normalize_phrase_text(text)
    for source, target in SUBJECT_REPLACEMENTS:
        normalized = normalized.replace(source, target)
    for source, target in SEMANTIC_REPLACEMENTS:
        normalized = normalized.replace(source, target)
    normalized = normalized.replace("，", "").replace("、", "").replace("及", "和")
    normalized = normalized.replace("和", "")
    normalized = re.sub(r"[（）()：:]", "", normalized)
    return normalized


def guess_layer(text: str) -> tuple[str, str]:
    if any(pattern in text for pattern in ENVIRONMENT_STATE_PATTERNS) or any(keyword in text for keyword in ENVIRONMENT_KEYWORDS):
        return "环", "命中环境、天气、光线或场地状态关键词。"
    if any(keyword in text for keyword in SUPERVISION_KEYWORDS):
        return "管", "命中监督、管理或责任落实关键词。"
    if any(keyword in text for keyword in OBJECT_KEYWORDS):
        return "物", "命中设备、设施或构件关键词。"
    if any(pattern in text for pattern in DIRECT_HUMAN_PATTERNS) or any(keyword in text for keyword in HUMAN_KEYWORDS):
        return "人", "命中人的不安全行为关键词。"
    if any(keyword in text for keyword in MANAGEMENT_KEYWORDS):
        return "管", "命中管理、制度或监管关键词。"
    return "管", "未命中强特征关键词，启发式默认归入管理层面。"


def guess_granularity_level(text: str) -> tuple[int, str]:
    length = len(text)
    if any(keyword in text for keyword in ("缺失", "不足", "不到位", "淡薄")) and length <= 8:
        return 2, "短语较泛，表达为概括性缺失。"
    if any(keyword in text for keyword in ("防护用品", "教育培训", "管理", "监管", "交底", "方案")):
        return 3, "短语属于类目级原因。"
    if any(keyword in text for keyword in ("未佩戴", "未设置", "未开展", "无证", "上岗", "不规范", "失效")):
        return 4, "短语表达为较具体的违规或缺陷类型。"
    if length >= 8 or any(keyword in text for keyword in ("漏电", "短路", "混存混放", "破损", "错误", "老化")):
        return 5, "短语表达为具体状态或具体缺陷。"
    return 3, "缺少明显锚点，启发式默认给出中等粒度。"


def _char_bigrams(text: str) -> set[str]:
    if len(text) < 2:
        return {text} if text else set()
    return {text[i : i + 2] for i in range(len(text) - 1)}


def _candidate_score(child: TaxonomyNode, parent: TaxonomyNode) -> float:
    child_bigrams = _char_bigrams(child.text)
    parent_bigrams = _char_bigrams(parent.text)
    overlap = len(child_bigrams & parent_bigrams) / max(len(child_bigrams), 1)
    generality_bonus = 0.15 if (parent.granularity_level or 0) < (child.granularity_level or 0) else 0.05
    length_bonus = 0.1 if len(parent.text) <= len(child.text) + 4 else 0.0
    return overlap + generality_bonus + length_bonus


def _remove_generic_phrases(text: str) -> str:
    normalized = text
    for phrase in GENERIC_PHRASES:
        normalized = normalized.replace(phrase, "")
    return normalized


def _cause_core(text: str) -> str:
    normalized = text
    for source, target in CORE_REPLACEMENTS:
        normalized = normalized.replace(source, target)
    for modifier in RESTRICTIVE_MODIFIERS:
        normalized = normalized.replace(modifier, "")
    normalized = _remove_generic_phrases(normalized)
    normalized = normalized.replace("安全", "")
    normalized = re.sub(r"\s+", "", normalized)
    return normalized


def _context_markers(text: str) -> set[str]:
    markers: set[str] = set()
    for marker in RESTRICTIVE_MODIFIERS:
        if marker and marker in text:
            markers.add(marker)
    return markers


def _is_same_theme_peer(child: TaxonomyNode, candidate: TaxonomyNode) -> bool:
    child_core = _cause_core(child.text)
    candidate_core = _cause_core(candidate.text)
    if not child_core or child_core != candidate_core:
        return False
    child_context = _context_markers(child.text)
    candidate_context = _context_markers(candidate.text)
    if not child_context or not candidate_context:
        return False
    return child_context != candidate_context


def _is_context_specific_protection_peer(child: TaxonomyNode, candidate: TaxonomyNode) -> bool:
    if "防护" not in child.text or "防护" not in candidate.text:
        return False
    child_context = _context_markers(child.text)
    candidate_context = _context_markers(candidate.text)
    if not child_context or not candidate_context:
        return False
    return child_context != candidate_context


def _infer_core_label(text: str, layer: str | None = None) -> str | None:
    normalized = normalize_phrase_text(text)
    if layer == "物" and "防护" in normalized and any(
        token in normalized for token in ("无防护", "防护设施", "防护装置", "防护栏杆", "防护措施")
    ):
        return "防护措施缺失"
    if layer == "环" and any(token in normalized for token in ("照明不足", "照度不足", "光线不足")):
        return "照明条件不足"
    if layer == "人" and any(token in normalized for token in ("未佩戴", "未正确佩戴")) and any(
        token in normalized for token in ("安全带", "安全帽", "防护用品", "劳动防护用品", "防坠")
    ):
        return "未佩戴防护用品"
    if layer == "管" and any(token in normalized for token in ("职责落实不到位", "责任落实不到位", "责任不落实", "监管职责未落实")):
        return "责任落实不到位"
    if layer == "管" and ("未履行" in normalized and "职责" in normalized):
        return "职责履行不到位"
    if layer == "管" and any(token in normalized for token in ("培训不足", "培训不到位", "教育培训缺失", "未经培训", "未开展安全教育培训")):
        return "安全培训缺失"
    if layer == "管" and any(token in normalized for token in ("制度", "规程", "规定", "管理制度", "管理缺失")):
        return "制度问题"
    return None


def rank_parent_candidates(
    child: TaxonomyNode,
    candidates: list[TaxonomyNode],
    max_candidates: int = 5,
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate.id == child.id:
            continue
        if candidate.layer != child.layer:
            continue
        if candidate.granularity_level is None or child.granularity_level is None:
            continue
        if candidate.granularity_level > child.granularity_level:
            continue
        if candidate.text == child.text:
            continue
        if candidate.equivalence_signature and child.equivalence_signature:
            if candidate.equivalence_signature == child.equivalence_signature:
                continue
        if child.text in candidate.text and len(candidate.text) > len(child.text):
            continue

        stripped_child = _remove_generic_phrases(child.text)
        stripped_parent = _remove_generic_phrases(candidate.text)
        if _is_same_theme_peer(child, candidate):
            if (candidate.granularity_level or 99) >= (child.granularity_level or 99):
                continue
        if _is_context_specific_protection_peer(child, candidate):
            if (candidate.granularity_level or 99) >= (child.granularity_level or 99):
                continue
        specific_overlap = len(_char_bigrams(stripped_child) & _char_bigrams(stripped_parent))
        is_generic_anchor = any(anchor in candidate.text for anchor in GENERIC_PARENT_ANCHORS)
        if specific_overlap == 0 and not is_generic_anchor:
            continue

        score = _candidate_score(child, candidate)
        if score <= 0:
            continue
        ranked.append(
            {
                "parent_id": candidate.id,
                "parent_text": candidate.text,
                "score": round(score, 4),
                "reason": "同层面且粒度更泛，文本具备一定语义重叠。",
            }
        )

    ranked.sort(key=lambda item: (-item["score"], len(item["parent_text"]), item["parent_text"]))
    return ranked[:max_candidates]


def build_equivalence_groups(nodes: list[TaxonomyNode]) -> tuple[list[TaxonomyNode], dict[str, str]]:
    buckets: dict[tuple[str | None, str], list[TaxonomyNode]] = {}
    for node in nodes:
        if not node.in_taxonomy:
            continue
        signature = equivalence_signature(node.text)
        node.equivalence_signature = signature
        key = (node.layer, signature)
        buckets.setdefault(key, []).append(node)

    group_nodes: list[TaxonomyNode] = []
    member_to_group: dict[str, str] = {}
    next_index = 1
    for (_, signature), members in buckets.items():
        unique_texts = {member.text for member in members}
        if len(unique_texts) < 2:
            continue

        group_id = f"eq{next_index}"
        next_index += 1
        group_node = TaxonomyNode(
            id=group_id,
            text=f"归并节点：{signature}",
            in_taxonomy=True,
            layer=members[0].layer,
            granularity_level=min(member.granularity_level or 99 for member in members),
            confidence=1.0,
            reason="同义改写或主语替换归并节点。",
            node_kind="group",
            equivalence_signature=signature,
            decision_trace={
                "equivalence_group": {
                    "members": [member.id for member in sorted(members, key=lambda item: item.text)],
                    "signature": signature,
                }
            },
        )
        group_nodes.append(group_node)
        for member in members:
            member_to_group[member.id] = group_id

    return group_nodes, member_to_group


def build_core_nodes(
    phrase_nodes: list[TaxonomyNode],
    group_nodes: list[TaxonomyNode],
    member_to_group: dict[str, str],
) -> tuple[list[TaxonomyNode], dict[str, str]]:
    attach_node_by_id = {node.id: node for node in [*phrase_nodes, *group_nodes]}
    buckets: dict[str, dict[str, Any]] = {}

    for node in phrase_nodes:
        if not node.in_taxonomy:
            continue
        core_label = _infer_core_label(node.text, node.layer)
        if not core_label:
            continue
        attach_target_id = member_to_group.get(node.id, node.id)
        bucket = buckets.setdefault(
            core_label,
            {"layer": node.layer, "target_members": {}, "ambiguous": False},
        )
        if bucket["layer"] != node.layer:
            bucket["ambiguous"] = True
        bucket["target_members"].setdefault(attach_target_id, []).append(node.id)

    core_nodes: list[TaxonomyNode] = []
    target_to_core: dict[str, str] = {}
    next_index = 1

    for core_label, bucket in buckets.items():
        if bucket["ambiguous"]:
            continue
        layer = bucket["layer"]
        target_members = bucket["target_members"]
        if len(target_members) < 2:
            continue

        core_id = f"core{next_index}"
        next_index += 1
        granularity = min((attach_node_by_id[target_id].granularity_level or 99) for target_id in target_members)
        core_node = TaxonomyNode(
            id=core_id,
            text=core_label,
            in_taxonomy=True,
            layer=layer,
            granularity_level=max(2, granularity - 1),
            confidence=1.0,
            reason="从多个场景化短语中抽象出的核心表达节点。",
            node_kind="core",
            decision_trace={
                "core_abstraction": {
                    "members": {target_id: sorted(member_ids) for target_id, member_ids in sorted(target_members.items())},
                    "label": core_label,
                }
            },
        )
        core_nodes.append(core_node)
        for target_id in target_members:
            target_to_core[target_id] = core_id

    return core_nodes, target_to_core


def build_compression_audit(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parent_by_child = {edge["child_id"]: edge["parent_id"] for edge in edges}
    node_by_id = {node["id"]: node for node in nodes}
    audit_rows: list[dict[str, Any]] = []

    for node in nodes:
        if not node.get("stage1_in_taxonomy"):
            continue
        if node.get("node_kind") != "phrase":
            continue

        current = node["id"]
        seen: set[str] = set()
        group_id: str | None = None
        group_text: str | None = None
        core_id: str | None = None
        core_text: str | None = None
        visible_parent_id: str | None = None
        visible_parent_text: str | None = None

        while current in parent_by_child and current not in seen:
            seen.add(current)
            parent_id = parent_by_child[current]
            parent_node = node_by_id.get(parent_id)
            if parent_node is None:
                break
            if parent_node.get("node_kind") == "group" and group_id is None:
                group_id = parent_id
                group_text = parent_node.get("text")
            if parent_node.get("node_kind") == "core" and core_id is None:
                core_id = parent_id
                core_text = parent_node.get("text")
            if parent_node.get("node_kind") != "group" and visible_parent_id is None:
                visible_parent_id = parent_id
                visible_parent_text = parent_node.get("text")
            current = parent_id

        audit_rows.append(
            {
                "phrase_id": node["id"],
                "original_text": node["text"],
                "group_id": group_id,
                "group_text": group_text,
                "core_id": core_id,
                "core_text": core_text,
                "visible_parent_id": visible_parent_id,
                "visible_parent_text": visible_parent_text,
            }
        )

    audit_rows.sort(key=lambda item: (item["original_text"], item["phrase_id"]))
    return audit_rows


def build_compact_rows(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parent_by_child = {edge["child_id"]: edge["parent_id"] for edge in edges}
    node_by_id = {node["id"]: node for node in nodes}

    def resolve_visible_parent(node_id: str) -> str | None:
        current = parent_by_child.get(node_id)
        seen: set[str] = set()
        while current is not None and current not in seen:
            seen.add(current)
            parent_node = node_by_id.get(current)
            if parent_node is None:
                return None
            if parent_node.get("node_kind") != "group":
                return current
            current = parent_by_child.get(current)
        return None

    compact_rows: list[dict[str, Any]] = []
    for node in nodes:
        if not node.get("stage1_in_taxonomy"):
            continue
        if node.get("node_kind") == "group":
            continue

        parent_id = resolve_visible_parent(node["id"])
        parent_text = node_by_id[parent_id]["text"] if parent_id and parent_id in node_by_id else None
        compact_rows.append(
            {
                "id": node["id"],
                "text": node["text"],
                "parent_id": parent_id,
                "parent_text": parent_text,
                "layer": node.get("stage2_layer"),
                "granularity_level": node.get("stage3_granularity_level"),
                "is_root": parent_id is None,
                "node_kind": node.get("node_kind", "phrase"),
            }
        )

    compact_rows.sort(
        key=lambda item: (
            item["layer"] or "",
            0 if item["is_root"] else 1,
            item["parent_text"] or "",
            item["granularity_level"] or 99,
            item["text"],
        )
    )
    return compact_rows


def compress_taxonomy_depth(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    max_depth: int = 6,
) -> list[dict[str, Any]]:
    if max_depth < 2:
        raise ValueError("max_depth must be at least 2")

    node_by_id = {node["id"]: node for node in nodes if node.get("stage1_in_taxonomy")}
    compressed_edges = [dict(edge) for edge in edges]

    def _parent_map() -> dict[str, str]:
        return {
            edge["child_id"]: edge["parent_id"]
            for edge in compressed_edges
            if edge["child_id"] in node_by_id and edge["parent_id"] in node_by_id
        }

    def _depth(node_id: str, parent_by_child: dict[str, str]) -> int:
        depth = 1
        current = node_id
        seen: set[str] = set()
        while current in parent_by_child and current not in seen:
            seen.add(current)
            current = parent_by_child[current]
            depth += 1
        return depth

    while True:
        parent_by_child = _parent_map()
        if not parent_by_child:
            return compressed_edges

        deepest_id = max(node_by_id, key=lambda item: _depth(item, parent_by_child))
        deepest_depth = _depth(deepest_id, parent_by_child)
        if deepest_depth <= max_depth:
            return compressed_edges

        chain = [deepest_id]
        current = deepest_id
        seen: set[str] = set()
        while current in parent_by_child and current not in seen:
            seen.add(current)
            current = parent_by_child[current]
            chain.append(current)

        root_to_leaf = list(reversed(chain))
        candidate_id: str | None = None

        for node_id in root_to_leaf[2:-1]:
            if node_by_id.get(node_id, {}).get("node_kind") == "group":
                candidate_id = node_id
                break

        if candidate_id is None:
            for node_id in root_to_leaf[2:-1]:
                candidate_id = node_id
                break

        if candidate_id is None:
            return compressed_edges

        current_parent = parent_by_child.get(candidate_id)
        if current_parent is None:
            return compressed_edges
        new_parent = parent_by_child.get(current_parent)
        if new_parent is None:
            return compressed_edges

        for edge in compressed_edges:
            if edge["child_id"] == candidate_id and edge["parent_id"] == current_parent:
                edge["parent_id"] = new_parent
                edge["reason"] = f'{edge.get("reason", "").rstrip()} 压缩层级时上提到更高层父节点。'.strip()
                break


def _mermaid_safe(text: str) -> str:
    return text.replace('"', "'")


def build_mermaid_taxonomy(compact_rows: list[dict[str, Any]]) -> str:
    lines = ["flowchart TD"]
    for row in compact_rows:
        label = f"{_mermaid_safe(row['text'])}\\n[{row['layer'] or '?'} | G{row['granularity_level'] or '?'}]"
        if row.get("node_kind") == "group":
            lines.append(f'    {row["id"]}{{"{label}"}}')
        else:
            lines.append(f'    {row["id"]}["{label}"]')

    for row in compact_rows:
        if row["parent_id"]:
            lines.append(f'    {row["parent_id"]} --> {row["id"]}')

    return "\n".join(lines) + "\n"


def build_markdown_taxonomy(compact_rows: list[dict[str, Any]], mermaid_text: str, task_id: str) -> str:
    lines = [
        "# Phrase Taxonomy",
        "",
        f"- task_id: `{task_id}`",
        f"- positive_nodes: `{len(compact_rows)}`",
        "",
        "## Compact Structure",
        "| id | text | parent_text | layer | granularity_level | is_root | node_kind |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]

    for row in compact_rows:
        lines.append(
            "| {id} | {text} | {parent_text} | {layer} | {granularity} | {is_root} | {node_kind} |".format(
                id=row["id"],
                text=str(row["text"]).replace("|", "\\|"),
                parent_text=str(row["parent_text"] or "").replace("|", "\\|"),
                layer=row["layer"] or "",
                granularity=row["granularity_level"] or "",
                is_root=str(row["is_root"]).lower(),
                node_kind=row.get("node_kind", "phrase"),
            )
        )

    lines.extend(["", "## Mermaid", "```mermaid", mermaid_text.rstrip(), "```", ""])
    return "\n".join(lines)


def resolve_cycle_groups(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    parent_by_child = {edge["child_id"]: edge["parent_id"] for edge in edges}
    node_by_id = {node["id"]: node for node in nodes}

    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    components: list[list[str]] = []

    def strongconnect(node_id: str) -> None:
        nonlocal index
        indices[node_id] = index
        lowlink[node_id] = index
        index += 1
        stack.append(node_id)
        on_stack.add(node_id)

        parent_id = parent_by_child.get(node_id)
        if parent_id is not None and parent_id in node_by_id:
            if parent_id not in indices:
                strongconnect(parent_id)
                lowlink[node_id] = min(lowlink[node_id], lowlink[parent_id])
            elif parent_id in on_stack:
                lowlink[node_id] = min(lowlink[node_id], indices[parent_id])

        if lowlink[node_id] == indices[node_id]:
            component: list[str] = []
            while True:
                current = stack.pop()
                on_stack.remove(current)
                component.append(current)
                if current == node_id:
                    break
            if len(component) > 1:
                components.append(component)

    for node_id in node_by_id:
        if node_id not in indices:
            strongconnect(node_id)

    if not components:
        return nodes, edges

    component_lookup = {member: index for index, component in enumerate(components) for member in component}
    updated_nodes = list(nodes)
    updated_edges: list[dict[str, Any]] = []

    for edge in edges:
        child_component = component_lookup.get(edge["child_id"])
        parent_component = component_lookup.get(edge["parent_id"])
        if child_component is not None and child_component == parent_component:
            continue
        updated_edges.append(edge)

    next_index = 1
    while any(node["id"] == f"cg{next_index}" for node in updated_nodes):
        next_index += 1

    for component in components:
        component_nodes = [node_by_id[node_id] for node_id in component]
        signature_candidates = sorted(
            {
                equivalence_signature(node["text"])
                for node in component_nodes
                if node.get("stage1_in_taxonomy")
            },
            key=len,
        )
        label = signature_candidates[0] if signature_candidates else sorted(node["text"] for node in component_nodes)[0]
        group_id = f"cg{next_index}"
        next_index += 1
        updated_nodes.append(
            {
                "id": group_id,
                "text": f"归并节点：{label}",
                "stage1_in_taxonomy": True,
                "stage2_layer": component_nodes[0].get("stage2_layer"),
                "stage3_granularity_level": min(
                    node.get("stage3_granularity_level") or 99 for node in component_nodes
                ),
                "confidence": 1.0,
                "reason": "互挂或环形结构归并为同义父节点。",
                "node_kind": "group",
                "decision_trace": {
                    "cycle_group": {
                        "members": sorted(component, key=lambda item: node_by_id[item]["text"]),
                    }
                },
            }
        )
        for member in component:
            updated_edges.append(
                {
                    "child_id": member,
                    "parent_id": group_id,
                    "relation": "equivalent_variant_of",
                    "reason": "互挂或环形结构归并为同义父节点。",
                }
            )

    return updated_nodes, updated_edges


def _chat_completion(
    *,
    messages: list[dict[str, str]],
    llm_config: LLMConfig,
) -> str:
    import time

    import httpx

    base_url = (llm_config.base_url or "https://api.openai.com").rstrip("/")
    url = f"{base_url}/v1/chat/completions"
    payload = {
        "model": llm_config.model,
        "messages": messages,
        "temperature": llm_config.temperature,
    }
    headers = {
        "Authorization": f"Bearer {llm_config.api_key}",
        "Content-Type": "application/json",
    }

    last_exc = None
    for attempt in range(llm_config.max_retries + 1):
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=llm_config.timeout)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            last_exc = exc
            if attempt < llm_config.max_retries:
                time.sleep(min(2**attempt, 8))
    raise RuntimeError(f"LLM request failed after {llm_config.max_retries + 1} attempts: {last_exc}")


def _clean_json_block(text: str) -> str:
    block = text.strip()
    if "```json" in block:
        block = block.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in block:
        block = block.split("```", 1)[1].split("```", 1)[0].strip()
    return block


def _extract_json_payload(text: str) -> Any:
    cleaned = _clean_json_block(text)
    return json.loads(cleaned)


def _resolve_llm_config(args: argparse.Namespace) -> LLMConfig | None:
    model = args.model or os.getenv("OPENAI_MODEL") or os.getenv("ACCIDENT_NLP_LLM_MODEL")
    api_key = args.api_key or os.getenv("OPENAI_API_KEY") or os.getenv("ACCIDENT_NLP_LLM_API_KEY")
    base_url = args.base_url or os.getenv("OPENAI_BASE_URL") or os.getenv("ACCIDENT_NLP_LLM_BASE_URL")
    if not model or not api_key:
        return None
    return LLMConfig(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=args.temperature,
        timeout=args.timeout,
        max_retries=args.max_retries,
    )


def _load_benchmark_examples(limit: int = 4) -> dict[str, list[dict[str, Any]]]:
    benchmark_path = Path("data") / "taxonomy_phrases_benchmark.cleaned.jsonl"
    examples = {"stage1": [], "stage23": []}
    if not benchmark_path.is_file():
        return examples

    for line in benchmark_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        label = json.loads(row["completion"])
        phrase = row["prompt"].split("是taxonomy里的元素吗", 1)[0].strip()

        if len(examples["stage1"]) < limit:
            examples["stage1"].append({"text": phrase, "in_taxonomy": label["in_taxonomy"]})
        if label["in_taxonomy"] and len(examples["stage23"]) < limit:
            examples["stage23"].append(
                {
                    "text": phrase,
                    "layer": label["layer"],
                    "granularity_level": label["score"],
                }
            )
        if all(len(bucket) >= limit for bucket in examples.values()):
            break
    return examples


def _stage1_llm_classify(
    unresolved_nodes: list[TaxonomyNode],
    llm_config: LLMConfig,
    examples: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    prompt = (
        "你在做事故原因 taxonomy 预分类。只判断一个短语是否适合成为原因树节点。"
        "整改措施、监管建议、宣传教育动作、处罚动作、会议动作、泛化治理动作通常不属于 taxonomy 节点。"
        "请返回 JSON array，每一项包含 id, in_taxonomy, reason。\n\n"
        f"few-shot examples:\n{json.dumps(examples, ensure_ascii=False)}\n\n"
        f"items:\n{json.dumps([{'id': node.id, 'text': node.text} for node in unresolved_nodes], ensure_ascii=False)}"
    )
    raw_text = _chat_completion(messages=[{"role": "user", "content": prompt}], llm_config=llm_config)
    payload = _extract_json_payload(raw_text)
    return {item["id"]: item for item in payload}


def _stage23_llm_classify(
    nodes: list[TaxonomyNode],
    llm_config: LLMConfig,
    examples: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    prompt = (
        "你在做事故原因 taxonomy 的层面分类和粒度分级。"
        "layer 只能是 人/物/环/管。granularity_level 取 2/3/4/5，值越高代表越具体。"
        "请返回 JSON array，每一项包含 id, layer, granularity_level, reason。\n\n"
        f"few-shot examples:\n{json.dumps(examples, ensure_ascii=False)}\n\n"
        f"items:\n{json.dumps([{'id': node.id, 'text': node.text} for node in nodes], ensure_ascii=False)}"
    )
    raw_text = _chat_completion(messages=[{"role": "user", "content": prompt}], llm_config=llm_config)
    payload = _extract_json_payload(raw_text)
    return {item["id"]: item for item in payload}


def _stage4_llm_pick_parent(
    child: TaxonomyNode,
    candidate_payload: list[dict[str, Any]],
    llm_config: LLMConfig,
) -> dict[str, Any]:
    prompt = (
        "你在为事故原因 taxonomy 选择直接父节点。"
        "只能在候选列表中选择最合适的直接上位概念；如果没有合适父节点，返回 null。"
        "请返回 JSON object，包含 parent_id, parent_text, reason。\n\n"
        f"child:\n{json.dumps({'id': child.id, 'text': child.text, 'layer': child.layer, 'granularity_level': child.granularity_level}, ensure_ascii=False)}\n\n"
        f"candidates:\n{json.dumps(candidate_payload, ensure_ascii=False)}"
    )
    raw_text = _chat_completion(messages=[{"role": "user", "content": prompt}], llm_config=llm_config)
    return _extract_json_payload(raw_text)


def run_taxonomy_pipeline(
    *,
    input_path: Path,
    output_path: Path,
    llm_config: LLMConfig | None = None,
    max_parent_candidates: int = 5,
    max_taxonomy_depth: int = 6,
) -> dict[str, Any]:
    payload = load_phrase_input(input_path)
    nodes = [TaxonomyNode(id=item["id"], text=item["text"]) for item in payload["phrases"]]
    examples = _load_benchmark_examples()

    unresolved_stage1: list[TaxonomyNode] = []
    for node in nodes:
        decision = stage1_rule_classify(node.text)
        node.decision_trace["stage1"] = decision
        if decision["in_taxonomy"] is None:
            unresolved_stage1.append(node)
        else:
            node.in_taxonomy = decision["in_taxonomy"]
            node.confidence = 1.0
            node.reason = decision["reason"]

    if unresolved_stage1 and llm_config is not None:
        llm_stage1 = _stage1_llm_classify(unresolved_stage1, llm_config, examples["stage1"])
        for node in unresolved_stage1:
            result = llm_stage1.get(node.id)
            if result is None:
                node.in_taxonomy = False
                node.reason = "LLM 未返回结果，保守排除。"
                node.confidence = 0.0
                continue
            node.in_taxonomy = bool(result["in_taxonomy"])
            node.reason = result.get("reason", "")
            node.confidence = 0.75
            node.decision_trace["stage1"]["decision_source"] = "llm"
    else:
        for node in unresolved_stage1:
            node.in_taxonomy = any(keyword in node.text for keyword in CAUSE_KEYWORDS)
            node.reason = "未配置 LLM，按启发式规则给出阶段 1 结果。"
            node.confidence = 0.55
            node.decision_trace["stage1"]["decision_source"] = "heuristic"

    positive_nodes = [node for node in nodes if node.in_taxonomy]
    if llm_config is not None and positive_nodes:
        llm_stage23 = _stage23_llm_classify(positive_nodes, llm_config, examples["stage23"])
        for node in positive_nodes:
            result = llm_stage23.get(node.id)
            if result is None:
                layer, layer_reason = guess_layer(node.text)
                granularity, granularity_reason = guess_granularity_level(node.text)
                node.layer = layer
                node.granularity_level = granularity
                node.decision_trace["stage23"] = {
                    "decision_source": "heuristic",
                    "reason": f"{layer_reason} {granularity_reason}",
                }
                continue
            node.layer = result["layer"]
            node.granularity_level = int(result["granularity_level"])
            node.decision_trace["stage23"] = {
                "decision_source": "llm",
                "reason": result.get("reason", ""),
            }
    else:
        for node in positive_nodes:
            layer, layer_reason = guess_layer(node.text)
            granularity, granularity_reason = guess_granularity_level(node.text)
            node.layer = layer
            node.granularity_level = granularity
            node.decision_trace["stage23"] = {
                "decision_source": "heuristic",
                "reason": f"{layer_reason} {granularity_reason}",
            }

    group_nodes, member_to_group = build_equivalence_groups(positive_nodes)
    core_nodes, target_to_core = build_core_nodes(positive_nodes, group_nodes, member_to_group)
    edges: list[dict[str, Any]] = []
    orphans: list[dict[str, Any]] = []

    for member in positive_nodes:
        group_id = member_to_group.get(member.id)
        if group_id is None:
            continue
        group_node = next(node for node in group_nodes if node.id == group_id)
        member.decision_trace["stage4_fixed_parent"] = {
            "parent_id": group_id,
            "parent_text": group_node.text,
            "reason": "同义改写或主语替换，挂到归并父节点。",
        }
        edges.append(
            {
                "child_id": member.id,
                "parent_id": group_id,
                "relation": "equivalent_variant_of",
                "reason": "同义改写或主语替换，挂到归并父节点。",
            }
        )

    for target_id, core_id in target_to_core.items():
        target_node = next(node for node in [*positive_nodes, *group_nodes] if node.id == target_id)
        target_node.decision_trace["stage4_core_parent"] = {
            "parent_id": core_id,
            "parent_text": next(node for node in core_nodes if node.id == core_id).text,
            "reason": "根据共享核心表达抽象为正式上位节点。",
        }
        edges.append(
            {
                "child_id": target_id,
                "parent_id": core_id,
                "relation": "is_context_specific_variant_of",
                "reason": "根据共享核心表达抽象为正式上位节点。",
            }
        )

    group_node_ids = {node.id for node in group_nodes}
    direct_core_children = {target_id for target_id in target_to_core if target_id not in group_node_ids}
    grouped_core_children = {target_id for target_id in target_to_core if target_id in group_node_ids}

    linkable_nodes = (
        [node for node in positive_nodes if node.id not in member_to_group and node.id not in direct_core_children]
        + [node for node in group_nodes if node.id not in grouped_core_children]
        + core_nodes
    )

    for child in linkable_nodes:
        candidate_payload = rank_parent_candidates(child, linkable_nodes, max_candidates=max_parent_candidates)
        child.decision_trace["stage4_candidates"] = candidate_payload

        if not candidate_payload:
            orphans.append({"id": child.id, "text": child.text, "reason": "没有候选父节点。"})
            continue

        if llm_config is not None:
            selection = _stage4_llm_pick_parent(child, candidate_payload, llm_config)
        else:
            selection = candidate_payload[0]
            selection["reason"] = "未配置 LLM，按启发式排序选择首个候选。"

        parent_id = selection.get("parent_id")
        if parent_id is None:
            orphans.append({"id": child.id, "text": child.text, "reason": selection.get("reason", "未找到合适父节点。")})
            continue

        edges.append(
            {
                "child_id": child.id,
                "parent_id": parent_id,
                "relation": "is_a_more_specific_cause_of",
                "reason": selection.get("reason", ""),
            }
        )

    output_nodes = [
        {
            "id": node.id,
            "text": node.text,
            "stage1_in_taxonomy": node.in_taxonomy,
            "stage2_layer": node.layer,
            "stage3_granularity_level": node.granularity_level,
            "confidence": node.confidence,
            "reason": node.reason,
            "node_kind": node.node_kind,
            "decision_trace": node.decision_trace,
        }
        for node in [*nodes, *group_nodes, *core_nodes]
    ]
    output_nodes, edges = resolve_cycle_groups(output_nodes, edges)
    edges = compress_taxonomy_depth(output_nodes, edges, max_depth=max_taxonomy_depth)

    result = {
        "task_id": payload["task_id"],
        "input_path": str(input_path),
        "llm_enabled": llm_config is not None,
        "nodes": output_nodes,
        "edges": edges,
        "orphans": orphans,
    }
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    compact_rows = build_compact_rows(result["nodes"], result["edges"])
    compression_audit = build_compression_audit(result["nodes"], result["edges"])
    compact_path = output_path.with_suffix(".compact.json")
    compression_path = output_path.with_suffix(".compression.json")
    mermaid_path = output_path.with_suffix(".mmd")
    markdown_path = output_path.with_suffix(".taxonomy.md")

    compact_path.write_text(json.dumps(compact_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    compression_path.write_text(json.dumps(compression_audit, ensure_ascii=False, indent=2), encoding="utf-8")
    mermaid_text = build_mermaid_taxonomy(compact_rows)
    mermaid_path.write_text(mermaid_text, encoding="utf-8")
    markdown_path.write_text(
        build_markdown_taxonomy(compact_rows, mermaid_text, payload["task_id"]),
        encoding="utf-8",
    )

    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a four-stage taxonomy draft from a phrase set.")
    parser.add_argument("--input", required=True, help="Path to the phrase-set JSON input.")
    parser.add_argument("--output", required=True, help="Path to the taxonomy result JSON output.")
    parser.add_argument("--model", help="Optional model name. Falls back to OPENAI_MODEL.")
    parser.add_argument("--api-key", help="Optional API key. Falls back to OPENAI_API_KEY.")
    parser.add_argument("--base-url", help="Optional OpenAI-compatible base URL.")
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--max-parent-candidates", type=int, default=5)
    parser.add_argument("--max-taxonomy-depth", type=int, default=6)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    llm_config = _resolve_llm_config(args)
    result = run_taxonomy_pipeline(
        input_path=Path(args.input),
        output_path=Path(args.output),
        llm_config=llm_config,
        max_parent_candidates=args.max_parent_candidates,
        max_taxonomy_depth=args.max_taxonomy_depth,
    )
    print(
        json.dumps(
            {
                "task_id": result["task_id"],
                "output": args.output,
                "llm_enabled": result["llm_enabled"],
                "nodes": len(result["nodes"]),
                "edges": len(result["edges"]),
                "orphans": len(result["orphans"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
