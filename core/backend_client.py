"""后端 API 客户端 - 与项目管理后端通信，与 MCP 协议解耦"""
import os
from typing import Any, Dict, List, Optional

import aiohttp
import requests

from ..utils.logger import get_logger

logger = get_logger(__name__)


class BackendClient:
    """后端 API 客户端：认证、请求、项目/工作流查询"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.base_url = (base_url or os.getenv("API_BASE_URL") or "").rstrip("/") or "http://localhost:8080/aiProject/api"
        self.api_key = api_key or os.getenv("API_KEY")
        self._session: Optional[aiohttp.ClientSession] = None

    def _headers(self) -> Dict[str, str]:
        h: Dict[str, str] = {"Accept": "application/json"}
        if self.api_key:
            h["X-API-Key"] = self.api_key
        return h

    async def start(self) -> None:
        """创建并保持 HTTP 会话"""
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"Accept": "application/json"},
            )
            logger.debug("后端 HTTP 会话已创建")

    async def close(self) -> None:
        """关闭 HTTP 会话"""
        if self._session:
            await self._session.close()
            self._session = None
            logger.debug("后端 HTTP 会话已关闭")

    async def validate_api_key(self, api_key: str) -> bool:
        """验证 API 密钥是否有效"""
        try:
            await self.start()
            url = f"{self.base_url}/system/api-keys"
            async with self._session.get(url, headers={"X-API-Key": api_key}) as resp:
                if resp.status == 200:
                    logger.info("API 密钥验证成功")
                    return True
                logger.warning(f"API 密钥验证失败，状态码: {resp.status}")
                return False
        except Exception as e:
            logger.error(f"API 密钥验证异常: {e}")
            return False

    async def request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Optional[Dict[str, Any]]:
        """发起异步 API 请求"""
        try:
            await self.start()
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            headers = self._headers()
            kwargs: Dict[str, Any] = {"headers": headers, "params": params}
            if data and method.upper() in ("POST", "PUT", "PATCH"):
                headers["Content-Type"] = "application/json"
                kwargs["json"] = data
            async with self._session.request(method, url, **kwargs) as response:
                if response.status == 200:
                    return await response.json()
                if response.status == 401:
                    logger.error("API 密钥无效或已过期")
                elif response.status == 403:
                    logger.error("API 密钥权限不足")
                else:
                    text = await response.text()
                    logger.error(f"API 调用失败: {response.status} - {text}")
                return None
        except Exception as e:
            logger.error(f"API 调用异常: {e}")
            return None

    def get_project_by_channel(self, channel_no: str) -> Any:
        """根据 Channel 号获取项目（同步，供部分逻辑复用）"""
        if not self.api_key:
            return "无法连接到服务器，请先设置API密钥"
        try:
            url = f"{self.base_url}/projects/channel/{channel_no}"
            resp = requests.get(url, headers={"X-API-Key": self.api_key}, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    projects = data.get("data")
                    if isinstance(projects, list) and projects:
                        return projects[0]
            return "无法连接到服务器，请检查API密钥或网络连接"
        except Exception as e:
            logger.warning(f"根据 Channel 获取项目失败: {e}")
            return "无法连接到服务器，请检查API密钥或网络连接"

    def get_workflow_nodes(self, workflow_id: str) -> Optional[List[Dict]]:
        """根据工作流 ID 获取节点列表（同步）"""
        if not self.api_key:
            logger.error("未设置 API 密钥，无法获取工作流信息")
            return None
        try:
            url = f"{self.base_url}/workflow/node/workflow/{workflow_id}"
            resp = requests.get(url, headers={"X-API-Key": self.api_key}, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", [])
            logger.error(f"获取工作流失败: {resp.status_code} - {resp.text}")
            return None
        except Exception as e:
            logger.error(f"请求工作流节点失败: {e}")
            return None
