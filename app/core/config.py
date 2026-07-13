from pydantic_settings import BaseSettings
from typing import Optional
import secrets


class Settings(BaseSettings):
    # 应用基础
    app_env: str = "development"
    app_name: str = "朱旭个人Agent"
    site_url: str = "http://47.116.25.89"
    secret_key: str = secrets.token_urlsafe(32)
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
    min_relevance_score: float = 0.45

    # 限流
    chat_daily_limit: int = 500
    chat_ip_minute_limit: int = 5
    feedback_daily_limit: int = 500
    feedback_ip_minute_limit: int = 10

    # 匿名对话保留期限；设为 None 可关闭自动清理。
    conversation_retention_days: Optional[int] = 30

    # 日志
    log_level: str = "INFO"
    save_raw_ip: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()


def get_settings() -> Settings:
    return settings
