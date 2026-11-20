# -*- coding: utf-8 -*-
"""全局配置。支持 .env 覆盖。"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # server/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    APP_NAME: str = "知寻 KnowSeek 后端服务"
    APP_VERSION: str = "1.0.0"

    # 数据库（默认 SQLite；可切 PostgreSQL，代码不依赖 SQLite 专有语法）
    # 相对路径基于 BASE_DIR（server/），随项目目录迁移无需改配置
    DATABASE_URL: str = f"sqlite:///{(BASE_DIR / 'ai_assistant.db').as_posix()}"

    # 向量库
    CHROMA_DIR: str = str((BASE_DIR / "chroma_data").as_posix())
    VECTOR_COLLECTION: str = "kb_default"

    # JWT
    JWT_SECRET: str = "knowseek-dev-secret-change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # QQ 邮箱 SMTP
    MAIL_HOST: str = "smtp.qq.com"
    MAIL_PORT: int = 465
    MAIL_USER: str = ""
    MAIL_PASS: str = ""
    MAIL_FROM: str = ""
    EMAIL_CODE_EXPIRE_MINUTES: int = 5
    EMAIL_SEND_INTERVAL_SECONDS: int = 60

    # DeepSeek（OpenAI 兼容）
    DEEPSEEK_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-chat"
    LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_TIMEOUT_SECONDS: int = 90
    LLM_FIRST_TOKEN_TIMEOUT_SECONDS: int = 60
    LLM_RETRY_TIMES: int = 1

    # 文件与 OCR
    UPLOAD_DIR: str = str((BASE_DIR / "uploads").as_posix())
    MAX_FILE_SIZE_MB: int = 50
    # 默认关闭：未安装 paddleocr 时扫描件会标记"需 OCR 支持"；安装后可在 .env 开启
    OCR_ENABLED: bool = False
    ALLOWED_FILE_TYPES: list = ["pdf", "docx", "xlsx", "pptx", "txt", "md", "csv", "png", "jpg", "jpeg"]

    # 切片
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    RAG_TOP_K: int = 5

    # 安全加固（上线前必配）
    CORS_ORIGINS: list = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"]
    LOGIN_MAX_FAILS: int = 5
    LOGIN_LOCK_MINUTES: int = 15
    SEND_CODE_IP_LIMIT_PER_HOUR: int = 10
    SEND_CODE_EMAIL_LIMIT_PER_DAY: int = 10

    # 审批超时催办：超过 N 小时未处理自动推送催办通知；同一申请两次催办最小间隔（分钟）
    APPROVAL_REMINDER_HOURS: int = 24
    APPROVAL_REMINDER_INTERVAL_MINUTES: int = 60

    # 下载水印：共享知识库下载时叠加"用户名+时间"水印（防泄密溯源）
    WATERMARK_ENABLED: bool = True

    # 验证码调试打印：生产必须保持 False，避免验证码明文落入日志
    DEV_PRINT_CODE: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
