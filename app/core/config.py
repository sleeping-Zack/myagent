from pydantic_settings import BaseSettings
from typing import Optional
from urllib.parse import urlparse


class Settings(BaseSettings):
    # 应用基础
    app_env: str = "development"
    app_name: str = "朱旭个人Agent"
    site_url: str = "http://47.116.25.89"
    allowed_hosts: str = ""
    trusted_proxy_ips: str = "127.0.0.1,::1"
    secret_key: str = ""
    debug: bool = False

    # 数据库
    database_url: str = "postgresql+asyncpg://personal_agent:password@localhost:5432/personal_agent"

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 2

    # Embedding — mode: "local" 或 "api"
    embedding_mode: str = "api"
    embedding_model_path: str = "/app/models/bge-small-zh-v1.5"
    embedding_device: str = "cpu"
    # API 模式：兼容 OpenAI Embeddings 接口
    embedding_api_key: str = ""
    embedding_api_base_url: str = "https://api.siliconflow.cn/v1"
    embedding_api_model: str = "BAAI/bge-large-zh-v1.5"
    embedding_dimensions: int = 1024

    # RAG 参数
    max_question_length: int = 500
    max_context_chunks: int = 5
    retrieval_top_k: int = 10
    min_relevance_score: float = 0.40

    # 限流
    chat_daily_limit: int = 500
    chat_ip_minute_limit: int = 30
    chat_visitor_minute_limit: int = 5
    feedback_daily_limit: int = 500
    feedback_ip_minute_limit: int = 10
    visitor_create_ip_minute_limit: int = 10
    visitor_create_daily_limit: int = 500
    conversation_create_ip_minute_limit: int = 10
    conversation_create_daily_limit: int = 200
    admin_failed_login_ip_minute_limit: int = 5

    # 匿名对话保留期限；设为 None 可关闭自动清理。
    conversation_retention_days: Optional[int] = 30
    visitor_session_days: int = 30
    visitor_cookie_name: str = "hr_session"
    memory_recent_message_limit: int = 8
    memory_recent_token_budget: int = 2500
    memory_summary_max_chars: int = 4000

    # 管理端
    admin_username: str = "admin"
    admin_password: str = ""
    admin_allowed_ips: str = ""

    # 日志
    log_level: str = "INFO"
    save_raw_ip: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    def csv_values(self, field_name: str) -> list[str]:
        return [
            value.strip()
            for value in getattr(self, field_name).split(",")
            if value.strip()
        ]

    def effective_allowed_hosts(self) -> list[str]:
        configured = self.csv_values("allowed_hosts")
        hostname = urlparse(self.site_url).hostname
        hosts = configured or ([hostname] if hostname else [])
        hosts.extend(["localhost", "127.0.0.1"])
        if self.app_env != "production":
            hosts.append("testserver")
        return list(dict.fromkeys(hosts))

    def validate_production(self) -> None:
        if self.app_env != "production":
            return
        errors: list[str] = []
        if urlparse(self.site_url).scheme != "https":
            errors.append("SITE_URL must use https in production")
        if len(self.secret_key) < 32 or self.secret_key == "change_this_secret_key_in_production":
            errors.append("SECRET_KEY must be a production secret of at least 32 characters")
        if ":password@" in self.database_url:
            errors.append("DATABASE_URL still uses the default password")
        if not self.effective_allowed_hosts():
            errors.append("ALLOWED_HOSTS or a valid SITE_URL is required")
        if errors:
            raise RuntimeError("Unsafe production configuration: " + "; ".join(errors))


settings = Settings()


def get_settings() -> Settings:
    return settings
