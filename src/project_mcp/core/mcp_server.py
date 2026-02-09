"""MCP服务器核心实现 - 真实版本"""
import asyncio
import json
import sys
import aiohttp
from typing import Any, List, Dict, Optional, Sequence
from pathlib import Path
import os
import requests
import csv
import re

# MCP相关导入
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource, Tool, TextContent, ImageContent, EmbeddedResource,
    CallToolResult, ListResourcesResult, ListToolsResult, ReadResourceResult
)

from ..config.settings import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ProjectMCPServer:
    """项目管理MCP服务器 - 真实实现"""
    
    def __init__(self):
        self.server = Server("project-management-mcp")
        self._initialized = False
        
        # 后端API配置
        self.backend_base_url = os.getenv('API_BASE_URL')  or "http://localhost:8080/aiProject/api"
        self.api_key: Optional[str] = os.getenv('API_KEY') 
        self.session: Optional[aiohttp.ClientSession] = None
        
        # 项目连接状态管理
        self.current_project_id: Optional[str] = None
        self.current_channel: Optional[str] = None
        
        # 配置默认工作目录
        # 优先级：环境变量WORKSPACE -> AIPROJECT_WORKSPACE -> 当前目录
        self.default_workspace = os.getenv('WORKSPACE') or os.getenv('AIPROJECT_WORKSPACE', os.getcwd())
        logger.info(f"MCP服务器默认工作目录: {self.default_workspace}")
        
        # Channel到项目的映射关系
        self.channel_project_mapping = {
           
        }
        self.project={}
        self.workflow_list=[]
        self.current_workflow_node_id=None

        

        
        self._setup_handlers()
    
    async def _create_http_session(self):
        """创建HTTP会话"""
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    'Accept': 'application/json'
                }
            )
            logger.info("HTTP会话已创建")
    
    async def _close_http_session(self):
        """关闭HTTP会话"""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("HTTP会话已关闭")
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """获取带有API密钥的请求头"""
        headers = {}
        if self.api_key:
            headers['X-API-Key'] = self.api_key
        return headers
    
    async def _validate_api_key(self, api_key: str) -> bool:
        """验证API密钥是否有效"""
        try:
            await self._create_http_session()
            headers = {'X-API-Key': api_key}
            
            # 调用后端API验证密钥
            async with self.session.get(
                f"{self.backend_base_url}/system/api-keys",
                headers=headers
            ) as response:
                if response.status == 200:
                    logger.info("API密钥验证成功")
                    return True
                else:
                    logger.warning(f"API密钥验证失败，状态码: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"API密钥验证异常: {e}")
            return False
    
    async def _call_backend_api(self, method: str, endpoint: str, 
                               data: Optional[Dict] = None, 
                               params: Optional[Dict] = None) -> Optional[Dict]:
        """调用后端API"""
        try:
            await self._create_http_session()
            url = f"{self.backend_base_url}/{endpoint.lstrip('/')}"
            headers = self._get_auth_headers()
            
            kwargs = {
                'headers': headers,
                'params': params
            }
            
            if data and method.upper() in ['POST', 'PUT', 'PATCH']:
                # 为JSON请求添加Content-Type
                headers['Content-Type'] = 'application/json'
                kwargs['headers'] = headers
                kwargs['json'] = data
            
            async with self.session.request(method, url, **kwargs) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.debug(f"API调用成功: {method} {endpoint}")
                    return result
                elif response.status == 401:
                    logger.error("API密钥无效或已过期")
                    return None
                elif response.status == 403:
                    logger.error("API密钥权限不足")
                    return None
                else:
                    error_text = await response.text()
                    logger.error(f"API调用失败: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"API调用异常: {e}")
            return None
    
    def _check_project_connection(self) -> Optional[str]:
        """检查项目连接状态，返回错误信息或None"""
        if not self.current_project_id:
            return "❌ **未连接到任何项目**\n\n请先使用 `connect_to_project` 工具连接到项目后再执行操作。"
        return None
    
    def _check_api_key(self) -> Optional[str]:
        """检查API密钥状态，返回错误信息或None"""
        if not self.api_key:
            return "❌ **未设置API密钥**\n\n请先使用 `set_api_key` 工具设置有效的API密钥。"
        return None
    
    def _get_current_project_info(self) -> Optional[dict]:
        """获取当前连接的项目信息"""
        if not self.current_project_id:
            return None
        return self.project
    
    def _setup_handlers(self):
        """设置MCP处理器"""
        
        # 工具列表处理器
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """列出所有可用工具"""
            return [
                Tool(
                    name="set_api_key",
                    description="设置API密钥用于后端API访问",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "api_key": {
                                "type": "string",
                                "description": "后端API密钥"
                            }
                        },
                        "required": ["api_key"]
                    }
                ),
                Tool(
                    name="get_api_status",
                    description="获取API连接状态和密钥信息",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="connect_to_project",
                    description="通过Channel号连接到特定项目",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "channel": {
                                "type": "string",
                                "description": "Channel号"
                            },
                            "workspace_path": {
                                "type": "string",
                                "description": "工作目录路径（可选，默认使用环境变量或当前目录）"
                            }
                        },
                        "required": ["channel"]
                    }
                ),
                Tool(
                    name="disconnect_project",
                    description="断开当前项目连接",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="get_connection_status",
                    description="获取当前项目连接状态",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),





                Tool(
                    name="get_workflow_execution_requirements",
                    description="执行工作流节点",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "user_requirement": {
                                "type": "string",
                                "description": "用户对于执行工作流节点的需求，比如执行哪一个，怎么执行"
                            }
                        }
                    }
                ),
                Tool(
                    name="upload_documents",
                    description="上传文档到当前项目：用户可以指定要上传的文档文件路径，系统会自动上传到当前连接的项目中",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_paths": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "要上传的文件路径列表，可以是绝对路径或相对于工作目录的相对路径"
                            },
                            "document_type": {
                                "type": "string",
                                "enum": ["REQUIREMENT", "DESIGN", "API", "USER_MANUAL", "TECHNICAL", "OTHER"],
                                "default": "OTHER",
                                "description": "文档类型，默认为OTHER"
                            },
                            "summary": {
                                "type": "string",
                                "description": "文档摘要描述（可选）"
                            },
                            "tags": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "文档标签列表（可选）"
                            }
                        },
                        "required": ["file_paths"]
                    }
                ),
                Tool(
                    name="sync_requirements",
                    description="同步项目需求：从后端API查询当前项目的所有实现中的需求，并保存到本地CSV文件",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="sync_bugs",
                    description="同步项目修复中的bug：从后端API查询当前项目修复中的bug，并保存到本地CSV文件",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="sync_workflows",
                    description="同步工作流：根据工作流管理.json文件删除该目录下的工作流文件，把当前工作流置为空，然后重新从项目同步新的工作流下来",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="send_result",
                    description="发送任务执行结果到系统。每次执行完任务后调用，将 taskId 和 taskResult 提交给后端，用于决定下一步（验收/完成/用户验收）",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "taskId": {
                                "type": "string",
                                "description": "任务ID"
                            },
                            "taskResult": {
                                "type": "string",
                                "description": "任务执行结果内容"
                            }
                        },
                        "required": ["taskId", "taskResult"]
                    }
                ),

            ]
        
        # 工具调用处理器
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> List[TextContent | ImageContent | EmbeddedResource]:
            """处理工具调用"""
            logger.info(f"调用工具: {name}, 参数: {arguments}")
            
            try:
                # API密钥相关工具
                if name == "set_api_key":
                    return await self._handle_set_api_key(arguments)
                elif name == "get_api_status":
                    return await self._handle_get_api_status(arguments)
                # 项目连接相关工具不需要检查连接状态
                elif name == "connect_to_project":
                    return await self._handle_connect_to_project(arguments)
                elif name == "disconnect_project":
                    return await self._handle_disconnect_project(arguments)
                elif name == "get_connection_status":
                    return await self._handle_get_connection_status(arguments)
                
                # 其他工具需要检查项目连接状态
                connection_error = self._check_project_connection()
                if connection_error:
                    return [TextContent(type="text", text=connection_error)]
                
                # 检查API密钥（某些功能需要后端API）
                api_key_error = self._check_api_key()
                use_backend = self.api_key is not None
                
                if name == "get_workflow_execution_requirements":
                    return await self._handle_get_workflow_execution_requirements(arguments)
                elif name == "upload_documents":
                    return await self._handle_upload_documents(arguments)
                elif name == "sync_requirements":
                    return await self._handle_sync_requirements(arguments)
                elif name == "sync_bugs":
                    return await self._handle_sync_bugs(arguments)
                elif name == "sync_workflows":
                    return await self._handle_sync_workflows(arguments)
                elif name == "send_result":
                    return await self._handle_send_result(arguments)
                else:
                    return [TextContent(type="text", text=f"未知工具: {name}")]
                    
            except Exception as e:
                logger.error(f"工具执行错误: {e}")
                return [TextContent(type="text", text=f"执行失败: {str(e)}")]
        
        # 资源列表处理器
        @self.server.list_resources()
        async def handle_list_resources() -> List[Resource]:
            """列出所有可用资源"""
            resources = []
            
         
            
            logger.debug(f"返回 {len(resources)} 个资源")
            return resources
        
        # 资源读取处理器
        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """读取资源内容"""
            logger.info(f"读取资源: {uri}")
            
            try:
                if uri.startswith("project://"):
                    project_id = uri[10:]  # 去掉 "project://"
                    project = self._get_current_project_info()
                    if project:
                        return json.dumps(project, ensure_ascii=False, indent=2)
                    else:
                        return json.dumps({"error": "项目未找到"}, ensure_ascii=False)
                
                elif uri.startswith("file://"):
                    file_id = uri[7:]  # 去掉 "file://"
                    file_info = next((f for f in self.files_data if f["id"] == file_id), None)
                    if file_info:
                        return file_info.get("content", "文件内容不可用")
                    else:
                        return "文件未找到"
                
                else:
                    return f"不支持的URI方案: {uri}"
                    
            except Exception as e:
                logger.error(f"资源读取错误: {e}")
                return f"读取资源时出错: {str(e)}"
    
    def _get_mime_type(self, filename: str) -> str:
        """根据文件名获取MIME类型"""
        ext = Path(filename).suffix.lower()
        mime_map = {
            '.md': 'text/markdown',
            '.txt': 'text/plain',
            '.json': 'application/json',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.pdf': 'application/pdf',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }
        return mime_map.get(ext, 'application/octet-stream')
    
    async def _handle_set_api_key(self, arguments: dict) -> List[TextContent]:
        """处理设置API密钥"""
        api_key = arguments["api_key"]
        
        # 验证API密钥
        if await self._validate_api_key(api_key):
            self.api_key = api_key
            logger.info("API密钥设置成功")
            return [TextContent(type="text", text="✅ **API密钥设置成功**\n\n现在可以访问后端API服务。")]
        else:
            logger.warning("API密钥验证失败")
            return [TextContent(type="text", text="❌ **API密钥验证失败**\n\n请检查密钥是否正确或后端服务是否可用。")]
    
    async def _handle_get_api_status(self, arguments: dict) -> List[TextContent]:
        """处理获取API状态"""
        # 检查配置中的 channelNo
        config_channel_no = settings.channel_no or os.getenv('CHANNEL_NO')
        auto_connected = False
        
        # 如果配置了 channelNo 且项目未连接，则自动连接
        if config_channel_no and not self.current_project_id:
            if self.api_key:
                try:
                    # 自动连接项目
                    logger.info(f"检测到配置的 channelNo: {config_channel_no}，自动连接项目")
                    self.project = self._get_project_by_channel(config_channel_no)
                    
                    # 检查项目是否获取成功
                    if isinstance(self.project, dict) and self.project:
                        # 设置连接状态
                        self.current_channel = config_channel_no
                        self.current_project_id = self.project["id"]
                        
                        # 确保项目信息.md文件存在
                        self._ensure_project_info_file()
                        
                        # 尝试获取工作流（不阻塞，失败也不影响连接）
                        try:
                            workflow_relations = await self._get_project_workflow_relations(self.current_project_id)
                            if workflow_relations is None:
                                logger.warning("无法获取项目工作流列表，但项目已连接")
                        except Exception as e:
                            logger.warning(f"获取工作流失败，但项目已连接: {e}")
                        
                        auto_connected = True
                        logger.info(f"自动连接项目成功: {config_channel_no} -> {self.project.get('name', '未知')}")
                    else:
                        logger.warning(f"自动连接项目失败: {self.project}")
                except Exception as e:
                    logger.error(f"自动连接项目时发生错误: {e}")
        
        if not self.api_key:
            status_lines = [
                "📡 **API连接状态**: 未设置\n",
                f"🌐 **后端地址**: {self.backend_base_url}",
                "🔑 **API密钥**: 未设置\n",
                "⚠️ **注意**: 请使用 `set_api_key` 工具设置API密钥以访问后端服务。"
            ]
            
            # 如果配置了 channelNo，提示用户
            if config_channel_no:
                status_lines.append(f"\n💡 **提示**: 检测到配置的 channelNo: {config_channel_no}，设置API密钥后将自动连接项目。")
        else:
            # 检查API密钥是否仍然有效
            is_valid = await self._validate_api_key(self.api_key)
            status = "有效" if is_valid else "无效/过期"
            status_emoji = "✅" if is_valid else "❌"
            
            masked_key = f"{self.api_key[:8]}{'*' * (len(self.api_key) - 12)}{self.api_key[-4:]}" if len(self.api_key) > 12 else f"{self.api_key[:4]}{'*' * 8}"
            
            status_lines = [
                f"📡 **API连接状态**: 已连接 {status_emoji}\n",
                f"🌐 **后端地址**: {self.backend_base_url}",
                f"🔑 **API密钥**: {masked_key}",
                f"📊 **密钥状态**: {status}\n"
            ]
            
            # 如果配置了 channelNo，显示项目连接状态
            if config_channel_no:
                if auto_connected or self.current_project_id:
                    project = self._get_current_project_info()
                    if project:
                        status_lines.append("📋 **项目连接状态**: 已连接 ✅\n")
                        status_lines.append(f"🏷️ **Channel**: {self.current_channel}")
                        status_lines.append(f"📝 **项目名称**: {project.get('name', '未知')}")
                        status_lines.append(f"📊 **项目状态**: {project.get('status', '未知')}")
                        status_lines.append(f"📄 **项目描述**: {project.get('description', '暂无描述')}\n")
                    else:
                        status_lines.append(f"📋 **项目连接状态**: 已连接（Channel: {self.current_channel}）\n")
                else:
                    status_lines.append(f"📋 **项目连接状态**: 未连接（配置的 Channel: {config_channel_no}）\n")
            
            status_lines.append("💡 **提示**: 后端API功能已启用，将优先使用后端数据。")
        
        return [TextContent(type="text", text="\n".join(status_lines))]
    
    def _get_workflow_management_file_path(self) -> Path:
        """获取工作流管理文件路径"""
        project_management_dir = Path(self.default_workspace) / "项目管理"
        return project_management_dir / "工作流管理.json"
    
    def _load_workflow_management(self) -> Optional[Dict]:
        """加载工作流管理文件"""
        try:
            management_file = self._get_workflow_management_file_path()
            if management_file.exists():
                with open(management_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"已加载工作流管理文件: {management_file}")
                    return data
            return None
        except Exception as e:
            logger.warning(f"加载工作流管理文件失败: {e}")
            return None
    
    def _save_workflow_management(self, workflows_data: List[Dict], current_workflow_id: Optional[int] = None) -> bool:
        """保存工作流管理文件"""
        try:
            project_management_dir = Path(self.default_workspace) / "项目管理"
            project_management_dir.mkdir(parents=True, exist_ok=True)
            
            management_file = project_management_dir / "工作流管理.json"
            management_data = {
                "currentWorkflowId": current_workflow_id,
                "workflows": workflows_data
            }
            
            with open(management_file, 'w', encoding='utf-8') as f:
                json.dump(management_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"工作流管理文件已保存: {management_file}")
            return True
        except Exception as e:
            logger.error(f"保存工作流管理文件失败: {e}")
            return False
    
    def _check_workflow_files_exist(self, workflow_name: str) -> bool:
        """检查工作流详情文件是否存在"""
        try:
            project_management_dir = Path(self.default_workspace) / "项目管理"
            safe_workflow_name = re.sub(r'[<>:"/\\|?*]', '_', workflow_name)
            csv_filename = f"工作流_{safe_workflow_name}.csv"
            workflow_csv = project_management_dir / csv_filename
            return workflow_csv.exists()
        except Exception as e:
            logger.warning(f"检查工作流文件失败: {e}")
            return False
    
    def _ensure_project_info_file(self) -> bool:
        """确保项目信息.md文件存在，如果不存在则创建"""
        try:
            project_management_dir = Path(self.default_workspace) / "项目管理"
            project_management_dir.mkdir(parents=True, exist_ok=True)
            
            project_info_file = project_management_dir / "项目信息.md"
            
            # 如果文件已存在，则不需要创建
            if project_info_file.exists():
                logger.info(f"项目信息.md文件已存在: {project_info_file}")
                return True
            
            # 创建项目信息.md文件
            project_name = self.project.get('name', '未知项目')
            project_status = self.project.get('status', '未知状态')
            project_description = self.project.get('description', '暂无描述')
            
            # 生成Markdown内容
            content = f"""# 项目信息

## 项目名称
{project_name}

## 状态
{project_status}

## 描述
{project_description}
"""
            
            # 写入文件
            with open(project_info_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"已创建项目信息.md文件: {project_info_file}")
            return True
            
        except Exception as e:
            logger.error(f"创建项目信息.md文件失败: {e}")
            return False
    
    async def _sync_workflows(self) -> bool:
        """同步工作流：删除旧的工作流文件，清空当前工作流，然后重新从项目同步"""
        try:
            # 检查项目连接
            if not self.current_project_id:
                logger.error("未连接到项目，无法同步工作流")
                return False
            
            # 检查API密钥
            if not self.api_key:
                logger.error("未设置API密钥，无法同步工作流")
                return False
            
            project_management_dir = Path(self.default_workspace) / "项目管理"
            project_management_dir.mkdir(parents=True, exist_ok=True)
            
            # 1. 读取工作流管理文件，获取所有工作流信息
            management_data = self._load_workflow_management()
            deleted_files = []
            
            if management_data:
                workflows = management_data.get("workflows", [])
                # 删除每个工作流对应的CSV文件
                for workflow in workflows:
                    workflow_name = workflow.get("name", "")
                    if workflow_name:
                        # 清理文件名，移除不允许的字符
                        safe_workflow_name = re.sub(r'[<>:"/\\|?*]', '_', workflow_name)
                        csv_filename = f"工作流_{safe_workflow_name}.csv"
                        workflow_csv = project_management_dir / csv_filename
                        
                        if workflow_csv.exists():
                            try:
                                workflow_csv.unlink()
                                deleted_files.append(csv_filename)
                                logger.info(f"已删除工作流文件: {workflow_csv}")
                            except Exception as e:
                                logger.warning(f"删除工作流文件失败 {workflow_csv}: {e}")
            
            # 2. 删除项目管理目录下所有匹配的工作流CSV文件（以防有遗漏）
            try:
                for csv_file in project_management_dir.glob("工作流_*.csv"):
                    if csv_file.name not in deleted_files:
                        csv_file.unlink()
                        deleted_files.append(csv_file.name)
                        logger.info(f"已删除工作流文件: {csv_file}")
            except Exception as e:
                logger.warning(f"删除工作流文件时出错: {e}")
            
            # 3. 将当前工作流置为空
            self._save_workflow_management([], None)
            logger.info("已清空工作流管理文件")
            
            # 4. 重新从项目同步新的工作流
            # 获取项目工作流关联列表
            workflow_relations = await self._get_project_workflow_relations(self.current_project_id)
            if workflow_relations is None:
                logger.error("无法获取项目工作流列表")
                return False
            
            if not workflow_relations:
                logger.info(f"项目 {self.current_project_id} 没有关联的工作流")
                return True
            
            # 同步每个工作流
            workflows_data = []
            saved_workflows = []
            failed_workflows = []
            
            for relation in workflow_relations:
                workflow_id = relation.get("workflowId")
                if not workflow_id:
                    continue
                
                try:
                    # 获取工作流详情（包含名称）
                    workflow_detail = await self._get_workflow_detail(workflow_id)
                    if not workflow_detail:
                        failed_workflows.append(f"工作流ID: {workflow_id} (无法获取详情)")
                        continue
                    
                    workflow_name = workflow_detail.get("workflowName", f"工作流_{workflow_id}")
                    # 清理文件名，移除不允许的字符
                    safe_workflow_name = re.sub(r'[<>:"/\\|?*]', '_', workflow_name)
                    
                    # 获取工作流节点列表
                    workflow_nodes = self._get_workflow_by_id(str(workflow_id))
                    if not workflow_nodes:
                        failed_workflows.append(f"{workflow_name} (无法获取节点)")
                        continue
                    
                    # 保存为CSV文件
                    csv_filename = f"工作流_{safe_workflow_name}.csv"
                    workflow_csv = project_management_dir / csv_filename
                    
                    with open(workflow_csv, mode="w", encoding="utf-8", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow(["id", "nodeName", "prompt"])
                        for node in workflow_nodes:
                            writer.writerow([
                                node.get("id", ""),
                                node.get("nodeName", ""),
                                node.get("prompt", "") 
                            ])
                    logger.info(f"工作流节点已保存到: {workflow_csv}")
                    
                    # 保存工作流信息（不包含当前节点信息，因为这是新同步的）
                    workflows_data.append({
                        "id": workflow_id,
                        "name": workflow_name,
                        "currentNodeId": None,
                        "currentNodeName": None
                    })
                    
                    saved_workflows.append(f"{workflow_name} ({len(workflow_nodes)}个节点)")
                    
                except Exception as e:
                    logger.error(f"保存工作流 {workflow_id} 失败: {e}")
                    failed_workflows.append(f"工作流ID: {workflow_id} ({str(e)})")
            
            # 保存工作流管理文件（当前工作流ID设为None）
            if workflows_data:
                self._save_workflow_management(workflows_data, None)
            
            logger.info(f"工作流同步完成: 成功 {len(saved_workflows)} 个, 失败 {len(failed_workflows)} 个")
            return True
            
        except Exception as e:
            logger.error(f"同步工作流失败: {e}")
            return False
    
    async def _handle_connect_to_project(self, arguments: dict) -> List[TextContent]:
        """处理连接到项目"""
        channel = arguments["channel"]
        workspace_path = arguments.get("workspace_path", self.default_workspace)
        self.project=self._get_project_by_channel(channel)
        
        # 修复：判断project类型，避免字符串被当作字典访问
        if not isinstance(self.project, dict):
            return [TextContent(type="text", text=f"❌ 连接失败: {self.project}")]
        
        # 检查项目是否存在
        if not self.project:
            return [TextContent(type="text", text=f"❌  {channel} 不存在")]
        
        # 设置连接状态
        self.current_channel = channel
        self.current_project_id = self.project["id"]
        
        # 确保项目信息.md文件存在
        self._ensure_project_info_file()
        
        # 检查API密钥
        if not self.api_key:
            return [TextContent(type="text", text="❌ 未设置API密钥，请先使用 set_api_key 设置API密钥")]
        
        # 获取项目工作流关联列表
        workflow_relations = await self._get_project_workflow_relations(self.current_project_id)
        if workflow_relations is None:
            return [TextContent(type="text", text="❌ 无法获取项目工作流列表，请检查API连接")]
        
        if not workflow_relations:
            logger.info(f"项目 {self.current_project_id} 没有关联的工作流")
            result_lines = [
                f"✅ **成功连接到项目**\n",
                f"🏷️ **Channel**: {channel}",
                f"📝 **项目名称**: {self.project['name']}",
                f"📊 **状态**: {self.project['status']}",
                f"📄 **描述**: {self.project['description']}\n",
                "⚠️ **注意**: 该项目没有关联的工作流"
            ]
            return [TextContent(type="text", text="\n".join(result_lines))]
        
        # 检查是否已存在工作流管理文件
        existing_management = self._load_workflow_management()
        need_update = False
        
        # 检查每个工作流的详情文件是否存在
        if existing_management:
            existing_workflow_ids = {w.get("id") for w in existing_management.get("workflows", [])}
            for relation in workflow_relations:
                workflow_id = relation.get("workflowId")
                if workflow_id and workflow_id not in existing_workflow_ids:
                    need_update = True
                    break
                elif workflow_id:
                    # 检查工作流详情文件是否存在
                    workflow_detail = await self._get_workflow_detail(workflow_id)
                    if workflow_detail:
                        workflow_name = workflow_detail.get("workflowName", f"工作流_{workflow_id}")
                        if not self._check_workflow_files_exist(workflow_name):
                            need_update = True
                            break
        else:
            need_update = True
        
        # 如果文件已存在且完整，则不需要更新
        if not need_update and existing_management:
            logger.info("工作流管理文件和详情文件已存在，跳过更新")
            current_workflow_id = existing_management.get("currentWorkflowId")
            workflows = existing_management.get("workflows", [])
            
            result_lines = [
                f"✅ **成功连接到项目**\n",
                f"🏷️ **Channel**: {channel}",
                f"📝 **项目名称**: {self.project['name']}",
                f"📊 **状态**: {self.project['status']}",
                f"📄 **描述**: {self.project['description']}\n",
                f"📋 **工作流信息**:",
                f"  📁 工作流管理文件已存在，已加载 {len(workflows)} 个工作流"
            ]
            
            if current_workflow_id:
                current_workflow = next((w for w in workflows if w.get("id") == current_workflow_id), None)
                if current_workflow:
                    result_lines.append(f"  🎯 当前工作流: {current_workflow.get('name')}")
                    if current_workflow.get("currentNodeId"):
                        result_lines.append(f"  📍 当前节点: {current_workflow.get('currentNodeName')} (ID: {current_workflow.get('currentNodeId')})")
            
            result_lines.append("\n✅ **工作流列表**:")
            for workflow in workflows:
                node_info = ""
                if workflow.get("currentNodeId"):
                    node_info = f" - 当前节点: {workflow.get('currentNodeName')} (ID: {workflow.get('currentNodeId')})"
                result_lines.append(f"  - {workflow.get('name')} (ID: {workflow.get('id')}){node_info}")
            
            result_lines.extend([
                "",
                "🎯 **现在可以执行以下操作:**",
                "- 查询项目信息",
                "- 执行工作流节点"
            ])
            
            return [TextContent(type="text", text="\n".join(result_lines))]
        
        # 需要更新：为每个工作流获取节点并保存为单独的CSV文件
        saved_workflows = []
        failed_workflows = []
        workflows_data = []
        
        try:
            project_management_dir = Path(self.default_workspace) / "项目管理"
            project_management_dir.mkdir(parents=True, exist_ok=True)
            
            # 如果已有管理文件，尝试加载当前工作流和节点信息
            current_workflow_id = None
            if existing_management:
                current_workflow_id = existing_management.get("currentWorkflowId")
                # 创建工作流ID到节点信息的映射
                existing_workflow_map = {
                    w.get("id"): {
                        "currentNodeId": w.get("currentNodeId"),
                        "currentNodeName": w.get("currentNodeName")
                    }
                    for w in existing_management.get("workflows", [])
                }
            else:
                existing_workflow_map = {}
            
            for relation in workflow_relations:
                workflow_id = relation.get("workflowId")
                if not workflow_id:
                    continue
                
                try:
                    # 获取工作流详情（包含名称）
                    workflow_detail = await self._get_workflow_detail(workflow_id)
                    if not workflow_detail:
                        failed_workflows.append(f"工作流ID: {workflow_id} (无法获取详情)")
                        continue
                    
                    workflow_name = workflow_detail.get("workflowName", f"工作流_{workflow_id}")
                    # 清理文件名，移除不允许的字符
                    safe_workflow_name = re.sub(r'[<>:"/\\|?*]', '_', workflow_name)
                    
                    # 获取工作流节点列表
                    workflow_nodes = self._get_workflow_by_id(str(workflow_id))
                    if not workflow_nodes:
                        failed_workflows.append(f"{workflow_name} (无法获取节点)")
                        continue
                    
                    # 检查是否已存在详情文件，如果存在则跳过保存
                    csv_filename = f"工作流_{safe_workflow_name}.csv"
                    workflow_csv = project_management_dir / csv_filename
                    
                    if not workflow_csv.exists():
                        # 保存为单独的CSV文件
                        with open(workflow_csv, mode="w", encoding="utf-8", newline="") as f:
                            writer = csv.writer(f)
                            writer.writerow(["id", "nodeName", "prompt"])
                            for node in workflow_nodes:
                                writer.writerow([
                                    node.get("id", ""),
                                    node.get("nodeName", ""),
                                    node.get("prompt", "") 
                                ])
                        logger.info(f"工作流节点已保存到: {workflow_csv}")
                    else:
                        logger.info(f"工作流详情文件已存在，跳过保存: {workflow_csv}")
                    
                    # 获取当前节点信息（从已有管理文件中获取，如果没有则设为None）
                    existing_info = existing_workflow_map.get(workflow_id, {})
                    workflows_data.append({
                        "id": workflow_id,
                        "name": workflow_name,
                        "currentNodeId": existing_info.get("currentNodeId"),
                        "currentNodeName": existing_info.get("currentNodeName")
                    })
                    
                    saved_workflows.append(f"{workflow_name} ({len(workflow_nodes)}个节点)")
                    
                except Exception as e:
                    logger.error(f"保存工作流 {workflow_id} 失败: {e}")
                    failed_workflows.append(f"工作流ID: {workflow_id} ({str(e)})")
            
            # 保存工作流管理文件
            if workflows_data:
                self._save_workflow_management(workflows_data, current_workflow_id)
            
            # 生成结果报告
            logger.info(f"连接到项目: {channel} -> {self.project['name']}")
            
            result_lines = [
                f"✅ **成功连接到项目**\n",
                f"🏷️ **Channel**: {channel}",
                f"📝 **项目名称**: {self.project['name']}",
                f"📊 **状态**: {self.project['status']}",
                f"📄 **描述**: {self.project['description']}\n",
                f"📋 **工作流同步结果**:",
                f"  ✅ 成功: {len(saved_workflows)} 个工作流",
                f"  ❌ 失败: {len(failed_workflows)} 个工作流\n"
            ]
            
            if saved_workflows:
                result_lines.append("✅ **已保存的工作流**:")
                for workflow_info in saved_workflows:
                    result_lines.append(f"  - {workflow_info}")
                result_lines.append("")
            
            if failed_workflows:
                result_lines.append("❌ **失败的工作流**:")
                for workflow_info in failed_workflows:
                    result_lines.append(f"  - {workflow_info}")
                result_lines.append("")
            
            if workflows_data:
                result_lines.append("📋 **工作流列表**:")
                for workflow in workflows_data:
                    node_info = ""
                    if workflow.get("currentNodeId"):
                        node_info = f" - 当前节点: {workflow.get('currentNodeName')} (ID: {workflow.get('currentNodeId')})"
                    result_lines.append(f"  - {workflow.get('name')} (ID: {workflow.get('id')}){node_info}")
                result_lines.append("")
            
            if current_workflow_id:
                current_workflow = next((w for w in workflows_data if w.get("id") == current_workflow_id), None)
                if current_workflow:
                    result_lines.append(f"🎯 **当前工作流**: {current_workflow.get('name')}")
            
            result_lines.extend([
                "",
                "🎯 **现在可以执行以下操作:**",
                "- 查询项目信息",
                "- 执行工作流节点"
            ])
            
            return [TextContent(type="text", text="\n".join(result_lines))]
            
        except Exception as e:
            logger.error(f"处理工作流失败: {e}")
            return [TextContent(type="text", text=f"❌ 处理工作流失败: {str(e)}")]
    
    async def _handle_disconnect_project(self, arguments: dict) -> List[TextContent]:
        """处理断开项目连接"""
        if not self.current_project_id:
            return [TextContent(type="text", text="❌ 当前没有连接到任何项目")]
        
        old_channel = self.current_channel
        old_project_id = self.current_project_id
        old_project = self._get_current_project_info()
        
        # 清除连接状态
        self.current_channel = None
        self.current_project_id = None
        
        logger.info(f"断开项目连接: {old_channel} -> {old_project_id}")
        
        result_lines = [
            f"✅ **已断开项目连接**\n",
            f"🏷️ **之前的Channel**: {old_channel}",
            f"📋 **项目**: {old_project['name'] if old_project else old_project_id}\n",
            "⚠️ **注意**: 需要重新连接项目才能执行其他操作",
            "使用 `connect_to_project` 工具连接到项目"
        ]
        
        return [TextContent(type="text", text="\n".join(result_lines))]
    
    async def _handle_get_connection_status(self, arguments: dict) -> List[TextContent]:
        """处理获取连接状态"""
        # 检查配置中的 channelNo，如果未连接则尝试自动连接
        config_channel_no = settings.channel_no or os.getenv('CHANNEL_NO')
        if not self.current_project_id and config_channel_no and self.api_key:
            try:
                logger.info(f"检测到配置的 channelNo: {config_channel_no}，自动连接项目")
                self.project = self._get_project_by_channel(config_channel_no)
                
                if isinstance(self.project, dict) and self.project:
                    self.current_channel = config_channel_no
                    self.current_project_id = self.project["id"]
                    self._ensure_project_info_file()
                    logger.info(f"自动连接项目成功: {config_channel_no} -> {self.project.get('name', '未知')}")
            except Exception as e:
                logger.warning(f"自动连接项目失败: {e}")
        
        if not self.current_project_id:
            result_lines = [
                "📡 **连接状态**: 未连接\n"
            ]
            
            # 如果配置了 channelNo，显示提示信息
            if config_channel_no:
                result_lines.append(f"💡 **提示**: 检测到配置的 channelNo: {config_channel_no}")
                if not self.api_key:
                    result_lines.append("⚠️ **注意**: 请先设置API密钥以自动连接项目")
                else:
                    result_lines.append("⚠️ **注意**: 自动连接失败，请检查 channelNo 是否正确")
            else:
                result_lines.append("\n使用channel号连接到目标项目")
        else:
            project = self._get_current_project_info()
            result_lines = [
                "📡 **连接状态**: 已连接 ✅\n",
                f"🏷️ **当前Channel**: {self.current_channel}",
                f"📋 **项目ID**: {self.current_project_id}",
                f"📝 **项目名称**: {project['name'] if project else '未知'}",
                f"👤 **客户**: {project['customer_name'] if project else '未知'}",
                f"📊 **状态**: {project['status'] if project else '未知'}",
                f"📄 **描述**: {project['description'] if project else '未知'}\n",
                "使用 `disconnect_project` 工具断开连接"
            ]
        
        return [TextContent(type="text", text="\n".join(result_lines))]
    
    def _get_project_by_channel(self, channel_no: str) -> str:
        """根据渠道编号获取项目名称，仅使用后端API，如果API不可用则提示无法连接到服务器"""
        import requests
        if not self.api_key:
            return "无法连接到服务器，请先设置API密钥"
        try:
            url = f"{self.backend_base_url}/projects/channel/{channel_no}"
            headers = {'X-API-Key': self.api_key}
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    projects = data.get('data')
                    if isinstance(projects, list) and projects:
                        return projects[0]
            return "无法连接到服务器，请检查API密钥或网络连接"
        except Exception as e:
            logger.warning(f"后端API获取项目名称失败: {e}")
            return "无法连接到服务器，请检查API密钥或网络连接"
    
    
    
    
    
    async def initialize(self):
        """初始化服务器"""
        if not self._initialized:
            logger.info("初始化MCP服务器")
            # 初始化HTTP会话
            await self._create_http_session()
            # 这里可以添加数据库连接、API客户端初始化等
            self._initialized = True
            logger.info("MCP服务器初始化完成")
    
    async def run(self):
        """运行MCP服务器"""
        await self.initialize()
        
        logger.info("🚀 启动项目管理MCP服务器")
        logger.info("📡 等待客户端连接...")
        
        # 运行标准的MCP stdio服务器
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="project-management-mcp",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    )
                )
            )



    async def _handle_upload_documents(self, arguments: dict) -> List[TextContent]:
        """处理文档上传"""
        file_paths = arguments["file_paths"]
        document_type = arguments.get("document_type", "OTHER")
        summary = arguments.get("summary", "")
        tags = arguments.get("tags", [])
        
        # 检查当前项目连接
        if not self.current_project_id:
            return [TextContent(type="text", text="❌ 未连接到项目，请先使用 connect_to_project 连接到项目")]
        
        # 检查API密钥
        if not self.api_key:
            return [TextContent(type="text", text="❌ 未设置API密钥，请先使用 set_api_key 设置API密钥")]
        
        upload_results = []
        successful_uploads = 0
        failed_uploads = 0
        
        for file_path in file_paths:
            try:
                result = await self._upload_single_document(
                    file_path, document_type, summary, tags
                )
                upload_results.append(result)
                if "✅" in result:
                    successful_uploads += 1
                else:
                    failed_uploads += 1
            except Exception as e:
                error_msg = f"❌ 上传失败 `{file_path}`: {str(e)}"
                upload_results.append(error_msg)
                failed_uploads += 1
                logger.error(f"上传文档失败: {file_path} - {e}")
        
        # 生成总结报告
        summary_lines = [
            f"📊 **文档上传总结**\n",
            f"📁 **项目**: {self._get_current_project_info()['name']}",
            f"📈 **成功**: {successful_uploads}个文档",
            f"❌ **失败**: {failed_uploads}个文档\n",
            "📋 **详细结果**:"
        ]
        
        # 添加详细结果
        for result in upload_results:
            summary_lines.append(f"  {result}")
        
        return [TextContent(type="text", text="\n".join(summary_lines))]
    
    async def _upload_single_document(self, file_path: str, document_type: str, 
                                    summary: str, tags: List[str]) -> str:
        """上传单个文档"""
        try:
            # 处理路径：如果是相对路径，则相对于工作目录
            if not os.path.isabs(file_path):
                file_path = os.path.join(self.default_workspace, file_path)
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return f"❌ 文件不存在: `{file_path}`"
            
            # 检查文件大小（限制50MB）
            file_size = os.path.getsize(file_path)
            if file_size > 50 * 1024 * 1024:  # 50MB
                return f"❌ 文件过大: `{os.path.basename(file_path)}` ({file_size / 1024 / 1024:.1f}MB > 50MB)"
            
            # 准备文档元数据
            file_name = os.path.basename(file_path)
            title = os.path.splitext(file_name)[0]  # 去掉扩展名作为标题
            
            # 构建multipart/form-data数据
            await self._create_http_session()
            
            # 读取文件内容
            with open(file_path, 'rb') as file:
                file_content = file.read()
            
            # 使用aiohttp.FormData正确构建multipart数据
            data = aiohttp.FormData()
            
            # 添加文件字段 - 使用文件内容而不是文件句柄
            data.add_field('file', file_content, 
                          filename=file_name,
                          content_type=self._get_mime_type(file_name))
            
            # 添加其他字段
            data.add_field('projectId', str(self.current_project_id))
            data.add_field('documentTitle', title)
            data.add_field('documentType', document_type)
            data.add_field('accessLevel', 'CONFIDENTIAL')
            
            if summary:
                data.add_field('summary', summary)
            
            # 处理tags数组 - 每个tag单独添加
            if tags:
                for tag in tags:
                    data.add_field('tags', tag)
            
            # 调用上传API - 只包含API密钥的headers，让aiohttp自动设置Content-Type
            url = f"{self.backend_base_url}/document-files/upload-and-create"
            headers = {}
            if self.api_key:
                headers['X-API-Key'] = self.api_key
            
            logger.info(f"开始上传文档: {file_name} 到项目 {self.current_project_id}")
            
            async with self.session.post(url, data=data, headers=headers) as response:
                response_text = await response.text()
                
                if response.status == 200:
                    try:
                        result = await response.json() if response.content_type == 'application/json' else response_text
                        logger.info(f"文档上传成功: {file_name}")
                        return f"✅ 已上传: `{file_name}` ({file_size / 1024:.1f}KB)"
                    except:
                        logger.info(f"文档上传成功: {file_name} (响应: {response_text[:100]})")
                        return f"✅ 已上传: `{file_name}` ({file_size / 1024:.1f}KB)"
                else:
                    logger.error(f"文档上传失败: {response.status} - {response_text}")
                    return f"❌ 上传失败: `{file_name}` (HTTP {response.status})"
                    
        except Exception as e:
            logger.error(f"上传文档时发生异常: {e}")
            return f"❌ 上传异常: `{os.path.basename(file_path)}` - {str(e)}"

    async def _handle_get_workflow_execution_requirements(self, arguments: dict) -> List[TextContent]:
        """处理获取执行节点的要求"""
        user_requirement = arguments.get("user_requirement")
        
        # 获取当前项目信息
        current_project = self._get_current_project_info()
        if not current_project:
            return [TextContent(type="text", text="❌ 无法获取当前项目信息")]
        
        try:
            # 生成指令要求AI读取工作流清单
            
            instruction = self._generate_wrokflow_reading_instruction(current_project, user_requirement)
            
            return [TextContent(type="text", text=instruction)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"❌ 生成工作流执行要求指令失败: {str(e)}")]


    

    

    
    def _generate_wrokflow_reading_instruction(self, project: dict, user_requirement: str = None) -> str:
        """生成指令要求AI读取工作流清单"""
        from datetime import datetime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 防御式处理：user_requirement 可能为 None，避免字符串拼接时报错
        safe_user_requirement = user_requirement if user_requirement is not None else ""

        instruction = (
            "从项目管理/工作流管理.json文件中读取当前工作流，如果当前工作流为空，则默认第一个工作为当前工作流并更新文档，"
            "找到该工作流的详细节点文件，文件名是工作流_工作流名称.csv，根据用户需求和工作流管理文件的当前节点选择一个合适的节点，"
            "如果工作流管理文件的节点为空则选择第一个节点，按照节点里的promt去完成该工作流，"
            "用户需求是：" + safe_user_requirement +
            "。如果用户选择的节点不是当前节点，请把当前工作流节点更新到项目管理/工作流管理文件中，然后按照节点里的promt去执行，"
            "完成该工作流节点后，提示用户当前工作流节点执行完成，可以执行下一个节点或者继续执行当前节点。"
        )

        result_lines = [
            instruction
        ]

        return "\n".join(result_lines)

    async def _handle_sync_requirements(self, arguments: dict) -> List[TextContent]:
        """处理同步项目需求"""
        # 检查当前项目连接
        if not self.current_project_id:
            return [TextContent(type="text", text="❌ 未连接到项目，请先使用 connect_to_project 连接到项目")]
        
        # 检查API密钥
        if not self.api_key:
            return [TextContent(type="text", text="❌ 未设置API密钥，请先使用 set_api_key 设置API密钥")]
        
        try:
            # 获取项目的实现中需求
            requirements_data = await self._fetch_project_requirements()
            
            if requirements_data is None:
                return [TextContent(type="text", text="❌ 无法获取项目需求数据，请检查API连接")]
            
            # 保存需求到CSV文件
            save_result = await self._save_requirements_to_csv(requirements_data)
            
            return [TextContent(type="text", text=save_result)]
            
        except Exception as e:
            logger.error(f"同步需求失败: {e}")
            return [TextContent(type="text", text=f"❌ 同步需求失败: {str(e)}")]

    async def _fetch_project_requirements(self) -> Optional[List[Dict]]:
        """从后端API获取项目的实现中需求"""
        try:
            # 构建查询参数，只查询实现中的需求
            params = {
                "projectId": str(self.current_project_id),
                "requirementStatus": "IMPLEMENTING",
                "pageNum": 1,
                "pageSize": 1000
            }
            
            # 调用后端API
            result = await self._call_backend_api("GET", "/requirements", params=params)
            
            if result and "data" in result:
                data = result["data"]
                # 处理分页数据结构
                if isinstance(data, dict) and "records" in data:
                    requirements = data["records"]
                elif isinstance(data, list):
                    requirements = data
                else:
                    logger.warning(f"意外的数据格式: {type(data)}")
                    return None
                
                logger.info(f"成功获取 {len(requirements)} 个实现中的需求")
                return requirements
            else:
                logger.warning("API返回数据格式异常")
                return None
                
        except Exception as e:
            logger.error(f"获取项目需求失败: {e}")
            return None

    async def _save_requirements_to_csv(self, requirements: List[Dict]) -> str:
        """保存需求数据到CSV文件"""
        try:
            from datetime import datetime
            from pathlib import Path
            import csv
            
            # 确保项目管理目录存在
            project_management_dir = Path(self.default_workspace) / "项目管理"
            project_management_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            current_project = self._get_current_project_info()
            project_name = current_project.get("name", "unknown") if current_project else "unknown"
            
            filename = f"实现中需求_{project_name}_{timestamp}.csv"
            file_path = project_management_dir / filename
            
            # 定义CSV字段
            fieldnames = ['需求编号', '需求名称', '需求描述', '需求状态']
            
            # 保存为CSV格式
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                # 写入表头
                writer.writerow(fieldnames)
                
                # 写入数据
                for req in requirements:
                    writer.writerow([
                        req.get('requirementNo', ''),
                        req.get('requirementTitle', ''),
                        req.get('requirementDescription', ''),
                        req.get('requirementStatus', '')
                    ])
            
            # 生成成功报告
            file_size = file_path.stat().st_size
            result_lines = [
                f"✅ **需求同步完成**\n",
                f"📁 **项目**: {project_name}",
                f"📈 **需求数量**: {len(requirements)} 个",
                f"📄 **文件路径**: `{file_path}`",
                f"📏 **文件大小**: {file_size / 1024:.2f} KB"
            ]
            
            logger.info(f"需求数据已保存到: {file_path}")
            return "\n".join(result_lines)
            
        except Exception as e:
            logger.error(f"保存需求CSV文件失败: {e}")
            return f"❌ 保存需求CSV文件失败: {str(e)}"



    async def _get_project_workflow_relations(self, project_id) -> Optional[List[Dict]]:
        """获取项目工作流关联列表"""
        try:
            # 调用后端API获取项目工作流关联列表
            result = await self._call_backend_api("GET", f"project-workflow-rel/project/{project_id}")
            
            if result and "data" in result:
                relations = result["data"]
                if isinstance(relations, list):
                    logger.info(f"成功获取 {len(relations)} 个工作流关联")
                    return relations
                else:
                    logger.warning(f"意外的数据格式: {type(relations)}")
                    return None
            else:
                logger.warning("API返回数据格式异常")
                return None
                
        except Exception as e:
            logger.error(f"获取项目工作流关联列表失败: {e}")
            return None
    
    async def _get_workflow_detail(self, workflow_id) -> Optional[Dict]:
        """获取工作流详情（包含名称）"""
        try:
            # 调用后端API获取工作流详情
            result = await self._call_backend_api("GET", f"workflow/{workflow_id}")
            
            if result and "data" in result:
                workflow = result["data"]
                if isinstance(workflow, dict):
                    logger.debug(f"成功获取工作流详情: {workflow.get('workflowName', '未知')}")
                    return workflow
                else:
                    logger.warning(f"意外的数据格式: {type(workflow)}")
                    return None
            else:
                logger.warning("API返回数据格式异常")
                return None
                
        except Exception as e:
            logger.error(f"获取工作流详情失败: {e}")
            return None
    
    def _get_workflow_by_id(self, workflow_id: str):
        """根据workflowId获取工作流节点列表"""
        import requests
        if not self.api_key:
            logger.error("未设置API密钥，无法获取工作流信息")
            return None
        try:
            url = f"{self.backend_base_url}/workflow/node/workflow/{workflow_id}"
            headers = {'X-API-Key': self.api_key}
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                # 假设返回格式为{"data": [...]}，直接返回节点列表
                return data.get('data', [])
            else:
                logger.error(f"获取工作流失败: {resp.status_code} - {resp.text}")
                return None
        except Exception as e:
            logger.error(f"请求工作流节点失败: {e}")
            return None

    async def _handle_sync_bugs(self, arguments: dict) -> List[TextContent]:
        """处理同步项目修复中的bug"""
        # 检查当前项目连接
        if not self.current_project_id:
            return [TextContent(type="text", text="❌ 未连接到项目，请先使用 connect_to_project 连接到项目")]
        # 检查API密钥
        if not self.api_key:
            return [TextContent(type="text", text="❌ 未设置API密钥，请先使用 set_api_key 设置API密钥")]
        try:
            bugs_data = await self._fetch_project_bugs()
            if bugs_data is None:
                return [TextContent(type="text", text="❌ 无法获取项目bug数据，请检查API连接")]
            save_result = await self._save_bugs_to_csv(bugs_data)
            return [TextContent(type="text", text=save_result)]
        except Exception as e:
            logger.error(f"同步bug失败: {e}")
            return [TextContent(type="text", text=f"❌ 同步bug失败: {str(e)}")]

    async def _fetch_project_bugs(self) -> Optional[List[Dict]]:
        """从后端API获取项目修复中的bug"""
        try:
            params = {
                "projectId": str(self.current_project_id),
                "bugStatus": "IN_PROGRESS",
                "pageNum": 1,
                "pageSize": 1000
            }
            result = await self._call_backend_api("GET", "/bugs", params=params)
            if result and "data" in result:
                data = result["data"]
                if isinstance(data, dict) and "records" in data:
                    bugs = data["records"]
                elif isinstance(data, list):
                    bugs = data
                else:
                    logger.warning(f"意外的数据格式: {type(data)}")
                    return None
                logger.info(f"成功获取 {len(bugs)} 个修复中的bug")
                return bugs
            else:
                logger.warning("API返回数据格式异常")
                return None
        except Exception as e:
            logger.error(f"获取项目bug失败: {e}")
            return None

    async def _save_bugs_to_csv(self, bugs: List[Dict]) -> str:
        """保存bug数据到CSV文件"""
        try:
            from datetime import datetime
            from pathlib import Path
            import csv
            project_management_dir = Path(self.default_workspace) / "项目管理"
            project_management_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            current_project = self._get_current_project_info()
            project_name = current_project.get("name", "unknown") if current_project else "unknown"
            filename = f"修复中bug_{project_name}_{timestamp}.csv"
            file_path = project_management_dir / filename
            fieldnames = ['bug编号', 'bug标题', 'bug描述', '复现步骤', '预期结果', '实际结果', '环境信息']
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(fieldnames)
                for bug in bugs:
                    writer.writerow([
                        bug.get('bugNo', ''),
                        bug.get('bugTitle', ''),
                        bug.get('bugDescription', ''),
                        bug.get('reproduceSteps', ''),
                        bug.get('expectedResult', ''),
                        bug.get('actualResult', ''),
                        bug.get('environmentInfo', '')
                    ])
            file_size = file_path.stat().st_size
            result_lines = [
                f"✅ **bug同步完成**\n",
                f"📁 **项目**: {project_name}",
                f"📈 **bug数量**: {len(bugs)} 个",
                f"📄 **文件路径**: `{file_path}`",
                f"📏 **文件大小**: {file_size / 1024:.2f} KB"
            ]
            logger.info(f"bug数据已保存到: {file_path}")
            return "\n".join(result_lines)
        except Exception as e:
            logger.error(f"保存bug CSV文件失败: {e}")
            return f"❌ 保存bug CSV文件失败: {str(e)}"

    async def _handle_sync_workflows(self, arguments: dict) -> List[TextContent]:
        """处理同步工作流"""
        # 检查当前项目连接
        if not self.current_project_id:
            return [TextContent(type="text", text="❌ 未连接到项目，请先使用 connect_to_project 连接到项目")]
        
        # 检查API密钥
        if not self.api_key:
            return [TextContent(type="text", text="❌ 未设置API密钥，请先使用 set_api_key 设置API密钥")]
        
        try:
            # 调用同步工作流方法
            success = await self._sync_workflows()
            
            if success:
                # 获取同步后的工作流信息
                management_data = self._load_workflow_management()
                current_project = self._get_current_project_info()
                project_name = current_project.get("name", "未知项目") if current_project else "未知项目"
                
                result_lines = [
                    f"✅ **工作流同步完成**\n",
                    f"📁 **项目**: {project_name}",
                ]
                
                if management_data:
                    workflows = management_data.get("workflows", [])
                    result_lines.append(f"📈 **工作流数量**: {len(workflows)} 个\n")
                    
                    if workflows:
                        result_lines.append("📋 **工作流列表**:")
                        for workflow in workflows:
                            result_lines.append(f"  - {workflow.get('name')} (ID: {workflow.get('id')})")
                        result_lines.append("")
                    else:
                        result_lines.append("⚠️ **注意**: 该项目没有关联的工作流\n")
                else:
                    result_lines.append("⚠️ **注意**: 无法加载工作流管理文件\n")
                
                result_lines.append("💡 **提示**: 所有旧的工作流文件已删除，当前工作流已清空，已从项目重新同步最新工作流")
                
                return [TextContent(type="text", text="\n".join(result_lines))]
            else:
                return [TextContent(type="text", text="❌ 工作流同步失败，请检查日志获取详细信息")]
                
        except Exception as e:
            logger.error(f"同步工作流失败: {e}")
            return [TextContent(type="text", text=f"❌ 同步工作流失败: {str(e)}")]

    async def _handle_send_result(self, arguments: dict) -> List[TextContent]:
        """发送任务执行结果到系统。调用后端 /api/projects/{projectId}/ai-dev/task-result"""
        if not self.current_project_id:
            return [TextContent(type="text", text="❌ 未连接到项目，请先使用 connect_to_project 连接到项目")]
        if not self.api_key:
            return [TextContent(type="text", text="❌ 未设置API密钥，请先使用 set_api_key 设置API密钥")]
        task_id = arguments.get("taskId")
        task_result = arguments.get("taskResult", "")
        if task_id is None or task_id == "":
            return [TextContent(type="text", text="❌ 参数 taskId 不能为空")]
        try:
            # 后端接口要求 taskId 为 Long，这里做数值转换
            task_id_val = int(task_id) if isinstance(task_id, str) and task_id.isdigit() else task_id
            if not isinstance(task_id_val, int):
                return [TextContent(type="text", text="❌ taskId 必须为有效数字")]
            endpoint = f"projects/{self.current_project_id}/ai-dev/task-result"
            data = {"taskId": task_id_val, "taskResult": task_result or ""}
            result = await self._call_backend_api("POST", endpoint, data=data)
            if result is not None:
                logger.info(f"任务结果已发送: taskId={task_id_val}, projectId={self.current_project_id}")
                return [TextContent(type="text", text=f"✅ 任务执行结果已提交到系统\n- 任务ID: {task_id_val}\n- 结果已由引擎处理，将根据结果决定下一步（验收/完成/用户验收）")]
            return [TextContent(type="text", text="❌ 提交任务结果失败，请检查API密钥与网络或查看日志")]
        except ValueError:
            return [TextContent(type="text", text="❌ taskId 必须为有效数字")]
        except Exception as e:
            logger.error(f"发送任务结果失败: {e}")
            return [TextContent(type="text", text=f"❌ 发送任务结果失败: {str(e)}")]


async def main():
    """主函数"""
    server = None
    try:
        server = ProjectMCPServer()
        await server.run()
    except KeyboardInterrupt:
        logger.info("⏹️ 收到中断信号，MCP服务器停止")
    except Exception as e:
        logger.error(f"❌ MCP服务器错误: {e}")
        sys.exit(1)
    finally:
        if server:
            await server._close_http_session()


if __name__ == "__main__":
    asyncio.run(main()) 