"""应用常量定义"""
from enum import Enum


class ProjectStatus(str, Enum):
    """项目状态枚举"""
    DRAFT = "draft"                    # 草稿
    REQUIREMENT_ANALYSIS = "requirement_analysis"  # 需求分析
    PROTOTYPE_DESIGN = "prototype_design"          # 原型设计
    DEVELOPMENT = "development"                    # 开发中
    TESTING = "testing"                           # 测试中
    DEPLOYMENT = "deployment"                     # 部署中
    OPERATION = "operation"                       # 运维中
    COMPLETED = "completed"                       # 已完成
    SUSPENDED = "suspended"                       # 暂停
    CANCELLED = "cancelled"                       # 取消


class FileStatus(str, Enum):
    """文件状态枚举"""
    LOCAL = "local"                    # 仅本地
    UPLOADING = "uploading"           # 上传中
    SYNCED = "synced"                 # 已同步
    MODIFIED = "modified"             # 已修改
    CONFLICT = "conflict"             # 冲突
    ERROR = "error"                   # 错误


class SyncDirection(str, Enum):
    """同步方向枚举"""
    DOWNLOAD = "download"             # 下载
    UPLOAD = "upload"                 # 上传
    BIDIRECTIONAL = "bidirectional"   # 双向同步


class WorkflowStage(str, Enum):
    """工作流阶段枚举"""
    REQUIREMENT = "requirement"       # 需求分析阶段
    PROTOTYPE = "prototype"           # 产品原型阶段
    DEVELOPMENT = "development"       # 开发完成阶段
    OPERATION = "operation"           # 运维验收阶段


class PaymentStatus(str, Enum):
    """付费状态枚举"""
    PENDING = "pending"               # 待付费
    PARTIAL = "partial"               # 部分付费
    PAID = "paid"                     # 已付费
    OVERDUE = "overdue"               # 逾期
    REFUNDED = "refunded"             # 已退款


class NotificationType(str, Enum):
    """通知类型枚举"""
    INFO = "info"                     # 信息
    WARNING = "warning"               # 警告
    ERROR = "error"                   # 错误
    SUCCESS = "success"               # 成功


class LogLevel(str, Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# MCP相关常量
class MCPConstants:
    """MCP协议相关常量"""
    
    # 工具名称
    TOOL_SYNC_PROJECT_DATA = "sync_project_data"
    
    # 资源URI前缀
    URI_PROJECT_PREFIX = "project://"
    URI_FILE_PREFIX = "file://"
    URI_DOCUMENT_PREFIX = "document://"
    
    # 支持的MIME类型
    MIME_TYPES = {
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".py": "text/x-python",
        ".js": "application/javascript",
        ".json": "application/json",
        ".xml": "application/xml",
        ".html": "text/html",
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }


# API相关常量
class APIConstants:
    """API相关常量"""
    
    # API端点
    PROJECTS_ENDPOINT = "/api/projects"
    FILES_ENDPOINT = "/api/files"
    UPLOAD_ENDPOINT = "/api/files/upload"
    DOWNLOAD_ENDPOINT = "/api/files/{file_id}/download"
    SYNC_ENDPOINT = "/api/sync"
    AUTH_ENDPOINT = "/api/auth"
    
    # HTTP状态码
    HTTP_OK = 200
    HTTP_CREATED = 201
    HTTP_BAD_REQUEST = 400
    HTTP_UNAUTHORIZED = 401
    HTTP_FORBIDDEN = 403
    HTTP_NOT_FOUND = 404
    HTTP_INTERNAL_ERROR = 500
    
    # 请求头
    HEADER_AUTHORIZATION = "Authorization"
    HEADER_CONTENT_TYPE = "Content-Type"
    HEADER_API_KEY = "X-API-Key"
    HEADER_USER_AGENT = "User-Agent"


# 数据库相关常量
class DatabaseConstants:
    """数据库相关常量"""
    
    # 表名
    TABLE_PROJECTS = "projects"
    TABLE_FILES = "files"
    TABLE_SYNC_RECORDS = "sync_records"
    TABLE_NOTIFICATIONS = "notifications"
    
    # 索引名
    INDEX_PROJECT_STATUS = "idx_project_status"
    INDEX_FILE_PATH = "idx_file_path"
    INDEX_SYNC_TIMESTAMP = "idx_sync_timestamp"


# 文件相关常量
class FileConstants:
    """文件相关常量"""
    
    # 文件分类
    CATEGORY_DOCUMENTS = "documents"
    CATEGORY_PROTOTYPES = "prototypes"
    CATEGORY_SOURCE_CODE = "source_code"
    CATEGORY_ASSETS = "assets"
    CATEGORY_EXPORTS = "exports"
    CATEGORY_CACHE = "cache"
    
    # 默认文件大小限制（字节）
    DEFAULT_MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    
    # 支持的文件扩展名
    ALLOWED_EXTENSIONS = {
        ".txt", ".md", ".py", ".js", ".json", ".xml", ".html",
        ".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".gif"
    }


# 缓存相关常量
class CacheConstants:
    """缓存相关常量"""
    
    # 缓存键前缀
    KEY_PROJECT = "project:"
    KEY_FILE = "file:"
    KEY_USER = "user:"
    KEY_SYNC = "sync:"
    
    # 默认TTL（秒）
    DEFAULT_TTL = 3600  # 1小时
    LONG_TTL = 24 * 3600  # 24小时
    SHORT_TTL = 300  # 5分钟


# 同步相关常量
class SyncConstants:
    """同步相关常量"""
    
    # 同步间隔（秒）
    DEFAULT_SYNC_INTERVAL = 300  # 5分钟
    MIN_SYNC_INTERVAL = 60      # 1分钟
    MAX_SYNC_INTERVAL = 3600    # 1小时
    
    # 批处理大小
    DEFAULT_BATCH_SIZE = 10
    MAX_BATCH_SIZE = 100
    
    # 重试配置
    MAX_RETRY_COUNT = 3
    RETRY_DELAY = 5  # 秒


# 通知相关常量
class NotificationConstants:
    """通知相关常量"""
    
    # 通知模板
    TEMPLATE_PROJECT_CREATED = "project_created"
    TEMPLATE_PROJECT_UPDATED = "project_updated"
    TEMPLATE_FILE_UPLOADED = "file_uploaded"
    TEMPLATE_SYNC_COMPLETED = "sync_completed"
    TEMPLATE_ERROR_OCCURRED = "error_occurred"
    
    # 通知渠道
    CHANNEL_EMAIL = "email"
    CHANNEL_WEBHOOK = "webhook"
    CHANNEL_LOG = "log"


# 错误相关常量
class ErrorConstants:
    """错误相关常量"""
    
    # 错误代码
    ERR_INVALID_CONFIG = "INVALID_CONFIG"
    ERR_DATABASE_CONNECTION = "DATABASE_CONNECTION"
    ERR_API_REQUEST_FAILED = "API_REQUEST_FAILED"
    ERR_FILE_NOT_FOUND = "FILE_NOT_FOUND"
    ERR_PERMISSION_DENIED = "PERMISSION_DENIED"
    ERR_SYNC_FAILED = "SYNC_FAILED"
    ERR_VALIDATION_FAILED = "VALIDATION_FAILED"
    
    # 错误消息
    MSG_INVALID_CONFIG = "配置无效"
    MSG_DATABASE_CONNECTION = "数据库连接失败"
    MSG_API_REQUEST_FAILED = "API请求失败"
    MSG_FILE_NOT_FOUND = "文件未找到"
    MSG_PERMISSION_DENIED = "权限不足"
    MSG_SYNC_FAILED = "同步失败"
    MSG_VALIDATION_FAILED = "数据验证失败"


# 正则表达式常量
class RegexConstants:
    """正则表达式常量"""
    
    # UUID格式
    UUID_PATTERN = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    
    # 邮箱格式
    EMAIL_PATTERN = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    # 文件名格式（禁止特殊字符）
    FILENAME_PATTERN = r'^[a-zA-Z0-9._-]+$'
    
    # API Key格式
    API_KEY_PATTERN = r'^[a-zA-Z0-9]{32,64}$'


# 默认值常量
class DefaultValues:
    """默认值常量"""
    
    # 分页
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    
    # 项目
    DEFAULT_PROJECT_NAME = "新项目"
    DEFAULT_PROJECT_DESCRIPTION = "项目描述"
    
    # 文件
    DEFAULT_FILE_CATEGORY = FileConstants.CATEGORY_DOCUMENTS
    
    # 用户代理
    DEFAULT_USER_AGENT = "project-management-mcp/1.0.0" 