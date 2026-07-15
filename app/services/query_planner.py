from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Sequence

from app.models.project import Project


_PROJECT_ALIASES = {
    "agentproject": ("智能硬件客服", "可治理agent", "agentproject"),
    "farino": ("法奥", "farino", "aiflowy"),
    "myagent": ("个人招聘", "招聘知识agent", "myagent", "本站"),
    "mood_tracker": ("情绪分析", "情绪日记", "心情助手", "moodtracker"),
}

_DOMAIN_QUERIES = {
    "项目": ("项目", "作品"),
    "实习经历": ("实习", "工作经历", "校企合作"),
    "技能": ("技能", "技术能力", "技术栈"),
    "教育背景": ("教育", "学校", "专业", "学历"),
    "优势": ("优势", "优点", "强项"),
    "不足": ("不足", "缺点", "短板", "边界"),
    "岗位匹配": ("岗位匹配", "为什么适合", "胜任"),
}


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.lower())


@dataclass(frozen=True)
class QueryTarget:
    query: str
    coverage_key: str
    project_slug: str | None = None
    section_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class QueryPlan:
    intent: Literal["project_list", "multi_project", "multi_part", "single_project", "general"]
    targets: list[QueryTarget] = field(default_factory=list)
    expected_coverage: list[str] = field(default_factory=list)
    context_limit: int = 5

    @property
    def requires_complete_coverage(self) -> bool:
        return self.intent in {"project_list", "multi_project", "multi_part"}


def _mentioned_projects(question: str, projects: Sequence[Project]) -> list[Project]:
    normalized = _normalize(question)
    mentioned: list[Project] = []
    for project in projects:
        aliases = (_normalize(project.title), project.slug, *_PROJECT_ALIASES.get(project.slug, ()))
        if any(_normalize(alias) in normalized for alias in aliases):
            mentioned.append(project)
    return mentioned


def _project_fields(question: str) -> list[tuple[str, str, tuple[str, ...]]]:
    fields: list[tuple[str, str, tuple[str, ...]]] = []
    field_patterns = (
        ("项目背景", "项目背景 场景 项目描述", ("项目背景", "项目描述", "项目简介"), r"背景|场景|解决什么|做什么"),
        ("个人职责", "个人职责 负责 贡献 角色", ("个人贡献", "个人职责", "职责", "负责"), r"职责|负责|贡献|角色|主导"),
        ("技术方案", "技术栈 架构 技术方案 实现", ("技术栈", "技术方案", "架构", "系统组成"), r"技术|技术栈|架构|实现|方案"),
        ("结果与产出", "结果 成果 产出 效果", ("结果", "成果", "产出", "项目价值"), r"结果|成果|产出|效果"),
        ("局限与边界", "局限 不足 边界", ("局限", "不足", "边界"), r"局限|不足|边界|问题"),
    )
    for label, query_terms, section_terms, pattern in field_patterns:
        if re.search(pattern, question, re.IGNORECASE):
            fields.append((label, query_terms, section_terms))
    return fields or [
        ("项目背景", "项目背景 场景 项目描述", ("项目背景", "项目描述", "项目简介")),
        ("个人职责", "个人职责 负责 贡献 角色", ("个人贡献", "个人职责", "职责", "负责")),
        ("技术方案", "技术栈 架构 技术方案 实现", ("技术栈", "技术方案", "架构", "系统组成")),
        ("结果与产出", "结果 成果 产出 效果", ("结果", "成果", "产出", "项目价值")),
    ]


def _split_complex_clauses(question: str) -> list[str]:
    if not re.search(r"[；;]|并且|以及|同时|另外|还要|再说明|再介绍", question):
        return []
    parts = re.split(r"[；;]|并且|以及|同时|另外|还要|再说明|再介绍", question)
    cleaned: list[str] = []
    for part in parts:
        value = re.sub(r"^(请|并|再|还|分别)", "", part.strip(" ，。！？?"))
        if len(value) >= 3 and value not in cleaned:
            cleaned.append(value)
    return cleaned if len(cleaned) >= 2 else []


def plan_question(question: str, projects: Sequence[Project]) -> QueryPlan:
    q = question.lower()
    mentioned = _mentioned_projects(question, projects)
    has_project_word = bool(re.search(r"项目|作品|project", q, re.IGNORECASE))
    list_request = bool(re.search(
        r"列出|罗列|清单|名称|哪些|哪几个|多少|都有什么|做过什么|做过哪些",
        q,
    ))
    all_projects = bool(re.search(
        r"(?:所有|全部|各个|每个|四个|几个).{0,4}项目|项目.{0,4}(?:分别|每个|各个|全部|所有)",
        q,
    ))
    detail_request = bool(re.search(r"介绍|详细|背景|职责|负责|贡献|技术|架构|成果|结果|对比|比较|区别", q))

    if has_project_word and list_request and not detail_request:
        return QueryPlan(intent="project_list", context_limit=max(5, len(projects)))

    selected_projects: list[Project] = []
    if has_project_word and all_projects:
        selected_projects = list(projects)
    elif len(mentioned) >= 2:
        selected_projects = mentioned

    if selected_projects:
        fields = _project_fields(question)
        targets = [
            QueryTarget(
                query=f"{project.title}：{query_terms}",
                coverage_key=f"{project.title}/{field_label}",
                project_slug=project.slug,
                section_terms=section_terms,
            )
            for project in selected_projects
            for field_label, query_terms, section_terms in fields
        ]
        return QueryPlan(
            intent="multi_project",
            targets=targets,
            expected_coverage=[target.coverage_key for target in targets],
            context_limit=min(16, max(6, len(targets))),
        )

    if len(mentioned) == 1:
        project = mentioned[0]
        fields = _project_fields(question)
        targets = [
            QueryTarget(
                query=f"{project.title}：{query_terms}",
                coverage_key=f"{project.title}/{field_label}",
                project_slug=project.slug,
                section_terms=section_terms,
            )
            for field_label, query_terms, section_terms in fields
        ]
        return QueryPlan(
            intent="single_project",
            targets=targets,
            expected_coverage=[target.coverage_key for target in targets],
            context_limit=min(8, max(5, len(targets) * 2)),
        )

    domains = [
        label
        for label, aliases in _DOMAIN_QUERIES.items()
        if any(alias in q for alias in aliases)
    ]
    if len(domains) >= 2:
        targets = [
            QueryTarget(query=f"朱旭的{domain}", coverage_key=domain)
            for domain in domains
        ]
        return QueryPlan(
            intent="multi_part",
            targets=targets,
            expected_coverage=domains,
            context_limit=min(10, max(6, len(domains) * 2)),
        )

    clauses = _split_complex_clauses(question)
    if clauses:
        targets = [
            QueryTarget(query=clause, coverage_key=clause)
            for clause in clauses
        ]
        return QueryPlan(
            intent="multi_part",
            targets=targets,
            expected_coverage=clauses,
            context_limit=min(10, max(6, len(clauses) * 2)),
        )

    return QueryPlan(
        intent="general",
        targets=[QueryTarget(question, "general")],
        context_limit=5,
    )
