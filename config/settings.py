"""应用配置 - 仅保留 MCP 实际使用的项"""
import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """MCP 应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "project-management-mcp"
    app_version: str = "1.0.0"
    log_level: str = "INFO"

    # 后端 API（可从环境变量覆盖）
    api_base_url: str = "http://localhost:8080/aiProject/api"
    api_key: Optional[str] = None

    # MCP/Channel
    channel_no: Optional[str] = None

    # WebSocket 客户端已拆至独立项目 ai_project_ws_client，此处不再保留相关配置


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


# 兼容：从环境变量补全
def get_settings_with_env() -> Settings:
    """获取配置，并用环境变量覆盖未在 .env 中设置的项"""
    s = get_settings()
    return Settings(
        api_base_url=os.getenv("API_BASE_URL") or s.api_base_url,
        api_key=os.getenv("API_KEY") or s.api_key,
        channel_no=os.getenv("CHANNEL_NO") or s.channel_no,
        log_level=os.getenv("LOG_LEVEL") or s.log_level,
    )
