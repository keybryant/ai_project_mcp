"""项目数据模型"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from decimal import Decimal

from sqlalchemy import Column, String, Text, DateTime, Numeric, Boolean, JSON, Index
from pydantic import Field, validator

from .database import BaseTable, BaseModel as PydanticBaseModel
from ..config.constants import ProjectStatus, WorkflowStage, PaymentStatus


class ProjectTable(BaseTable):
    """项目数据库表"""
    
    __tablename__ = "projects"
    
    # 基本信息
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default=ProjectStatus.DRAFT)
    
    # 客户信息
    customer_id = Column(String(36), nullable=True)
    customer_name = Column(String(255), nullable=True)
    customer_email = Column(String(255), nullable=True)
    customer_phone = Column(String(50), nullable=True)
    
    # 项目详情
    requirements = Column(Text, nullable=True)
    objectives = Column(Text, nullable=True)
    scope = Column(Text, nullable=True)
    
    # 时间规划
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    estimated_hours = Column(Numeric(10, 2), nullable=True)
    
    # 工作流阶段
    current_stage = Column(String(50), nullable=True)
    stage_progress = Column(JSON, nullable=True)  # {"requirement": 100, "prototype": 50, ...}
    
    # 付费信息
    total_amount = Column(Numeric(10, 2), nullable=True)
    paid_amount = Column(Numeric(10, 2), nullable=True, default=0)
    payment_status = Column(String(50), nullable=False, default=PaymentStatus.PENDING)
    
    # 技术栈
    technologies = Column(JSON, nullable=True)  # ["Python", "React", ...]
    platform = Column(String(100), nullable=True)
    
    # 部署信息
    repository_url = Column(String(500), nullable=True)
    deployment_url = Column(String(500), nullable=True)
    domain = Column(String(255), nullable=True)
    
    # 元数据
    metadata = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)
    priority = Column(String(20), nullable=True, default="medium")
    
    # 状态标志
    is_active = Column(Boolean, nullable=False, default=True)
    is_archived = Column(Boolean, nullable=False, default=False)
    
    # 索引
    __table_args__ = (
        Index('idx_project_status', 'status'),
        Index('idx_project_customer', 'customer_id'),
        Index('idx_project_stage', 'current_stage'),
        Index('idx_project_active', 'is_active'),
    )


class Project(PydanticBaseModel):
    """项目Pydantic模型"""
    
    # 基本信息
    name: str = Field(description="项目名称")
    description: Optional[str] = Field(default=None, description="项目描述")
    status: ProjectStatus = Field(default=ProjectStatus.DRAFT, description="项目状态")
    
    # 客户信息
    customer_id: Optional[str] = Field(default=None, description="客户ID")
    customer_name: Optional[str] = Field(default=None, description="客户姓名")
    customer_email: Optional[str] = Field(default=None, description="客户邮箱")
    customer_phone: Optional[str] = Field(default=None, description="客户电话")
    
    # 项目详情
    requirements: Optional[str] = Field(default=None, description="需求描述")
    objectives: Optional[str] = Field(default=None, description="项目目标")
    scope: Optional[str] = Field(default=None, description="项目范围")
    
    # 时间规划
    start_date: Optional[datetime] = Field(default=None, description="开始日期")
    end_date: Optional[datetime] = Field(default=None, description="结束日期")
    estimated_hours: Optional[Decimal] = Field(default=None, description="预估工时")
    
    # 工作流阶段
    current_stage: Optional[WorkflowStage] = Field(default=None, description="当前阶段")
    stage_progress: Optional[Dict[str, int]] = Field(default=None, description="阶段进度")
    
    # 付费信息
    total_amount: Optional[Decimal] = Field(default=None, description="总金额")
    paid_amount: Optional[Decimal] = Field(default=Decimal("0"), description="已付金额")
    payment_status: PaymentStatus = Field(default=PaymentStatus.PENDING, description="付费状态")
    
    # 技术栈
    technologies: Optional[List[str]] = Field(default=None, description="技术栈")
    platform: Optional[str] = Field(default=None, description="平台")
    
    # 部署信息
    repository_url: Optional[str] = Field(default=None, description="代码仓库URL")
    deployment_url: Optional[str] = Field(default=None, description="部署URL")
    domain: Optional[str] = Field(default=None, description="域名")
    
    # 元数据
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="元数据")
    tags: Optional[List[str]] = Field(default=None, description="标签")
    priority: str = Field(default="medium", description="优先级")
    
    # 状态标志
    is_active: bool = Field(default=True, description="是否活跃")
    is_archived: bool = Field(default=False, description="是否归档")
    
    @validator("customer_email")
    def validate_email(cls, v):
        """验证邮箱格式"""
        if v is not None:
            import re
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
                raise ValueError("邮箱格式不正确")
        return v
    
    @validator("priority")
    def validate_priority(cls, v):
        """验证优先级"""
        allowed_priorities = ["low", "medium", "high", "urgent"]
        if v not in allowed_priorities:
            raise ValueError(f"优先级必须是 {allowed_priorities} 之一")
        return v
    
    @validator("stage_progress")
    def validate_stage_progress(cls, v):
        """验证阶段进度"""
        if v is not None:
            for stage, progress in v.items():
                if not isinstance(progress, int) or progress < 0 or progress > 100:
                    raise ValueError(f"阶段 {stage} 的进度必须是 0-100 之间的整数")
        return v
    
    @property
    def remaining_amount(self) -> Decimal:
        """剩余金额"""
        if self.total_amount is None:
            return Decimal("0")
        return self.total_amount - (self.paid_amount or Decimal("0"))
    
    @property
    def payment_progress(self) -> float:
        """付费进度百分比"""
        if self.total_amount is None or self.total_amount == 0:
            return 0.0
        return float((self.paid_amount or Decimal("0")) / self.total_amount * 100)
    
    @property
    def overall_progress(self) -> float:
        """整体进度百分比"""
        if not self.stage_progress:
            return 0.0
        
        stage_weights = {
            "requirement": 0.05,    # 需求分析 5%
            "prototype": 0.25,      # 原型设计 25%
            "development": 0.35,    # 开发完成 35%
            "operation": 0.35       # 运维验收 35%
        }
        
        total_progress = 0.0
        for stage, weight in stage_weights.items():
            progress = self.stage_progress.get(stage, 0)
            total_progress += (progress / 100) * weight
        
        return total_progress * 100
    
    @property
    def is_overdue(self) -> bool:
        """是否逾期"""
        if self.end_date is None:
            return False
        return datetime.now() > self.end_date and self.status != ProjectStatus.COMPLETED
    
    @property
    def days_remaining(self) -> Optional[int]:
        """剩余天数"""
        if self.end_date is None:
            return None
        delta = self.end_date - datetime.now()
        return max(0, delta.days)


class ProjectCreate(PydanticBaseModel):
    """创建项目请求模型"""
    
    name: str = Field(description="项目名称")
    description: Optional[str] = Field(default=None, description="项目描述")
    customer_name: Optional[str] = Field(default=None, description="客户姓名")
    customer_email: Optional[str] = Field(default=None, description="客户邮箱")
    customer_phone: Optional[str] = Field(default=None, description="客户电话")
    requirements: Optional[str] = Field(default=None, description="需求描述")
    objectives: Optional[str] = Field(default=None, description="项目目标")
    scope: Optional[str] = Field(default=None, description="项目范围")
    start_date: Optional[datetime] = Field(default=None, description="开始日期")
    end_date: Optional[datetime] = Field(default=None, description="结束日期")
    estimated_hours: Optional[Decimal] = Field(default=None, description="预估工时")
    total_amount: Optional[Decimal] = Field(default=None, description="总金额")
    technologies: Optional[List[str]] = Field(default=None, description="技术栈")
    platform: Optional[str] = Field(default=None, description="平台")
    priority: str = Field(default="medium", description="优先级")
    tags: Optional[List[str]] = Field(default=None, description="标签")


class ProjectUpdate(PydanticBaseModel):
    """更新项目请求模型"""
    
    name: Optional[str] = Field(default=None, description="项目名称")
    description: Optional[str] = Field(default=None, description="项目描述")
    status: Optional[ProjectStatus] = Field(default=None, description="项目状态")
    customer_name: Optional[str] = Field(default=None, description="客户姓名")
    customer_email: Optional[str] = Field(default=None, description="客户邮箱")
    customer_phone: Optional[str] = Field(default=None, description="客户电话")
    requirements: Optional[str] = Field(default=None, description="需求描述")
    objectives: Optional[str] = Field(default=None, description="项目目标")
    scope: Optional[str] = Field(default=None, description="项目范围")
    start_date: Optional[datetime] = Field(default=None, description="开始日期")
    end_date: Optional[datetime] = Field(default=None, description="结束日期")
    estimated_hours: Optional[Decimal] = Field(default=None, description="预估工时")
    current_stage: Optional[WorkflowStage] = Field(default=None, description="当前阶段")
    stage_progress: Optional[Dict[str, int]] = Field(default=None, description="阶段进度")
    total_amount: Optional[Decimal] = Field(default=None, description="总金额")
    paid_amount: Optional[Decimal] = Field(default=None, description="已付金额")
    payment_status: Optional[PaymentStatus] = Field(default=None, description="付费状态")
    technologies: Optional[List[str]] = Field(default=None, description="技术栈")
    platform: Optional[str] = Field(default=None, description="平台")
    repository_url: Optional[str] = Field(default=None, description="代码仓库URL")
    deployment_url: Optional[str] = Field(default=None, description="部署URL")
    domain: Optional[str] = Field(default=None, description="域名")
    priority: Optional[str] = Field(default=None, description="优先级")
    tags: Optional[List[str]] = Field(default=None, description="标签")
    is_active: Optional[bool] = Field(default=None, description="是否活跃")
    is_archived: Optional[bool] = Field(default=None, description="是否归档")


class ProjectFilter(PydanticBaseModel):
    """项目过滤参数"""
    
    status: Optional[ProjectStatus] = Field(default=None, description="项目状态")
    customer_id: Optional[str] = Field(default=None, description="客户ID")
    current_stage: Optional[WorkflowStage] = Field(default=None, description="当前阶段")
    payment_status: Optional[PaymentStatus] = Field(default=None, description="付费状态")
    priority: Optional[str] = Field(default=None, description="优先级")
    is_active: Optional[bool] = Field(default=None, description="是否活跃")
    is_archived: Optional[bool] = Field(default=None, description="是否归档")
    start_date_from: Optional[datetime] = Field(default=None, description="开始日期起")
    start_date_to: Optional[datetime] = Field(default=None, description="开始日期止")
    end_date_from: Optional[datetime] = Field(default=None, description="结束日期起")
    end_date_to: Optional[datetime] = Field(default=None, description="结束日期止")
    keyword: Optional[str] = Field(default=None, description="关键词搜索")


class ProjectSummary(PydanticBaseModel):
    """项目摘要信息"""
    
    id: str
    name: str
    status: ProjectStatus
    customer_name: Optional[str]
    current_stage: Optional[WorkflowStage]
    overall_progress: float
    payment_progress: float
    is_overdue: bool
    days_remaining: Optional[int]
    created_at: datetime
    updated_at: datetime 