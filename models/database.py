"""数据库模型基类"""
from datetime import datetime
from typing import Any, Dict, Optional
import uuid

from sqlalchemy import DateTime, String, Column, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field


# SQLAlchemy基类
Base = declarative_base()


class BaseTable(Base):
    """数据库表基类"""
    
    __abstract__ = True
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, 
        default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """从字典更新"""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now()


class BaseModel(BaseModel):
    """Pydantic模型基类"""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        """Pydantic配置"""
        from_attributes = True
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
    
    def model_dump_dict(self) -> Dict[str, Any]:
        """转换为字典（兼容方法）"""
        return self.model_dump()
    
    @classmethod
    def from_orm_instance(cls, orm_instance: Any) -> "BaseModel":
        """从ORM实例创建"""
        return cls.model_validate(orm_instance)


class TimestampMixin:
    """时间戳混入类"""
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def touch(self) -> None:
        """更新时间戳"""
        self.updated_at = datetime.now()


class PaginationParams(BaseModel):
    """分页参数"""
    
    page: int = Field(default=1, ge=1, description="页码")
    size: int = Field(default=20, ge=1, le=100, description="每页大小")
    
    @property
    def offset(self) -> int:
        """计算偏移量"""
        return (self.page - 1) * self.size
    
    @property
    def limit(self) -> int:
        """计算限制数"""
        return self.size


class PaginationResult(BaseModel):
    """分页结果"""
    
    items: list[Any] = Field(description="数据项")
    total: int = Field(description="总数")
    page: int = Field(description="当前页")
    size: int = Field(description="每页大小")
    pages: int = Field(description="总页数")
    
    @classmethod
    def create(
        cls,
        items: list[Any],
        total: int,
        pagination: PaginationParams
    ) -> "PaginationResult":
        """创建分页结果"""
        pages = (total + pagination.size - 1) // pagination.size
        return cls(
            items=items,
            total=total,
            page=pagination.page,
            size=pagination.size,
            pages=pages
        )


class SortParams(BaseModel):
    """排序参数"""
    
    field: str = Field(description="排序字段")
    order: str = Field(default="asc", regex="^(asc|desc)$", description="排序方向")
    
    @property
    def is_ascending(self) -> bool:
        """是否升序"""
        return self.order.lower() == "asc"
    
    @property
    def is_descending(self) -> bool:
        """是否降序"""
        return self.order.lower() == "desc"


class FilterParams(BaseModel):
    """过滤参数基类"""
    
    def to_filter_dict(self) -> Dict[str, Any]:
        """转换为过滤字典"""
        return {
            k: v for k, v in self.model_dump().items()
            if v is not None
        }


class APIResponse(BaseModel):
    """API响应基类"""
    
    success: bool = Field(description="是否成功")
    message: str = Field(default="", description="响应消息")
    data: Optional[Any] = Field(default=None, description="响应数据")
    error_code: Optional[str] = Field(default=None, description="错误代码")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    
    @classmethod
    def success_response(
        cls, 
        data: Optional[Any] = None, 
        message: str = "操作成功"
    ) -> "APIResponse":
        """创建成功响应"""
        return cls(
            success=True,
            message=message,
            data=data
        )
    
    @classmethod
    def error_response(
        cls, 
        message: str = "操作失败", 
        error_code: Optional[str] = None
    ) -> "APIResponse":
        """创建错误响应"""
        return cls(
            success=False,
            message=message,
            error_code=error_code
        )


class ValidationError(Exception):
    """验证错误"""
    
    def __init__(self, message: str, field: Optional[str] = None):
        self.message = message
        self.field = field
        super().__init__(message)


class DatabaseError(Exception):
    """数据库错误"""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(message)


class NotFoundError(Exception):
    """未找到错误"""
    
    def __init__(self, resource: str, identifier: str):
        self.resource = resource
        self.identifier = identifier
        message = f"{resource} with id '{identifier}' not found"
        super().__init__(message) 