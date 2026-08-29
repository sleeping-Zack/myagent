from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Sequence

from app.models.project import Project


_STRONG_PROJECT_ALIASES = {
    "agentproject": (
        "智能硬件客服",
        "可治理agent",
        "agentproject",
        "budgetmanager",
        "answerverifier",
        "agentstate",
        "fetch_external_data",
        "reactagent",
        "reactagentbackend",
        "agentrunner",
        "工具中间件",
        "scene识别",
        "taskplanner",
        "planvalidator",
        "planexecutor",
        "resultaggregator",
        "replanner",
        "toolcallcache",
        "30条检索案例",
        "62条离线agent案例",
    ),
    "farino": (
        "法奥",
        "farino",
        "aiflowy",
        "动态计划",
        "qa沉淀",
        "售后工单",
    ),
    "myagent": (
        "个人招聘",
        "招聘知识agent",
        "个人知识agent",
        "个人知识站",
        "个人知识项目",
        "myagent",
        "本站",
    ),
    "mood_tracker": (
        "情绪分析",
        "情绪分类",
        "情绪日记",
        "心情助手",
        "本地情绪模型",
        "moodtracker",
        "predict_emotion",
        "焦虑日记",
        "五分类",
        "多情绪对话标签",
    ),
}

_WEAK_PROJECT_SIGNALS = {
    "agentproject": (
        ("审批记录",),
        ("批准或拒绝",),
        ("恢复执行",),
        ("检索内容注入",),
        ("答案验证",),
        ("运行产物",),
        ("diagnostic event",),
        ("eventbus",),
        ("retrypolicy",),
        ("circuitbreaker",),
        ("semanticcache",),
    ),
    "farino": (
        ("无效工具",),
        ("问答快照",),
        ("消息id幂等",),
        ("计划更新",),
        ("任务目标",),
    ),
    "myagent": (
        ("siliconflow",),
        ("bge",),
        ("openai-compatible",),
        ("返回source",),
        ("生成元数据",),
        ("对话上下文",),
        ("持久化",),
        ("敏感内容模式",),
        ("pgvector",),
    ),
    "mood_tracker": (
        ("class_weight",),
        ("joblib",),
        ("macro-f1",),
        ("weighted-f1",),
        ("混淆矩阵",),
        ("误分类",),
        ("scikit-learn",),
        ("hugging face",),
        ("lazy loading",),
        ("k-means", "cluster id"),
        ("positive/negative/neutral",),
    ),
}

_DOMAIN_QUERIES = {
    "项目": ("项目", "作品"),
    "实习经历": ("实习", "工作经历", "校企合作"),
    "技能": ("技能", "技术能力", "技术栈"),
    "教育背景": ("教育", "学校", "专业", "学历"),
    "优势": ("优势", "优点", "优缺点", "优劣势", "强项", "长处"),
    "不足": ("不足", "缺点", "优劣势", "劣势", "短板", "边界"),
    "岗位匹配": ("岗位匹配", "为什么适合", "胜任"),
}

_GENERAL_TOPIC_QUERIES = (
    (
        r"机器学习.{0,18}(?:深度学习|算法工程师)|"
        r"(?:深度学习|算法工程师).{0,18}机器学习",
        "机器学习能力边界 传统机器学习 深度学习算法工程师",
        ("机器学习能力边界", "能力边界", "有项目实践"),
    ),
    (
        r"系统问题.{0,16}(?:定位|验证)|"
        r"(?:定位|排查).{0,16}(?:系统问题|故障)",
        "问题定位 日志 命令输出 配置 调用链 复现步骤 故障验证",
        ("问题定位", "工程导向"),
    ),
    (
        r"重点技能|技术能力|技能有哪些|哪些技能",
        "重点技能 技能矩阵 Agent RAG Python 后端",
        ("重点技能", "有项目实践"),
    ),
    (
        r"技能矩阵",
        "技能矩阵 重点技能 有项目实践 基础二次开发",
        ("技能矩阵", "重点技能", "有项目实践"),
    ),
)


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.lower())


def _is_project_list_request(question: str) -> bool:
    q = question.lower()
    if re.search(
        r"(?:项目|作品)的?(?:名|名称|名字).{0,8}"
        r"(?:为什么|为何|怎么|如何|由来|含义)",
        q,
    ):
        return False
    english_patterns = (
        r"\b(?:what|which)\s+projects?\s+(?:have|has|did|do)\b"
        r".{0,16}\b(?:built|made|worked|shown)\b",
        r"\blist\b.{0,24}\b(?:projects?|names?)\b",
        r"\bnames?\s+of\s+(?:your\s+)?(?:public\s+)?projects?\b",
    )
    chinese_patterns = (
        r"(?:哪些|哪几个|有几个|多少个|(?<!为)什么).{0,8}(?:项目|作品)"
        r"(?!管理|指标|方法|名称|架构|技术|数据|文档|经历|经验)",
        r"(?:项目|作品)的?(?:名|名称|名字|清单|列表)",
        r"(?:列出|罗列|报一下|报出|给出).{0,20}(?:项目|作品)",
        r"做过(?:什么|哪些)(?:项目|作品)?",
    )
    return any(
        re.search(pattern, q, re.IGNORECASE)
        for pattern in (*english_patterns, *chinese_patterns)
    )


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
    strict_coverage: bool = False

    @property
    def requires_complete_coverage(self) -> bool:
        return self.strict_coverage or self.intent in {
            "project_list", "multi_project", "multi_part"
        }


def _mentioned_projects(question: str, projects: Sequence[Project]) -> list[Project]:
    normalized = _normalize(question)
    has_portfolio_context = bool(re.search(
        r"朱旭|候选人|简历|作品集|"
        r"(?:你|你的).{0,8}(?:项目|作品|系统|实现)|"
        r"(?:项目|作品|系统).{0,8}(?:中|里|采用|使用|实现|为什么)",
        question,
        re.IGNORECASE,
    ))
    mentioned: list[Project] = []
    for project in projects:
        strong_aliases = (
            _normalize(project.title),
            project.slug,
            *_STRONG_PROJECT_ALIASES.get(project.slug, ()),
        )
        strong_match = any(
            _normalize(alias) in normalized for alias in strong_aliases
        )
        weak_signal_count = sum(
            any(_normalize(alias) in normalized for alias in aliases)
            for aliases in _WEAK_PROJECT_SIGNALS.get(project.slug, ())
        )
        if strong_match or (weak_signal_count and (
            has_portfolio_context or weak_signal_count >= 2
        )):
            mentioned.append(project)
    return mentioned


def _project_fields(question: str) -> list[tuple[str, str, tuple[str, ...]]]:
    fields: list[tuple[str, str, tuple[str, ...]]] = []
    field_patterns = (
        (
            "经历性质",
            "经历性质 项目性质 校企合作 正式实习 个人项目",
            ("经历性质", "项目性质", "项目背景", "项目简介"),
            r"性质|实习|校企合作|个人项目",
        ),
        (
            "项目背景",
            "项目背景 场景 项目描述",
            ("项目背景", "项目描述", "项目简介"),
            r"背景|场景|解决(?:什么|哪些|哪类).{0,6}(?:问题|需求|场景)?|做什么",
        ),
        ("个人职责", "个人职责 负责 贡献 角色", ("个人贡献", "个人职责", "职责", "负责"), r"职责|负责|贡献|角色|主导"),
        (
            "技术方案",
            "技术栈 架构 技术方案 实现",
            ("技术栈", "技术方案", "架构", "系统组成"),
            r"技术|技术栈|架构|实现|方案|框架|技术路线|"
            r"工程机制|关键机制|toolpolicy|人工审批|审批策略|"
            r"工具.{0,8}(?:校验|验证)|调用风险|"
            r"\bsse\b|流式(?:输出|事件|回答)|事件协议|来源事件|先发来源|"
            r"回答\s*token|\btoken\b|规划阶段|同步机制|同步步骤|"
            r"architecture|orchestration|technology|tech\s*stack|framework",
        ),
        ("结果与产出", "结果 成果 产出 效果", ("结果", "成果", "产出", "项目价值"), r"结果|成果|产出|效果"),
        (
            "局限与边界",
            "局限 不足 边界",
            ("局限", "不足", "边界"),
            r"局限|不足|边界|(?:存在|遇到|出现|当前).{0,6}问题|"
            r"问题.{0,4}(?:是什么|有哪些|如何解决)",
        ),
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


def _company_internship_target(question: str) -> QueryTarget | None:
    if not re.search(
        r"(?:正式|公司|企业).{0,6}实习|实习.{0,6}(?:正式|公司|企业)",
        question,
    ):
        return None
    return QueryTarget(
        query="正式公司实习 企业实习 工作经历 时间线",
        coverage_key="正式公司实习",
        section_terms=(
            "正式公司实习",
            "工作经历",
            "实习经历",
            "经历结构",
            "经历性质",
        ),
    )


def _timeline_target(question: str) -> QueryTarget | None:
    years = list(dict.fromkeys(re.findall(r"20\d{2}", question)))
    if len(years) < 2 or not re.search(r"获奖|实习|项目|经历|教育", question):
        return None
    return QueryTarget(
        query=f"{' '.join(years)} 经历时间线 获奖 实习 AI 项目",
        coverage_key="阶段时间线",
        section_terms=("经历时间线", *years),
    )


def _capability_targets(question: str) -> list[QueryTarget]:
    slots = (
        (
            "测试实践",
            r"测试|test(?:ing)?",
            "测试实践 自动化测试 单元测试 集成测试",
            ("测试", "自动化测试", "单元测试", "集成测试"),
        ),
        (
            "离线评测",
            r"离线评测|离线基准|评测集|offline evaluation|benchmark",
            "离线评测 评测集 基准测试 指标",
            ("离线评测", "评测集", "评测"),
        ),
        (
            "Trace 与可观测性",
            r"\btrace\b|链路追踪|可观测",
            "Trace 链路追踪 可观测性 日志 指标",
            ("Trace", "链路追踪", "可观测性"),
        ),
        (
            "故障定位",
            r"故障定位|故障排查|问题排查|问题定位|排障",
            "故障定位 问题排查 日志 配置 调用链 复现验证",
            ("故障定位", "问题定位", "工程导向"),
        ),
    )
    targets = [
        QueryTarget(
            query=query,
            coverage_key=label,
            section_terms=section_terms,
        )
        for label, pattern, query, section_terms in slots
        if re.search(pattern, question, re.IGNORECASE)
    ]
    return targets if len(targets) >= 2 else []


def _skill_wording_targets(question: str) -> list[QueryTarget]:
    has_overclaim = bool(re.search(r"精通|专家级|专家水平|熟练掌握", question))
    has_skill_subject = bool(re.search(r"技能|技术栈|技术能力|能力", question))
    asks_for_wording = bool(re.search(
        r"描述|表述|措辞|层级|层次|换成|改成|更准确",
        question,
    ))
    if not (has_overclaim and has_skill_subject and asks_for_wording):
        return []
    return [
        QueryTarget(
            query="技术能力边界 避免夸大 精通 专家级 风险一致性",
            coverage_key="技能能力边界",
            section_terms=("能力边界", "风险与一致性", "禁止夸大"),
        ),
        QueryTarget(
            query="技能矩阵 重点技能 有项目实践 基础二次开发 措辞层级",
            coverage_key="技能措辞层级",
            section_terms=("技能矩阵", "重点技能", "有项目实践", "基础二次开发"),
        ),
    ]


def _split_complex_clauses(question: str) -> list[str]:
    boundary = r"[；;]|[，。！？?]\s*(?:并且|同时|另外|还要|再说明|再介绍)"
    if not re.search(boundary, question):
        return []
    parts = re.split(boundary, question)
    cleaned: list[str] = []
    for part in parts:
        value = re.sub(r"^(请|并|再|还|分别)", "", part.strip(" ，。！？?"))
        if len(value) >= 3 and value not in cleaned:
            cleaned.append(value)
    return cleaned if len(cleaned) >= 2 else []


def _semantic_multi_parts(question: str) -> list[str]:
    fact_slots = (
        ("经历性质", ("经历性质", "经历类型", "经历类别", "项目性质", "实习性质")),
        ("贡献来源", ("贡献来源", "个人贡献", "本人贡献", "职责来源")),
        ("效果口径", ("效果口径", "成果表述", "效果表述", "结果口径", "产出口径")),
    )
    matched_facts = [
        label
        for label, aliases in fact_slots
        if any(alias in question for alias in aliases)
    ]
    if len(matched_facts) >= 2:
        return matched_facts

    role_slots = (
        ("算法研究岗位", ("算法研究岗", "研究型算法岗", "研究型算法职位")),
        ("AI 应用后端岗位", ("ai应用后端", "ai 应用后端", "应用型后端职位", "应用后端岗")),
    )
    normalized_question = question.lower()
    matched_roles = [
        label
        for label, aliases in role_slots
        if any(alias in normalized_question for alias in aliases)
    ]
    compares_roles = bool(re.search(r"分别|对比|比较|区别|差异|与|和|vs\.?", question, re.IGNORECASE))
    evaluates_fit = bool(re.search(r"匹配|适配|胜任|缺口|不足|短板|区别|差异", question))
    if len(matched_roles) >= 2 and compares_roles and evaluates_fit:
        return matched_roles
    return []


def _multi_part_plan(parts: list[str]) -> QueryPlan:
    targets = [QueryTarget(query=part, coverage_key=part) for part in parts]
    return QueryPlan(
        intent="multi_part",
        targets=targets,
        expected_coverage=parts,
        context_limit=min(10, max(6, len(parts) * 2)),
    )


def _compares_project_with_independent_domain(
    question: str,
    domains: list[str],
) -> bool:
    if "项目" not in domains or len(domains) < 2:
        return False
    return bool(re.search(r"衔接|它们|两者|二者|有何不同|对比|比较", question))


def plan_question(question: str, projects: Sequence[Project]) -> QueryPlan:
    q = question.lower()
    mentioned = _mentioned_projects(question, projects)
    has_project_word = bool(re.search(r"项目|作品|project", q, re.IGNORECASE))
    project_list_request = _is_project_list_request(question)
    all_projects = bool(re.search(
        r"(?:所有|全部|各个|每个|每项|逐个|四个|几个).{0,6}(?:项目|作品)|"
        r"(?:项目|作品).{0,6}(?:分别|每个|每项|各个|全部|所有)|"
        r"\b(?:all|each|every)\b.{0,16}\bprojects?\b|"
        r"\bprojects?\b.{0,16}\b(?:all|each|every)\b",
        q,
        re.IGNORECASE,
    ))
    detail_request = bool(re.search(
        r"介绍|详细|背景|职责|负责|贡献|技术|架构|成果|结果|对比|比较|区别|"
        r"architecture|technology|framework|responsibilit|result|compare|differ",
        q,
        re.IGNORECASE,
    ))
    domains = [
        label
        for label, aliases in _DOMAIN_QUERIES.items()
        if any(alias in q for alias in aliases)
    ]

    if project_list_request and not detail_request and not mentioned:
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
        internship_target = _company_internship_target(question)
        if internship_target is not None:
            targets.append(internship_target)
        return QueryPlan(
            intent="multi_project",
            targets=targets,
            expected_coverage=[target.coverage_key for target in targets],
            context_limit=min(16, max(6, len(targets))),
        )

    if len(mentioned) == 1:
        if _compares_project_with_independent_domain(question, domains):
            return _multi_part_plan(domains)
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

    skill_wording_targets = _skill_wording_targets(question)
    if skill_wording_targets:
        return QueryPlan(
            intent="general",
            targets=skill_wording_targets,
            expected_coverage=[
                target.coverage_key for target in skill_wording_targets
            ],
            context_limit=6,
            strict_coverage=True,
        )

    capability_targets = _capability_targets(question)
    if capability_targets:
        return QueryPlan(
            intent="general",
            targets=capability_targets,
            expected_coverage=[
                target.coverage_key for target in capability_targets
            ],
            context_limit=min(8, max(5, len(capability_targets) * 2)),
            strict_coverage=True,
        )

    for pattern, query_terms, section_terms in _GENERAL_TOPIC_QUERIES:
        if re.search(pattern, question, re.IGNORECASE):
            return QueryPlan(
                intent="general",
                targets=[QueryTarget(
                    query=query_terms,
                    coverage_key="general",
                    section_terms=section_terms,
                )],
                context_limit=5,
            )

    semantic_parts = _semantic_multi_parts(question)
    if semantic_parts:
        return _multi_part_plan(semantic_parts)

    if len(domains) >= 2:
        targets = [
            QueryTarget(query=f"朱旭的{domain}", coverage_key=domain)
            for domain in domains
        ]
        timeline_target = _timeline_target(question)
        if timeline_target is not None:
            targets.append(timeline_target)
        return QueryPlan(
            intent="multi_part",
            targets=targets,
            expected_coverage=[target.coverage_key for target in targets],
            context_limit=min(10, max(6, len(targets) * 2)),
        )

    clauses = _split_complex_clauses(question)
    if clauses:
        return _multi_part_plan(clauses)

    return QueryPlan(
        intent="general",
        targets=[QueryTarget(question, "general")],
        context_limit=5,
    )
