"""配置模块 - 仅导出 MCP 使用的配置"""

from .settings import Settings, get_settings, get_settings_with_env

settings = get_settings()

__all__ = ["Settings", "get_settings", "get_settings_with_env", "settings"]
