"""MCP 服务器核心：工具注册与请求分发，具体后端调用由 BackendClient 完成"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Resource, Tool, TextContent, ImageContent, EmbeddedResource

from ..config.settings import get_settings
from ..utils.logger import get_logger
from .backend_client import BackendClient

logger = get_logger(__name__)
settings = get_settings()


class ProjectMCPServer:
    """项目管理 MCP 服务器：协议层 + 后端客户端 + 工作区状态"""

    def __init__(self):
        self.server = Server("project-management-mcp")
        self._initialized = False

        # 后端客户端（与 MCP 解耦）
        self._api = BackendClient(
            base_url=settings.api_base_url,
            api_key=settings.api_key,
        )
        self.api_key: Optional[str] = settings.api_key
        self.backend_base_url: str = self._api.base_url

        # 项目根目录：.project 位于该目录下；默认从环境变量 WORKSPACE/AIPROJECT_WORKSPACE 或当前工作目录获取，也可由各工具参数 workspace_path 传入
        self.default_workspace = os.getenv("WORKSPACE") or os.getenv("AIPROJECT_WORKSPACE", os.getcwd())
        logger.info(f"MCP 项目根目录（默认）: {self.default_workspace}")

        self._setup_handlers()

    def _get_project_root(self, arguments: Optional[dict] = None) -> str:
        """从参数或默认值得到项目根目录。.project 目录位于项目根目录下。"""
        if arguments and arguments.get("workspace_path"):
            return arguments["workspace_path"]
        return self.default_workspace

    def _get_project_file_path(self, project_root: Optional[str] = None) -> Path:
        """当前项目配置路径：项目根目录下的 .project/project.json"""
        root = project_root or self.default_workspace
        return Path(root) / ".project" / "project.json"

    def _load_project_json(self, project_root: Optional[str] = None) -> Dict[str, str]:
        """
        从项目根目录下的 .project/project.json 读取当前项目（projectId, projectName）。
        project_root 不传时使用 default_workspace。读取不到或格式无效时抛出异常。
        """
        path = self._get_project_file_path(project_root)
        if not path.exists():
            raise FileNotFoundError(
                f"项目根目录下未找到 .project/project.json（路径: {path}），请先创建该文件并填写 projectId 和 projectName，或传入 workspace_path 指定项目根目录。"
            )
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not data.get("projectId"):
            raise ValueError("project.json 必须包含 projectId 字段。")
        return {
            "projectId": str(data["projectId"]),
            "projectName": str(data.get("projectName", "")),
        }

    async def _validate_api_key(self, api_key: str) -> bool:
        """验证 API 密钥是否有效"""
        return await self._api.validate_api_key(api_key)

    async def _call_backend_api(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """调用后端 API（委托给 BackendClient）"""
        return await self._api.request(method, endpoint, data=data, params=params)
    
    def _check_api_key(self) -> Optional[str]:
        """检查API密钥状态，返回错误信息或None"""
        if not self.api_key:
            return "❌ **未设置API密钥**\n\n请先使用 `set_api_key` 工具设置有效的API密钥。"
        return None
    
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
                        "properties": {
                            "workspace_path": {
                                "type": "string",
                                "description": "项目根目录路径（可选）。.project/project.json 位于该目录下。若不传则使用环境变量 WORKSPACE/AIPROJECT_WORKSPACE 或当前工作目录"
                            }
                        }
                    }
                ),
                Tool(
                    name="set_project",
                    description="根据 Channel 号从后端获取项目信息，并写入项目根目录的 .project/project.json（包含 projectId、projectName），后续操作将从此文件读取当前项目",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "channel": {
                                "type": "string",
                                "description": "Channel号"
                            },
                            "workspace_path": {
                                "type": "string",
                                "description": "项目根目录路径（可选）。.project 位于该目录下。若不传则使用环境变量 WORKSPACE/AIPROJECT_WORKSPACE 或当前工作目录"
                            }
                        },
                        "required": ["channel"]
                    }
                ),
                Tool(
                    name="upload_documents",
                    description="上传文档到当前项目：从项目根目录的 .project/project.json 读取 projectId，上传到对应项目",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_paths": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "要上传的文件路径列表，可以是绝对路径或相对于项目根目录的相对路径"
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
                            },
                            "workspace_path": {
                                "type": "string",
                                "description": "项目根目录路径（可选）。.project/project.json 位于该目录下。若不传则使用环境变量 WORKSPACE/AIPROJECT_WORKSPACE 或当前工作目录"
                            }
                        },
                        "required": ["file_paths"]
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
                            },
                            "workspace_path": {
                                "type": "string",
                                "description": "项目根目录路径（可选）。.project/project.json 位于该目录下。若不传则使用环境变量 WORKSPACE/AIPROJECT_WORKSPACE 或当前工作目录"
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
                elif name == "set_project":
                    return await self._handle_set_project(arguments)

                # 以下工具需要从 .project/project.json 读取 projectId（在各自 handler 内读取）
                # 检查API密钥（某些功能需要后端API）
                api_key_error = self._check_api_key()
                use_backend = self.api_key is not None
                
                if name == "upload_documents":
                    return await self._handle_upload_documents(arguments)
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
                    try:
                        project_data = self._load_project_json()
                        return json.dumps(project_data, ensure_ascii=False, indent=2)
                    except (FileNotFoundError, ValueError) as e:
                        return json.dumps({"error": str(e)}, ensure_ascii=False)
                
                elif uri.startswith("file://"):
                    file_id = uri[7:]  # 去掉 "file://"
                    files_data = getattr(self, "files_data", None) or []
                    file_info = next((f for f in files_data if f.get("id") == file_id), None)
                    if file_info:
                        return file_info.get("content", "文件内容不可用")
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
        
        if await self._validate_api_key(api_key):
            self.api_key = api_key
            self._api.api_key = api_key
            logger.info("API密钥设置成功")
            return [TextContent(type="text", text="✅ **API密钥设置成功**\n\n现在可以访问后端API服务。")]
        else:
            logger.warning("API密钥验证失败")
            return [TextContent(type="text", text="❌ **API密钥验证失败**\n\n请检查密钥是否正确或后端服务是否可用。")]
    
    async def _handle_get_api_status(self, arguments: dict) -> List[TextContent]:
        """处理获取API状态"""
        if not self.api_key:
            status_lines = [
                "📡 **API连接状态**: 未设置\n",
                f"🌐 **后端地址**: {self.backend_base_url}",
                "🔑 **API密钥**: 未设置\n",
                "⚠️ **注意**: 请使用 `set_api_key` 工具设置API密钥以访问后端服务。"
            ]
        else:
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
            status_lines.append("💡 **提示**: 后端API功能已启用，将优先使用后端数据。")

        # 当前项目：从项目根目录的 .project/project.json 读取
        project_root = self._get_project_root(arguments)
        try:
            project_data = self._load_project_json(project_root)
            status_lines.append("📋 **当前项目**: ✅\n")
            status_lines.append(f"📝 **项目名称**: {project_data.get('projectName', '')}")
            status_lines.append(f"📌 **项目ID**: {project_data.get('projectId', '')}")
            status_lines.append(f"📁 **项目根目录**: {project_root}")
        except (FileNotFoundError, ValueError):
            status_lines.append("📋 **当前项目**: 未设置（项目根目录下 .project/project.json 不存在或无效）\n")
            status_lines.append(f"💡 项目根目录: {project_root}；使用 `set_project` 工具按 Channel 写入当前项目配置，或传入 workspace_path 指定项目根。")

        return [TextContent(type="text", text="\n".join(status_lines))]
    
    def _ensure_project_info_file(self, project: Dict[str, Any], project_root: Optional[str] = None) -> bool:
        """确保项目信息.md文件存在，如果不存在则根据 project 信息创建。project_root 为项目根目录，不传则用 default_workspace。"""
        try:
            root = project_root or self.default_workspace
            project_management_dir = Path(root) / "项目管理"
            project_management_dir.mkdir(parents=True, exist_ok=True)
            
            project_info_file = project_management_dir / "项目信息.md"
            
            if project_info_file.exists():
                logger.info(f"项目信息.md文件已存在: {project_info_file}")
                return True
            
            project_name = project.get('name', '未知项目')
            project_status = project.get('status', '未知状态')
            project_description = project.get('description', '暂无描述')
            
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
    
    async def _handle_set_project(self, arguments: dict) -> List[TextContent]:
        """根据 Channel 获取项目并写入项目根目录的 .project/project.json"""
        channel = arguments.get("channel", "")
        if not channel:
            return [TextContent(type="text", text="❌ 请提供 channel 参数")]
        if not self.api_key:
            return [TextContent(type="text", text="❌ 未设置API密钥，请先使用 set_api_key 设置API密钥")]
        project = self._get_project_by_channel(channel)
        if not isinstance(project, dict) or not project:
            return [TextContent(type="text", text=f"❌ 获取项目失败: {project}")]
        project_id = str(project.get("id", ""))
        project_name = str(project.get("name", ""))
        if not project_id:
            return [TextContent(type="text", text="❌ 项目数据缺少 id")]
        project_root = self._get_project_root(arguments)
        path = self._get_project_file_path(project_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"projectId": project_id, "projectName": project_name}, f, ensure_ascii=False, indent=2)
        self._ensure_project_info_file(project, project_root)
        logger.info(f"已写入当前项目配置: {path} -> {project_name} ({project_id})")
        return [TextContent(type="text", text=f"✅ **已设置当前项目**\n📝 **项目名称**: {project_name}\n📌 **项目ID**: {project_id}\n📁 **项目根目录**: {project_root}\n📄 **配置已写入**: {path}")]
    
    def _get_project_by_channel(self, channel_no: str) -> Any:
        """根据 Channel 号获取项目（委托给 BackendClient）"""
        return self._api.get_project_by_channel(channel_no)

    async def initialize(self) -> None:
        """初始化服务器（启动后端 HTTP 会话）"""
        if not self._initialized:
            logger.info("初始化 MCP 服务器")
            await self._api.start()
            self._initialized = True
            logger.info("MCP 服务器初始化完成")

    async def run(self) -> None:
        """运行 MCP 服务器"""
        await self.initialize()
        logger.info("🚀 启动项目管理 MCP 服务器")
        logger.info("📡 等待客户端连接...")
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="project-management-mcp",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )



    async def _handle_upload_documents(self, arguments: dict) -> List[TextContent]:
        """处理文档上传"""
        project_root = self._get_project_root(arguments)
        try:
            project_data = self._load_project_json(project_root)
            project_id = project_data["projectId"]
            project_name = project_data.get("projectName", "")
        except (FileNotFoundError, ValueError) as e:
            return [TextContent(type="text", text=f"❌ {e}")]
        file_paths = arguments["file_paths"]
        document_type = arguments.get("document_type", "OTHER")
        summary = arguments.get("summary", "")
        tags = arguments.get("tags", [])
        if not self.api_key:
            return [TextContent(type="text", text="❌ 未设置API密钥，请先使用 set_api_key 设置API密钥")]
        upload_results = []
        successful_uploads = 0
        failed_uploads = 0
        for file_path in file_paths:
            try:
                result = await self._upload_single_document(
                    file_path, document_type, summary, tags, project_id, project_root
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
        summary_lines = [
            f"📊 **文档上传总结**\n",
            f"📁 **项目**: {project_name}",
            f"📈 **成功**: {successful_uploads}个文档",
            f"❌ **失败**: {failed_uploads}个文档\n",
            "📋 **详细结果**:"
        ]
        
        # 添加详细结果
        for result in upload_results:
            summary_lines.append(f"  {result}")
        
        return [TextContent(type="text", text="\n".join(summary_lines))]
    
    async def _upload_single_document(self, file_path: str, document_type: str,
                                    summary: str, tags: List[str], project_id: str, project_root: str) -> str:
        """上传单个文档。相对路径相对于 project_root。"""
        try:
            if not os.path.isabs(file_path):
                file_path = os.path.join(project_root, file_path)
            if not os.path.exists(file_path):
                return f"❌ 文件不存在: `{file_path}`"
            file_size = os.path.getsize(file_path)
            if file_size > 50 * 1024 * 1024:  # 50MB
                return f"❌ 文件过大: `{os.path.basename(file_path)}` ({file_size / 1024 / 1024:.1f}MB > 50MB)"
            file_name = os.path.basename(file_path)
            title = os.path.splitext(file_name)[0]
            await self._api.start()
            form = aiohttp.FormData()
            with open(file_path, "rb") as f:
                file_content = f.read()
            form.add_field("file", file_content, filename=file_name, content_type=self._get_mime_type(file_name))
            form.add_field("projectId", str(project_id))
            form.add_field("documentTitle", title)
            form.add_field("documentType", document_type)
            form.add_field("accessLevel", "CONFIDENTIAL")
            if summary:
                form.add_field("summary", summary)
            for tag in tags or []:
                form.add_field("tags", tag)
            url = f"{self.backend_base_url}/document-files/upload-and-create"
            headers = {"X-API-Key": self.api_key} if self.api_key else {}
            logger.info(f"开始上传文档: {file_name} 到项目 {project_id}")
            async with self._api._session.post(url, data=form, headers=headers) as response:
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

    async def _handle_send_result(self, arguments: dict) -> List[TextContent]:
        """发送任务执行结果到系统。调用后端 /api/projects/{projectId}/ai-dev/task-result"""
        project_root = self._get_project_root(arguments)
        try:
            project_data = self._load_project_json(project_root)
            project_id = project_data["projectId"]
        except (FileNotFoundError, ValueError) as e:
            return [TextContent(type="text", text=f"❌ {e}")]
        if not self.api_key:
            return [TextContent(type="text", text="❌ 未设置API密钥，请先使用 set_api_key 设置API密钥")]
        task_id = arguments.get("taskId")
        task_result = arguments.get("taskResult", "")
        if task_id is None or task_id == "":
            return [TextContent(type="text", text="❌ 参数 taskId 不能为空")]
        try:
            task_id_val = int(task_id) if isinstance(task_id, str) and task_id.isdigit() else task_id
            if not isinstance(task_id_val, int):
                return [TextContent(type="text", text="❌ taskId 必须为有效数字")]
            endpoint = f"projects/{project_id}/ai-dev/task-result"
            data = {"taskId": task_id_val, "taskResult": task_result or ""}
            result = await self._call_backend_api("POST", endpoint, data=data)
            if result is not None:
                logger.info(f"任务结果已发送: taskId={task_id_val}, projectId={project_id}")
                return [TextContent(type="text", text=f"✅ 任务执行结果已提交到系统\n- 任务ID: {task_id_val}\n- 结果已由引擎处理，将根据结果决定下一步（验收/完成/用户验收）")]
            return [TextContent(type="text", text="❌ 提交任务结果失败，请检查API密钥与网络或查看日志")]
        except ValueError:
            return [TextContent(type="text", text="❌ taskId 必须为有效数字")]
        except Exception as e:
            logger.error(f"发送任务结果失败: {e}")
            return [TextContent(type="text", text=f"❌ 发送任务结果失败: {str(e)}")]

