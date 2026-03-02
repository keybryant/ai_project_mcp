#!/usr/bin/env python3
"""项目管理 MCP 应用主入口。仅启动 MCP 服务器；WebSocket 客户端已拆至独立项目 ai_project_ws_client。"""

import asyncio
import sys
from pathlib import Path

# 保证以包方式运行：将项目根目录的父目录加入 path，以便 import ai_project_mcp
_root = Path(__file__).resolve().parent.parent
if _root not in sys.path:
    sys.path.insert(0, str(_root))

from ai_project_mcp.core.mcp_server import ProjectMCPServer
from ai_project_mcp.utils.logger import get_logger

logger = get_logger(__name__)


async def main() -> None:
    logger.info("🚀 项目管理 MCP 应用启动")
    server = None
    try:
        server = ProjectMCPServer()
        await server.run()
    except KeyboardInterrupt:
        logger.info("⏹️ 收到中断信号，MCP 服务器停止")
    except Exception as e:
        logger.error(f"❌ MCP 服务器错误: {e}")
        sys.exit(1)
    finally:
        if server is not None:
            await server._api.close()


if __name__ == "__main__":
    asyncio.run(main())
