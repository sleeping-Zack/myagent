import hashlib
import html
import ipaddress
import re
import unicodedata
from datetime import date
from urllib.parse import unquote
from fastapi import Request
from app.core.config import settings


def hash_ip(ip: str) -> str:
    """日级别盐值哈希IP，用于限流而不存储原始IP"""
    daily_salt = str(date.today())
    return hashlib.sha256(f"{ip}{daily_salt}{settings.secret_key}".encode()).hexdigest()[:16]


def get_client_ip(request: Request) -> str:
    """Only trust X-Real-IP when the direct peer is a configured reverse proxy."""
    peer = request.client.host if request.client else "unknown"
    trusted_peer = False
    try:
        peer_address = ipaddress.ip_address(peer)
        trusted_peer = any(
            peer_address in ipaddress.ip_network(value, strict=False)
            for value in settings.csv_values("trusted_proxy_ips")
        )
    except ValueError:
        pass
    if trusted_peer:
        forwarded = request.headers.get("x-real-ip", "").strip()
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return peer


def is_safe_question(text: str) -> bool:
    """拒绝明显的越权、敏感资源读取和知识库导出请求。"""
    normalized = html.unescape(unquote(text))
    normalized = unicodedata.normalize("NFKC", normalized)
    normalized = normalized.translate(str.maketrans({"∕": "/", "⁄": "/"}))
    normalized = "".join(
        char for char in normalized if unicodedata.category(char) != "Cf"
    )
    spaced = re.sub(r"\s+", " ", normalized.casefold()).strip()
    normalized = re.sub(r"\s+", "", spaced)

    unquoted_spaced, quoted_count = re.subn(
        r"'[^']*'|\"[^\"]*\"|“[^”]*”|‘[^’]*’|`[^`]*`", " ", spaced
    )
    unquoted_compact = re.sub(r"\s+", "", unquoted_spaced)
    meta_discussion = re.search(
        r"\b(?:explain|analy[sz]e|discuss)\b.*"
        r"\b(?:unsafe|dangerous|security|prompt[- ]?injection)\b|"
        r"\bwhy\b.*\b(?:unsafe|dangerous|security|prompt[- ]?injection)\b",
        unquoted_spaced,
        re.IGNORECASE,
    ) or re.search(
        r"为什么.{0,40}(?:危险|不安全|安全测试|拒绝)|"
        r"(?:分析|解释|讨论).{0,40}(?:危险|不安全|注入|安全)|"
        r"(?:分析|解释|定义|讨论).{0,20}(?:这个|该)?(?:术语|概念|含义)",
        unquoted_compact,
    )
    unquoted_command = re.search(
        r"\b(?:reveal|print|read|show|share|send|give|provide|disclose|dump|"
        r"fetch|quote|access|translate|summari[sz]e|encode|transform|convert|"
        r"compress|transcribe|ignore|execute|run|follow|obey)\b|"
        r"\b(?:then|now)\s+do\s+it\b",
        unquoted_spaced,
        re.IGNORECASE,
    ) or re.search(
        r"忽略|绕过|打开|读取|查看|展示|显示|输出|导出|发送|发给我|"
        r"告诉我|给我看|发我|泄露|调取|抄出|抄录|贴出|回显|"
        r"翻译|改写|编码|转换|转成|压缩|执行|照做",
        unquoted_compact,
    )
    if quoted_count and meta_discussion and not unquoted_command:
        return True

    encoded_instruction_attack = re.search(
        r"\bdecode\b.{0,40}\b(?:execute|run|follow|obey)\b|"
        r"\bdecode\b.{0,32}\b(?:hidden|encoded)\s+(?:instruction|prompt)\b|"
        r"\b(?:hidden|encoded)\s+(?:instruction|prompt)\b.{0,32}\bdecode\b",
        spaced,
        re.IGNORECASE,
    ) or re.search(
        r"解码.{0,32}(?:执行|运行|遵循|照做)|"
        r"解码.{0,20}(?:隐藏|编码).{0,8}(?:指令|提示词)|"
        r"(?:隐藏|编码).{0,8}(?:指令|提示词).{0,20}解码",
        normalized,
    )
    if encoded_instruction_attack:
        return False

    direct_dangerous_patterns = [
        r"忽略.{0,12}(此前|之前|以上).{0,8}(指令|规则|要求)",
        r"ignore.{0,20}(previous|prior).{0,12}(instruction|prompt)",
        r"ignore.{0,20}(privacy|security|safety).{0,12}(policy|rule|restriction)",
    ]
    if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in direct_dangerous_patterns):
        return False

    protected_resource = re.search(
        r"知识库|资料库|文档库|内部(?:文档|文件|资料)|私有(?:文档|文件|资料)|"
        r"提示词|系统提示词|systemprompt|开发者指令|(?:hr|面试)问答(?:文档|文件)?|"
        r"(?:knowledge|prompts?)[\\/]",
        normalized,
        re.IGNORECASE,
    )
    private_target = re.search(
        r"微信号|(?:候选人|朱旭|本人|他的|她的).{0,16}"
        r"(?:邮箱|微信号?|联系方式|手机号|电话|住址|地址|账号|身份证号?|银行卡号?)|"
        r"(?:私有|私密|私人|个人|隐私|未公开|隐藏).{0,10}"
        r"(?:邮箱|微信号?|联系方式|手机号|电话|住址|地址|账号|档案|记录)|"
        r"内部(?:备注|记录|指令)|候选人资料|"
        r"(?:private[_-]?profile|internal[_-]?notes?|hr[_-]?interview[_-]?qa)",
        normalized,
        re.IGNORECASE,
    )
    english_private_target = re.search(
        r"(?:\d+_)?private[_ -]?profile|internal[_ -]?notes?|"
        r"\b(?:private|personal|non-public|hidden|internal)\s+"
        r"(?:candidate\s+)?(?:email|phone|address|contact|wechat|account|profile|"
        r"notes?|records?|file|document|dossier)\b",
        spaced,
        re.IGNORECASE,
    )
    credential_target = re.search(
        r"api[_-]?key|密码|口令|私钥|密钥|ssh(?:key|私钥|凭据)?|服务器凭据|"
        r"access[_-]?token|credentials?|passphrase|password",
        normalized,
        re.IGNORECASE,
    )
    file_reference = re.search(
        r"(?:knowledge|prompts?|config|notes|etc|root|home|var|srv)[\\/]"
        r"(?:[\w\u4e00-\u9fff.-]+[\\/])*[\w\u4e00-\u9fff.-]+|"
        r"\.env(?:\.[a-z0-9_-]+)?|"
        r"(?:credentials?|secrets?|id_rsa|authorized_keys)(?:\.[a-z0-9_-]+)?",
        normalized,
        re.IGNORECASE,
    )
    referenced_file_target = re.search(
        r"(?:那个|这个|该|上述|前述)(?:文件|文档)", normalized
    )
    sensitive_target = (
        protected_resource
        or private_target
        or english_private_target
        or credential_target
        or file_reference
        or referenced_file_target
    )
    metadata_discussion = re.search(
        r"(?:比较|解释|说明|讨论).{0,32}(?:命名|用途|格式|结构|字段|类型)",
        normalized,
    )
    negated_metadata_extraction = re.search(
        r"(?:不要|无需|不需要).{0,8}?(?:展示|显示|输出|读取|打开|打印)"
        r".{0,12}?(?:值|内容|原文)",
        normalized,
    )
    safe_metadata_discussion = False
    if metadata_discussion and negated_metadata_extraction:
        remaining_text = (
            normalized[:negated_metadata_extraction.start()]
            + normalized[negated_metadata_extraction.end():]
        )
        safe_metadata_discussion = not re.search(
            r"展示|显示|输出|读取|打开|打印|发送|发给我|告诉我|给我看|"
            r"泄露|调取|抄出|抄录|贴出|回显|reveal|print|read|show|share|send",
            remaining_text,
            re.IGNORECASE,
        )

    extraction_intent = re.search(
        r"打开|读取|查看|展示|显示|输出|导出|列(?:出|一下)|"
        r"返回(?:给我)?.{0,24}(?:内容|原文|全文|文件|文档)|"
        r"发送|发给我|"
        r"告诉我|给我看|发我|泄露|调取|抄出|抄录|贴出(?:来)?|回显|"
        r"翻译|改写|编码|转换|转成|压缩|"
        r"复述|引用|总结|目录|列表|有哪些(?:文档|文件|内容)|"
        r"都写了什么|写了什么|完整内容|全部内容|原文|全文|"
        r"reveal|print|verbatim",
        normalized,
        re.IGNORECASE,
    )
    english_extraction_intent = re.search(
        r"\b(?:reveal|print|read|show|share|send|give|provide|disclose|dump|fetch|"
        r"quote|access|translate|summari[sz]e|encode|transform|convert|compress|"
        r"transcribe)\b|\bverbatim\b",
        spaced,
        re.IGNORECASE,
    )
    authority_or_bypass = re.search(
        r"(?:我是|作为|假装(?:我是)?)(?:系统)?(?:管理员|hr|人事|维护人员|开发者|所有者)|"
        r"(?:已获|已经获得|拥有).{0,8}(?:授权|许可|批准)|"
        r"(?:调试|开发者)模式|"
        r"绕过(?:过滤|限制|规则|校验|审查)|"
        r"(?:已|已经)(?:改成|设为|标为)公开",
        normalized,
        re.IGNORECASE,
    )
    english_authority = re.search(
        r"\b(?:you are|act as|as|pretend (?:you(?:'re| are)|to be))\s+"
        r"(?:the\s+)?(?:system\s+)?(?:administrator|admin|hr|owner|maintainer)\b|"
        r"\b(?:admin|hr|owner)\s+(?:approval|authorization|permission)\b",
        spaced,
        re.IGNORECASE,
    )

    safe_print_guidance = re.search(
        r"^(?:请)?(?:如何|怎样).{0,12}(?:避免|防止|阻止|禁止).{0,32}打印",
        normalized,
    ) and not re.search(
        r"(?:另外|然后|同时|接着|现在|不过|但是|[；;]|[。！？?!](?:请|把|将))"
        r".{0,24}打印",
        normalized,
    )
    chinese_print_intent = re.search(r"打印", normalized) and not safe_print_guidance
    shell_file_command = re.search(
        r"^(?:(?:sudo\s+)?cat\s+(?:[/~.]|[a-z]:[\\/])|"
        r"type\s+[a-z]:[\\/]|"
        r"(?:get-content|gc)\s+(?:[/~.]|[a-z]:[\\/]))",
        spaced,
        re.IGNORECASE,
    )
    dangerous_intent = (
        extraction_intent
        or english_extraction_intent
        or chinese_print_intent
        or shell_file_command
    )
    if safe_metadata_discussion and not (authority_or_bypass or english_authority):
        return True
    return not (
        sensitive_target and (dangerous_intent or authority_or_bypass or english_authority)
    )
