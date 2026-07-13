import hashlib
import re
from datetime import date
from app.core.config import settings


def hash_ip(ip: str) -> str:
    """日级别盐值哈希IP，用于限流而不存储原始IP"""
    daily_salt = str(date.today())
    return hashlib.sha256(f"{ip}{daily_salt}{settings.secret_key}".encode()).hexdigest()[:16]


def is_safe_question(text: str) -> bool:
    """拒绝明显的越权、提示词导出和批量知识库导出请求。"""
    dangerous_patterns = [
        r"忽略.{0,12}(此前|之前|以上).{0,8}(指令|规则|要求)",
        r"ignore.{0,20}(previous|prior).{0,12}(instruction|prompt)",
        r"(输出|显示|泄露|告诉我).{0,12}(系统提示词|system prompt|开发者指令)",
        r"(列出|导出|返回).{0,12}(全部|所有|完整).{0,12}(知识库|原文|文档)",
        r"(未公开|私有|隐藏).{0,10}(信息|资料|内容)",
        r"(api[ _-]?key|密码|私钥|ssh|服务器凭据)",
    ]
    lower = text.lower()
    return not any(re.search(pattern, lower, re.IGNORECASE) for pattern in dangerous_patterns)
