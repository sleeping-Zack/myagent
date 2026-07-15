import hashlib
import ipaddress
import re
from datetime import date
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
    normalized = re.sub(r"\s+", "", text.lower())

    direct_dangerous_patterns = [
        r"忽略.{0,12}(此前|之前|以上).{0,8}(指令|规则|要求)",
        r"ignore.{0,20}(previous|prior).{0,12}(instruction|prompt)",
        r"(未公开|私有|隐藏).{0,10}(信息|资料|内容)",
        r"(api[ _-]?key|密码|私钥|ssh|服务器凭据)",
    ]
    if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in direct_dangerous_patterns):
        return False

    extraction_intent = re.search(
        r"打开|读取|查看|展示|显示|输出|导出|列(?:出|一下)|返回|发送|发给我|"
        r"复述|总结|目录|列表|有哪些(?:文档|文件|内容)|"
        r"都写了什么|写了什么|完整内容|全部内容|原文|全文",
        normalized,
        re.IGNORECASE,
    )
    if not extraction_intent:
        return True

    protected_resource = re.search(
        r"知识库|资料库|文档库|内部(?:文档|文件|资料)|私有(?:文档|文件|资料)|"
        r"提示词|系统提示词|systemprompt|开发者指令|(?:hr|面试)问答(?:文档|文件)?|"
        r"(?:knowledge|prompts?)[\\/]",
        normalized,
        re.IGNORECASE,
    )
    file_reference = re.search(
        r"(?:[\w\u4e00-\u9fff.-]+[\\/])+[\w\u4e00-\u9fff.-]+|"
        r"[\w\u4e00-\u9fff.-]+\.[a-z][a-z0-9_-]{0,11}(?![a-z0-9])",
        normalized,
        re.IGNORECASE,
    )
    generic_file_target = re.search(r"文档|文件", normalized)

    return not (protected_resource or file_reference or generic_file_target)
