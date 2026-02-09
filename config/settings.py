"""应用配置设置"""
import os
from pathlib import Path
from typing import List, Optional
from functools import lru_cache

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置类"""
    
    # 应用基础配置
    app_name: str = Field(default="project-management-mcp", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    app_env: str = Field(default="development", env="APP_ENV")
    debug: bool = Field(default=False, env="DEBUG")
    
    # 后台API服务配置
    api_base_url: str = Field(default="http://localhost:8000", env="API_BASE_URL")
    api_timeout: int = Field(default=30, env="API_TIMEOUT")
    api_retry_count: int = Field(default=3, env="API_RETRY_COUNT")
    
    # 认证配置
    api_key: Optional[str] = Field(default=None, env="API_KEY")
    api_secret: Optional[str] = Field(default=None, env="API_SECRET")
    jwt_secret_key: str = Field(default="your-secret-key", env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=30, env="JWT_EXPIRE_MINUTES")
    
    # 数据库配置
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/projects.db", 
        env="DATABASE_URL"
    )
    database_echo: bool = Field(default=False, env="DATABASE_ECHO")
    
    # 文件存储配置
    data_dir: str = Field(default="./data", env="DATA_DIR")
    files_dir: str = Field(default="./data/files", env="FILES_DIR")
    cache_dir: str = Field(default="./data/cache", env="CACHE_DIR")
    logs_dir: str = Field(default="./data/logs", env="LOGS_DIR")
    max_file_size: str = Field(default="100MB", env="MAX_FILE_SIZE")
    allowed_file_types: str = Field(
        default=".txt,.md,.py,.js,.json,.xml,.html,.pdf,.doc,.docx",
        env="ALLOWED_FILE_TYPES"
    )
    
    # 日志配置
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(
        default="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        env="LOG_FORMAT"
    )
    log_rotation: str = Field(default="10 MB", env="LOG_ROTATION")
    log_retention: str = Field(default="30 days", env="LOG_RETENTION")
    
    # MCP服务器配置
    mcp_server_name: str = Field(default="project-management-mcp", env="MCP_SERVER_NAME")
    mcp_server_version: str = Field(default="1.0.0", env="MCP_SERVER_VERSION")
    mcp_stdio_buffer_size: int = Field(default=1024, env="MCP_STDIO_BUFFER_SIZE")
    channel_no: Optional[str] = Field(default=None, env="CHANNEL_NO")
    
    # 同步配置
    sync_interval: int = Field(default=300, env="SYNC_INTERVAL")  # 秒
    auto_sync_enabled: bool = Field(default=True, env="AUTO_SYNC_ENABLED")
    sync_batch_size: int = Field(default=10, env="SYNC_BATCH_SIZE")
    
    # 缓存配置
    cache_enabled: bool = Field(default=True, env="CACHE_ENABLED")
    cache_ttl: int = Field(default=3600, env="CACHE_TTL")  # 秒
    cache_max_size: int = Field(default=1000, env="CACHE_MAX_SIZE")
    
    # 通知配置
    notification_enabled: bool = Field(default=True, env="NOTIFICATION_ENABLED")
    email_enabled: bool = Field(default=False, env="EMAIL_ENABLED")
    email_host: Optional[str] = Field(default=None, env="EMAIL_HOST")
    email_port: Optional[int] = Field(default=None, env="EMAIL_PORT")
    email_user: Optional[str] = Field(default=None, env="EMAIL_USER")
    email_password: Optional[str] = Field(default=None, env="EMAIL_PASSWORD")
    email_from: Optional[str] = Field(default=None, env="EMAIL_FROM")
    
    # 性能配置
    max_concurrent_requests: int = Field(default=10, env="MAX_CONCURRENT_REQUESTS")
    request_timeout: int = Field(default=30, env="REQUEST_TIMEOUT")
    connection_pool_size: int = Field(default=20, env="CONNECTION_POOL_SIZE")
    
    # 安全配置
    cors_enabled: bool = Field(default=True, env="CORS_ENABLED")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        env="CORS_ORIGINS"
    )
    rate_limit_enabled: bool = Field(default=True, env="RATE_LIMIT_ENABLED")
    rate_limit_requests: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    rate_limit_period: int = Field(default=60, env="RATE_LIMIT_PERIOD")
    
    # 开发配置
    reload_on_change: bool = Field(default=False, env="RELOAD_ON_CHANGE")
    profiling_enabled: bool = Field(default=False, env="PROFILING_ENABLED")
    metrics_enabled: bool = Field(default=False, env="METRICS_ENABLED")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @validator("data_dir", "files_dir", "cache_dir", "logs_dir", pre=True)
    def validate_directories(cls, v: str) -> str:
        """验证并创建目录"""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return str(path.absolute())
    
    @validator("allowed_file_types", pre=True)
    def parse_file_types(cls, v) -> str:
        """解析文件类型字符串"""
        if isinstance(v, list):
            return ",".join(v)
        return str(v)
    
    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v) -> List[str]:
        """解析CORS源列表"""
        if isinstance(v, str):
            # 移除方括号并分割
            v = v.strip("[]")
            return [origin.strip().strip('"') for origin in v.split(",")]
        elif isinstance(v, list):
            return v
        return [str(v)]
    
    @validator("max_file_size", pre=True)
    def parse_file_size(cls, v) -> str:
        """解析文件大小字符串"""
        if isinstance(v, int):
            # 如果是整数，转换为MB字符串
            return f"{v // (1024 * 1024)}MB"
        return str(v)
    
    @property
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.app_env.lower() in ("development", "dev")
    
    @property
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.app_env.lower() in ("production", "prod")
    
    @property
    def is_testing(self) -> bool:
        """是否为测试环境"""
        return self.app_env.lower() in ("testing", "test")
    
    @property
    def database_file_path(self) -> Path:
        """数据库文件路径"""
        if self.database_url.startswith("sqlite"):
            # 提取SQLite文件路径
            file_path = self.database_url.split("///")[-1]
            return Path(file_path)
        raise ValueError("Only SQLite databases are supported")
    
    @property
    def log_file_path(self) -> Path:
        """日志文件路径"""
        return Path(self.logs_dir) / "app.log"
    
    @property
    def error_log_file_path(self) -> Path:
        """错误日志文件路径"""
        return Path(self.logs_dir) / "error.log"
    
    def get_full_api_url(self, endpoint: str) -> str:
        """获取完整的API URL"""
        base_url = self.api_base_url.rstrip("/")
        endpoint = endpoint.lstrip("/")
        return f"{base_url}/{endpoint}"
    
    def get_file_path(self, category: str, filename: str) -> Path:
        """获取文件存储路径"""
        base_path = Path(self.files_dir)
        category_path = base_path / category
        category_path.mkdir(parents=True, exist_ok=True)
        return category_path / filename
    
    @property
    def allowed_file_types_list(self) -> List[str]:
        """获取允许的文件类型列表"""
        return [ext.strip() for ext in self.allowed_file_types.split(",")]
    
    def is_file_type_allowed(self, filename: str) -> bool:
        """检查文件类型是否允许"""
        file_ext = Path(filename).suffix.lower()
        return file_ext in self.allowed_file_types_list


@lru_cache()
def get_settings() -> Settings:
    """获取配置实例（单例模式）"""
    return Settings()


# 便捷的配置访问
settings = get_settings() 