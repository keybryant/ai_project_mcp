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

    # 本地 Cursor 控制（WebSocket 收到命令时由 cursor_controller 执行）
    cursor_exe: str = "cursor"
    cursor_ui_timeout: int = 15
    cursor_send_hotkey: str = "Enter"
    cursor_open_agent_hotkey: str = "Ctrl+Shift+L"
    # WebSocket 客户端（与 MCP 同时启动时连接后端，接收 create_folder/open_cursor/write_and_send 等命令）
    # 环境变量: CURSOR_WS_URL / CURSOR_BACKEND_ADDRESS / CURSOR_WS_NAME / RECONNECT_INTERVAL
    cursor_ws_url: str = ""  # 完整地址，如 ws://localhost:8080/ws/ai-tool；若为空则用 cursor_backend_address 拼接
    cursor_backend_address: str = "43.139.194.139/aiProject"  # 仅 host:port 或带协议，如 localhost:8080 或 http://43.139.194.139/aiProject；会拼成 ws://.../ws/ai-tool
    cursor_ws_name: str = "cursor"  # WebSocket 连接时携带的客户端名称（查询参数 name）
    reconnect_interval: float = 5.0  # 断线重连间隔（秒）


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
