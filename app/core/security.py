import hashlib
from datetime import date
from app.core.config import settings


def hash_ip(ip: str) -> str:
    """日级别盐值哈希IP，用于限流而不存储原始IP"""
    daily_salt = str(date.today())
    return hashlib.sha256(f"{ip}{daily_salt}{settings.secret_key}".encode()).hexdigest()[:16]


def is_safe_question(text: str) -> bool:
    """基础敏感词检测"""
    dangerous_patterns = [
        "忽略此前", "ignore previous", "你现在是", "system prompt",
        "api key", "密码", "ssh", "服务器地址",
    ]
    lower = text.lower()
    return not any(p in lower for p in dangerous_patterns)
