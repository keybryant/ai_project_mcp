#!/usr/bin/env python3
"""项目管理 MCP 应用主入口。启动 MCP 的同时在后台启动 WebSocket 客户端监听后端命令。"""

import asyncio
import sys
from pathlib import Path

# 保证以包方式运行：将项目根目录的父目录加入 path，以便 import ai_project_mcp
_root = Path(__file__).resolve().parent.parent
if _root not in sys.path:
    sys.path.insert(0, str(_root))

from ai_project_mcp.core.mcp_server import ProjectMCPServer
from ai_project_mcp.core.ws_client import run_client as run_ws_client
from ai_project_mcp.utils.logger import get_logger

logger = get_logger(__name__)


async def main() -> None:
    logger.info("🚀 项目管理 MCP 应用启动")
    server = None
    ws_task = None
    try:
        # 后台启动 WebSocket 客户端（连接后端，接收 create_folder / open_cursor / write_and_send / open_new_agent 等命令）
        ws_task = asyncio.create_task(run_ws_client())
        server = ProjectMCPServer()
        await server.run()
    except KeyboardInterrupt:
        logger.info("⏹️ 收到中断信号，MCP 服务器停止")
    except Exception as e:
        logger.error(f"❌ MCP 服务器错误: {e}")
        sys.exit(1)
    finally:
        if ws_task is not None and not ws_task.done():
            ws_task.cancel()
            try:
                await ws_task
            except asyncio.CancelledError:
                pass
        if server is not None:
            await server._api.close()


if __name__ == "__main__":
    asyncio.run(main())
