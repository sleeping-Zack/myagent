import re
from typing import TYPE_CHECKING, Union

from app.schemas.citation import CitationOut

if TYPE_CHECKING:
    from app.services.retrieval_service import RetrievalOutcome


_INTERNAL_REFERENCE_RE = re.compile(
    r"(?:[\w\u4e00-\u9fff.-]+[\\/])+[\w\u4e00-\u9fff.-]*|"
    r"[\w\u4e00-\u9fff.-]+\.[a-z][a-z0-9_-]{0,11}(?![a-z0-9])",
    re.IGNORECASE,
)

_UNAVAILABLE_VALUE_RE = re.compile(
    r"缺少|没有|未(?:提供|记录|披露|确认|统计|公布)|未知|不详|"
    r"待补充|不应猜测|无法证明|不能证明|不(?:虚构|声称)"
)
_FIELD_REQUIREMENTS = (
    (
        re.compile(r"\bgpa\b|绩点", re.IGNORECASE),
        re.compile(
            r"(?:\bgpa\b|绩点)\s*(?:为|是|[:：])?\s*[0-4](?:\.\d{1,2})?\b",
            re.IGNORECASE,
        ),
    ),
    (
        re.compile(r"(?:专业|年级|班级|成绩).{0,4}排名"),
        re.compile(
            r"(?:专业|年级|班级|成绩)?排名\s*(?:为|是|[:：])?\s*"
            r"(?:第\s*)?\d+\s*(?:名|位|%|/\s*\d+)?"
        ),
    ),
    (
        re.compile(
            r"英语.{0,6}(?:考试|成绩|分数)|四六级|四级|六级|"
            r"\bcet\s*[- ]?[46]\b|雅思|托福",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:英语(?:考试|成绩|分数|四级|六级|四六级)|四六级|四级|六级|"
            r"\bcet\s*[- ]?[46]\b|雅思|托福)\s*"
            r"(?:成绩|分数)?\s*(?:为|是|[:：])?\s*\d+(?:\.\d+)?\s*(?:分)?",
            re.IGNORECASE,
        ),
    ),
    (
        re.compile(r"在哪个城市|(?:期望|希望|意向).{0,8}(?:城市|地点)|工作城市|工作地点"),
        re.compile(
            r"(?:(?:期望|希望|意向)(?:工作)?(?:城市|地点|工作地)|"
            r"(?:工作)?(?:城市|地点|工作地))\s*(?:为|是|[:：])\s*"
            r"(?:北京|上海|天津|重庆|广州|深圳|杭州|南京|成都|武汉|西安|苏州|"
            r"[\u4e00-\u9fff]{2,8}市)"
            r"|(?:期望|希望|意向)\s*(?:在|去)\s*"
            r"(?:北京|上海|天津|重庆|广州|深圳|杭州|南京|成都|武汉|西安|苏州|"
            r"[\u4e00-\u9fff]{2,8}市).{0,4}(?:工作|就业)"
        ),
    ),
    (
        re.compile(r"到岗|入职时间"),
        re.compile(
            r"(?:到岗|入职)(?:时间)?\s*(?:为|是|[:：])?\s*"
            r"(?:随时|立即|马上|尽快|"
            r"\d{4}[-年/.]\d{1,2}(?:[-月/.]\d{1,2})?|"
            r"(?:\d+|[一二两三四五六七八九十]+)(?:天|周|个月|月)(?:内|后)?)"
            r"|(?:随时|立即|马上|尽快|"
            r"\d{4}[-年/.]\d{1,2}(?:[-月/.]\d{1,2})?|"
            r"(?:\d+|[一二两三四五六七八九十]+)(?:天|周|个月|月)(?:内|后)?)"
            r".{0,4}(?:到岗|入职)"
        ),
    ),
    (
        re.compile(r"每周.{0,10}(?:实习|到岗).{0,8}(?:几|多少|天|日)"),
        re.compile(
            r"每周\s*(?:可|能|可以)?\s*(?:实习|到岗)?\s*"
            r"(?:\d+|[一二两三四五六七八九十]+)\s*(?:天|日)"
        ),
    ),
    (
        re.compile(r"薪资|薪酬|工资"),
        re.compile(
            r"(?:期望)?(?:薪资|薪酬|工资)\s*(?:为|是|[:：])?\s*(?:人民币)?\s*"
            r"\d+(?:\.\d+)?(?:\s*[-~至到]\s*\d+(?:\.\d+)?)?\s*"
            r"(?:k|千|万|元)(?:\s*/\s*(?:月|年|天))?",
            re.IGNORECASE,
        ),
    ),
    (
        re.compile(r"企业用户|企业客户"),
        re.compile(
            r"(?:企业用户|企业客户)(?:数|数量|量)?\s*(?:为|是|达到|[:：])?\s*"
            r"\d+(?:\.\d+)?\s*(?:万|千)?\s*(?:家|个|名)?"
            r"|\d+(?:\.\d+)?\s*(?:万|千)?\s*(?:家|个|名)?\s*"
            r"(?:企业用户|企业客户)"
        ),
    ),
    (
        re.compile(
            r"(?:日|月|年)?访问量|访问用户|访问次数|"
            r"(?:每天|每日|日均).{0,12}访问|(?:多少|几).{0,4}(?:次)?访问|"
            r"\b(?:pv|uv|dau|mau)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:(?:日|月|年)?访问量|访问用户|访问次数|\b(?:pv|uv|dau|mau)\b)"
            r"(?:数|数量)?\s*(?:为|是|达到|[:：])?\s*"
            r"\d+(?:\.\d+)?\s*(?:万|千)?\s*(?:次|人|个)?"
            r"|\d+(?:\.\d+)?\s*(?:万|千)?\s*(?:次|人|个)?\s*"
            r"(?:(?:日|月|年)?访问量|访问用户|访问次数|\b(?:pv|uv|dau|mau)\b)",
            re.IGNORECASE,
        ),
    ),
    (
        re.compile(r"(?:正式)?上线到哪些企业|上线企业(?:是|包括|有哪些)"),
        re.compile(
            r"(?:已|正式)?上线(?:到|于)?\s*"
            r"[\u4e00-\u9fffA-Za-z0-9·-]{1,20}(?:公司|集团|医院|企业)"
        ),
    ),
    (
        re.compile(r"覆盖.{0,8}(?:多少|几).{0,6}(?:客户)?现场|客户现场"),
        re.compile(
            r"(?:覆盖\s*\d+(?:\.\d+)?\s*个?\s*客户现场|"
            r"客户现场(?:覆盖)?(?:数量)?\s*(?:为|是|达到|[:：])?\s*"
            r"\d+(?:\.\d+)?)"
        ),
    ),
    (
        re.compile(r"客服(?:请求|咨询)(?:量|次数)?"),
        re.compile(
            r"(?:日|每日|每天)?客服(?:请求|咨询)(?:量|次数)?"
            r"\s*(?:为|是|达到|[:：])?\s*"
            r"\d+(?:\.\d+)?\s*(?:万|千)?\s*(?:次|条)?"
        ),
    ),
    (
        re.compile(r"(?:正式)?上线客户|上线企业|企业上线|落地客户"),
        re.compile(
            r"(?:(?:正式)?上线客户|上线企业|企业上线|落地客户)"
            r"(?:数|数量|范围)?\s*(?:为|是|达到|[:：])?\s*"
            r"\d+(?:\.\d+)?\s*(?:万|千)?\s*(?:家|个)?"
            r"|\d+(?:\.\d+)?\s*(?:万|千)?\s*(?:家|个)?\s*"
            r"(?:(?:正式)?上线客户|上线企业|企业上线|落地客户)"
        ),
    ),
    (
        re.compile(r"并发|\b(?:qps|tps|rps)\b", re.IGNORECASE),
        re.compile(
            r"(?:并发量|并发数|并发用户|峰值并发|\b(?:qps|tps|rps)\b)"
            r"\s*(?:为|是|达到|[:：])?\s*\d+(?:\.\d+)?\s*"
            r"(?:万|千)?\s*(?:qps|tps|rps|请求/秒|用户|连接)?",
            re.IGNORECASE,
        ),
    ),
    (
        re.compile(
            r"每秒.{0,12}(?:请求|查询)|吞吐(?:量)?|请求速率|"
            r"\b(?:qps|tps|rps)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:吞吐(?:量)?|每秒.{0,6}(?:请求|查询)|请求(?:速率|量)?|"
            r"\b(?:qps|tps|rps)\b).{0,8}?"
            r"\d+(?:\.\d+)?\s*(?:万|千)?\s*"
            r"(?:qps|tps|rps|请求/秒|次/秒)",
            re.IGNORECASE,
        ),
    ),
    (
        re.compile(
            r"\bp(?:50|90|95|99)\b.{0,10}(?:响应|延迟|耗时|时间)|"
            r"(?:响应|延迟|耗时).{0,10}\bp(?:50|90|95|99)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bp(?:50|90|95|99)\b.{0,10}?"
            r"\d+(?:\.\d+)?\s*(?:ms|毫秒|s|秒)\b",
            re.IGNORECASE,
        ),
    ),
    (
        re.compile(
            r"线上.{0,12}(?:准确率|正确率)|"
            r"(?:准确率|正确率).{0,12}线上"
        ),
        re.compile(
            r"线上.{0,12}(?:准确率|正确率).{0,12}"
            r"\d+(?:\.\d+)?\s*(?:%|百分点)",
        ),
    ),
    (
        re.compile(r"路由.{0,8}(?:准确率|正确率)|(?:准确率|正确率).{0,8}路由"),
        re.compile(
            r"路由.{0,8}(?:准确率|正确率).{0,8}"
            r"\d+(?:\.\d+)?\s*%"
        ),
    ),
    (
        re.compile(r"测试集.{0,8}(?:有多大|多少|规模)"),
        re.compile(
            r"测试集(?:规模)?\s*(?:为|是|有|包含|达到|[:：])?\s*"
            r"\d+\s*(?:条|题|个|份|样本)"
            r"|测试集\s*\|\s*\d+(?:\s*\|)?"
            r"|\d+\s*条独立测试样本"
        ),
    ),
    (
        re.compile(r"\bsla\b|服务等级|可用性", re.IGNORECASE),
        re.compile(
            r"(?:\bsla\b|服务等级|可用性)\s*(?:为|是|达到|[:：])?\s*"
            r"(?:\d+(?:\.\d+)?\s*%|(?:\d+|[一二两三四五六七八九十]+)\s*个九)",
            re.IGNORECASE,
        ),
    ),
    (
        re.compile(r"几个九|稳定性.{0,8}(?:达到|多少|几个九)"),
        re.compile(
            r"(?:生产)?(?:稳定性|可用性)\s*(?:为|是|达到|[:：])?\s*"
            r"(?:\d+(?:\.\d+)?\s*%|(?:\d+|[一二两三四五六七八九十]+)\s*个九)"
        ),
    ),
    (
        re.compile(r"商业收益|收益|营收|收入|利润|成本节省|商业指标"),
        re.compile(
            r"(?:商业收益|收益|营收|收入|利润|成本节省|商业指标|降本)"
            r".{0,12}?\d+(?:\.\d+)?\s*(?:万|千|亿)?\s*"
            r"(?:元|人民币|%|百分点)"
        ),
    ),
)


def _redact_internal_references(value: str) -> str:
    return _INTERNAL_REFERENCE_RE.sub("[内部资料]", value)


def _has_field_value(chunks: list[dict], value_pattern: re.Pattern) -> bool:
    for chunk in chunks:
        text = " ".join([
            chunk.get("title") or "",
            chunk.get("section") or "",
            chunk.get("content") or "",
        ])
        for clause in re.split(r"[\n。！？；;]", text):
            if value_pattern.search(clause) and not _UNAVAILABLE_VALUE_RE.search(clause):
                return True
    return False


class CitationService:
    def format_citations(self, chunks: list[dict]) -> list[CitationOut]:
        citations: list[CitationOut] = []
        for chunk in chunks:
            title = _redact_internal_references(chunk["title"])
            preview = _redact_internal_references((chunk.get("content") or "")[:150])
            citations.append(
                CitationOut(
                    id=chunk["chunk_id"],
                    title=title,
                    section=chunk.get("section"),
                    content_preview=preview,
                    project_slug=chunk.get("project_slug"),
                    tags=chunk.get("tags") or [],
                    ranking_score=chunk["score"],
                )
            )
        return citations

    def has_sufficient_evidence(
        self,
        evidence: Union[list[dict], "RetrievalOutcome"],
        question: str,
        min_score: float = 0.40,
    ) -> bool:
        outcome = None if isinstance(evidence, list) else evidence
        chunks = evidence if outcome is None else outcome.chunks
        if outcome and outcome.plan.intent == "project_list":
            return bool(outcome.direct_answer)
        if not chunks:
            return False

        if outcome and outcome.plan.requires_complete_coverage and outcome.missing_coverage:
            return False

        top_score = chunks[0]["score"]
        if top_score < min_score:
            return False

        field_requirements = [
            value_pattern
            for question_pattern, value_pattern in _FIELD_REQUIREMENTS
            if question_pattern.search(question)
        ]
        if field_requirements and not all(
            _has_field_value(chunks, requirement)
            for requirement in field_requirements
        ):
            return False

        # 问题含数字/排名 → 必须有含数字的证据
        if re.search(r"\d|排名|绩点|gpa|第[一二三四五六七八九十\d]|top\s*\d", question, re.IGNORECASE):
            has_numeric = any(
                re.search(r"\d", c.get("content") or "") for c in chunks
            )
            if not has_numeric:
                return False

        # 个人贡献语境中的“主导/独立完成”才要求职责证据；“独立运行”不属于贡献声明。
        if re.search(r"主导|独立\s*(?:完成|负责|承担|开发|设计|实现|做)", question):
            has_resp = any(
                (c.get("section") or "").lower() in ("responsibility", "职责") for c in chunks
            )
            if not has_resp:
                return False

        # 问题含“实习” → 证据本身必须明确提及实习经历。
        if "实习" in question:
            asks_experience_nature = any(
                term in question for term in ("校企合作", "个人项目")
            )
            has_exp = any(
                "experience" in (c.get("tags") or [])
                or "实习" in " ".join([
                    c.get("title") or "",
                    c.get("section") or "",
                    c.get("content") or "",
                ])
                for c in chunks
            )
            has_alternative_nature = asks_experience_nature and any(
                any(term in (c.get("content") or "") for term in ("校企合作", "个人项目"))
                for c in chunks
            )
            if not has_exp and not has_alternative_nature:
                return False

        return True
