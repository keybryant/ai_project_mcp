# -*- coding: utf-8 -*-
"""
WebSocket 客户端：连接后端，接收 JSON 命令并调用 cursor_controller，返回结果。
与 MCP 同时启动时在后台运行。协议：后端发 { "id", "cmd", "params" }，回 { "id", "type", "data" }。
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from ..config.settings import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


def _get_ws_url() -> str:
    """从配置得到 WebSocket 地址：ws://<后端地址>/ws/ai-tool。"""
    cfg = get_settings()
    if cfg.cursor_ws_url and cfg.cursor_ws_url.strip():
        return cfg.cursor_ws_url.strip()
    base = (cfg.cursor_backend_address or "").strip()
    if not base:
        return ""
    if base.startswith("http://"):
        base = base[7:]
    elif base.startswith("https://"):
        base = base[8:]
    if not base.startswith("ws://") and not base.startswith("wss://"):
        base = "ws://" + base
    return base.rstrip("/") + "/ws/ai-tool"


async def _run_sync(fn, *args, **kwargs) -> Any:
    """在线程池中执行同步函数。"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


async def _handle_command(cmd: str, params: Optional[dict] = None) -> dict[str, Any]:
    """根据 cmd 调用 cursor_controller 并返回 data。"""
    try:
        from . import cursor_controller as ctrl
    except ImportError:
        return {"ok": False, "error": "未安装 Cursor 控制依赖（pywinauto/pyautogui）"}
    params = params or {}
    default_workspace = __import__("os").getenv("WORKSPACE") or __import__("os").getenv("AIPROJECT_WORKSPACE", __import__("os").getcwd())
    try:
        if cmd == "create_folder":
            path = params.get("path", "")
            project_id = params.get("projectId")
            project_name = params.get("projectName")
            project_root = params.get("workspace_path") or default_workspace
            return await _run_sync(ctrl.create_folder, path, project_id, project_name, project_root)
        if cmd == "open_cursor":
            path = params.get("path", "")
            project_id = params.get("projectId")
            project_root = params.get("workspace_path") or default_workspace
            return await _run_sync(ctrl.open_cursor, path, project_id, project_root)
        if cmd == "write_and_send":
            text = params.get("text", "")
            project_id = params.get("projectId")
            return await _run_sync(ctrl.write_and_send, text, project_id)
        if cmd == "open_new_agent":
            project_id = params.get("projectId")
            return await _run_sync(ctrl.open_new_agent, project_id)
        return {"ok": False, "error": f"未知命令: {cmd}"}
    except Exception as e:
        logger.exception("执行命令异常")
        return {"ok": False, "error": str(e)}


def _response_payload(msg_id: Any, msg_type: str, data: dict, project_id: Optional[str] = None) -> dict:
    payload = {"id": msg_id, "type": msg_type, "data": data}
    if project_id is not None:
        payload["projectId"] = project_id
    return payload


async def _process_message(ws, raw: str) -> None:
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError as e:
        out = json.dumps({"type": "error", "data": {"error": f"JSON 解析失败: {e}"}}, ensure_ascii=False)
        await ws.send(out)
        return
    msg_id = msg.get("id")
    cmd = msg.get("cmd")
    params = msg.get("params") or {}
    project_id = params.get("projectId")
    if not cmd:
        return
    logger.info("[WS 收到] %s", raw[:200])
    data = await _handle_command(cmd, params)
    out = json.dumps(_response_payload(msg_id, "result", data, project_id), ensure_ascii=False)
    logger.info("[WS 发送] %s", out[:200])
    await ws.send(out)


async def run_client() -> None:
    """连接后端 WebSocket，循环重连；供与 MCP 同时启动时作为后台任务。"""
    try:
        import websockets
        from websockets.exceptions import ConnectionClosed
    except ImportError:
        logger.warning("未安装 websockets，跳过 WebSocket 客户端启动。pip install websockets")
        return
    cfg = get_settings()
    interval = max(1.0, cfg.reconnect_interval)
    while True:
        try:
            url = _get_ws_url()
            if not url or not url.replace("ws://", "").replace("wss://", "").strip():
                logger.debug("未配置 CURSOR_WS_URL 或 CURSOR_BACKEND_ADDRESS，%s 秒后重试...", interval)
                await asyncio.sleep(interval)
                continue
            logger.info("WebSocket 正在连接 %s ...", url)
            async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                logger.info("WebSocket 已连接")
                async for raw in ws:
                    await _process_message(ws, raw)
        except ConnectionClosed as e:
            logger.warning("WebSocket 连接关闭: %s", e)
        except asyncio.CancelledError:
            logger.info("WebSocket 客户端任务已取消")
            raise
        except Exception as e:
            logger.exception("WebSocket 连接或接收异常: %s", e)
        logger.info("%s 秒后重连...", interval)
        await asyncio.sleep(interval)
