#!/usr/bin/env python3
"""项目管理MCP应用主入口"""

import asyncio
import sys
from pathlib import Path

# 添加src目录到Python路径
src_dir = Path(__file__).parent.parent
sys.path.insert(0, str(src_dir))

from project_mcp.core.mcp_server import ProjectMCPServer
from project_mcp.utils.logger import get_logger

logger = get_logger(__name__)

async def main():
    """主函数"""
    logger.info("🚀 项目管理MCP应用启动")
    
    try:
        # 创建并运行MCP服务器
        server = ProjectMCPServer()
        await server.run()
        
    except KeyboardInterrupt:
        logger.info("⏹️ 收到中断信号，MCP服务器停止")
    except Exception as e:
        logger.error(f"❌ MCP服务器错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 