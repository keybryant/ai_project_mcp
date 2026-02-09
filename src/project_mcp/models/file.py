"""文件数据模型"""
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, JSON, Index
from pydantic import Field, validator

from .database import BaseTable, BaseModel as PydanticBaseModel
from ..config.constants import FileStatus


class FileTable(BaseTable):
    """文件数据库表"""
    
    __tablename__ = "files"
    
    # 文件基本信息
    name = Column(String(255), nullable=False, index=True)
    path = Column(String(1000), nullable=False, index=True)
    relative_path = Column(String(1000), nullable=True)
    size = Column(Integer, nullable=False, default=0)
    mime_type = Column(String(100), nullable=True)
    
    # 文件状态
    status = Column(String(50), nullable=False, default=FileStatus.LOCAL)
    hash = Column(String(64), nullable=True, index=True)
    
    # 关联信息
    project_id = Column(String(36), nullable=True, index=True)
    category = Column(String(100), nullable=True, index=True)
    
    # 远程信息
    remote_id = Column(String(36), nullable=True)
    remote_url = Column(String(1000), nullable=True)
    download_url = Column(String(1000), nullable=True)
    
    # 同步信息
    last_sync_at = Column(DateTime, nullable=True)
    sync_error = Column(Text, nullable=True)
    
    # 元数据
    metadata = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)
    
    # 版本信息
    version = Column(Integer, nullable=False, default=1)
    parent_file_id = Column(String(36), nullable=True)
    
    # 状态标志
    is_deleted = Column(Boolean, nullable=False, default=False)
    is_archived = Column(Boolean, nullable=False, default=False)
    
    # 索引
    __table_args__ = (
        Index('idx_file_path', 'path'),
        Index('idx_file_project', 'project_id'),
        Index('idx_file_status', 'status'),
        Index('idx_file_category', 'category'),
        Index('idx_file_hash', 'hash'),
        Index('idx_file_sync', 'last_sync_at'),
    )


class FileInfo(PydanticBaseModel):
    """文件信息Pydantic模型"""
    
    # 文件基本信息
    name: str = Field(description="文件名")
    path: str = Field(description="文件路径")
    relative_path: Optional[str] = Field(default=None, description="相对路径")
    size: int = Field(default=0, description="文件大小（字节）")
    mime_type: Optional[str] = Field(default=None, description="MIME类型")
    
    # 文件状态
    status: FileStatus = Field(default=FileStatus.LOCAL, description="文件状态")
    hash: Optional[str] = Field(default=None, description="文件哈希")
    
    # 关联信息
    project_id: Optional[str] = Field(default=None, description="项目ID")
    category: Optional[str] = Field(default=None, description="文件分类")
    
    # 远程信息
    remote_id: Optional[str] = Field(default=None, description="远程文件ID")
    remote_url: Optional[str] = Field(default=None, description="远程文件URL")
    download_url: Optional[str] = Field(default=None, description="下载URL")
    
    # 同步信息
    last_sync_at: Optional[datetime] = Field(default=None, description="最后同步时间")
    sync_error: Optional[str] = Field(default=None, description="同步错误信息")
    
    # 元数据
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="文件元数据")
    tags: Optional[list[str]] = Field(default=None, description="文件标签")
    
    # 版本信息
    version: int = Field(default=1, description="文件版本")
    parent_file_id: Optional[str] = Field(default=None, description="父文件ID")
    
    # 状态标志
    is_deleted: bool = Field(default=False, description="是否已删除")
    is_archived: bool = Field(default=False, description="是否已归档")
    
    @validator("path")
    def validate_path(cls, v):
        """验证文件路径"""
        if not v:
            raise ValueError("文件路径不能为空")
        # 标准化路径
        return str(Path(v).resolve())
    
    @validator("size")
    def validate_size(cls, v):
        """验证文件大小"""
        if v < 0:
            raise ValueError("文件大小不能为负数")
        return v
    
    @validator("version")
    def validate_version(cls, v):
        """验证版本号"""
        if v < 1:
            raise ValueError("版本号必须大于0")
        return v
    
    @property
    def file_extension(self) -> str:
        """文件扩展名"""
        return Path(self.name).suffix.lower()
    
    @property
    def file_stem(self) -> str:
        """文件名（不含扩展名）"""
        return Path(self.name).stem
    
    @property
    def size_human(self) -> str:
        """人类可读的文件大小"""
        size = self.size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
    
    @property
    def is_text_file(self) -> bool:
        """是否为文本文件"""
        text_extensions = {
            '.txt', '.md', '.py', '.js', '.json', '.xml', '.html', 
            '.css', '.yaml', '.yml', '.toml', '.ini', '.cfg'
        }
        return self.file_extension in text_extensions
    
    @property
    def is_image_file(self) -> bool:
        """是否为图片文件"""
        image_extensions = {
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'
        }
        return self.file_extension in image_extensions
    
    @property
    def is_document_file(self) -> bool:
        """是否为文档文件"""
        doc_extensions = {
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'
        }
        return self.file_extension in doc_extensions
    
    @property
    def needs_sync(self) -> bool:
        """是否需要同步"""
        return self.status in [FileStatus.LOCAL, FileStatus.MODIFIED]


class FileCreate(PydanticBaseModel):
    """创建文件请求模型"""
    
    name: str = Field(description="文件名")
    path: str = Field(description="文件路径")
    project_id: Optional[str] = Field(default=None, description="项目ID")
    category: Optional[str] = Field(default=None, description="文件分类")
    tags: Optional[list[str]] = Field(default=None, description="文件标签")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="文件元数据")


class FileUpdate(PydanticBaseModel):
    """更新文件请求模型"""
    
    name: Optional[str] = Field(default=None, description="文件名")
    project_id: Optional[str] = Field(default=None, description="项目ID")
    category: Optional[str] = Field(default=None, description="文件分类")
    status: Optional[FileStatus] = Field(default=None, description="文件状态")
    tags: Optional[list[str]] = Field(default=None, description="文件标签")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="文件元数据")
    is_archived: Optional[bool] = Field(default=None, description="是否已归档")


class FileFilter(PydanticBaseModel):
    """文件过滤参数"""
    
    project_id: Optional[str] = Field(default=None, description="项目ID")
    category: Optional[str] = Field(default=None, description="文件分类")
    status: Optional[FileStatus] = Field(default=None, description="文件状态")
    file_type: Optional[str] = Field(default=None, description="文件类型")
    is_archived: Optional[bool] = Field(default=None, description="是否已归档")
    is_deleted: Optional[bool] = Field(default=None, description="是否已删除")
    keyword: Optional[str] = Field(default=None, description="关键词搜索")
    size_min: Optional[int] = Field(default=None, description="最小文件大小")
    size_max: Optional[int] = Field(default=None, description="最大文件大小")
    modified_after: Optional[datetime] = Field(default=None, description="修改时间之后")
    modified_before: Optional[datetime] = Field(default=None, description="修改时间之前")


class FileSummary(PydanticBaseModel):
    """文件摘要信息"""
    
    id: str
    name: str
    path: str
    size: int
    size_human: str
    mime_type: Optional[str]
    status: FileStatus
    project_id: Optional[str]
    category: Optional[str]
    last_sync_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class FileUploadRequest(PydanticBaseModel):
    """文件上传请求"""
    
    file_paths: list[str] = Field(description="文件路径列表")
    project_id: Optional[str] = Field(default=None, description="项目ID")
    category: Optional[str] = Field(default=None, description="文件分类")
    overwrite: bool = Field(default=False, description="是否覆盖已存在文件")


class FileUploadResponse(PydanticBaseModel):
    """文件上传响应"""
    
    success: list[str] = Field(description="上传成功的文件")
    failed: list[Dict[str, str]] = Field(description="上传失败的文件")
    total: int = Field(description="总文件数")
    
    @property
    def success_count(self) -> int:
        """成功上传数量"""
        return len(self.success)
    
    @property
    def failed_count(self) -> int:
        """失败上传数量"""
        return len(self.failed)
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total == 0:
            return 0.0
        return (self.success_count / self.total) * 100


class FileDownloadRequest(PydanticBaseModel):
    """文件下载请求"""
    
    file_id: str = Field(description="文件ID")
    save_path: Optional[str] = Field(default=None, description="保存路径")


class FileContentRequest(PydanticBaseModel):
    """文件内容请求"""
    
    file_path: str = Field(description="文件路径")
    encoding: str = Field(default="utf-8", description="文件编码")
    max_size: Optional[int] = Field(default=None, description="最大读取大小")


class FileContentResponse(PydanticBaseModel):
    """文件内容响应"""
    
    content: str = Field(description="文件内容")
    encoding: str = Field(description="文件编码")
    size: int = Field(description="文件大小")
    is_binary: bool = Field(description="是否为二进制文件")
    mime_type: Optional[str] = Field(description="MIME类型") 