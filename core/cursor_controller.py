# -*- coding: utf-8 -*-
"""
本地 Cursor 控制器：创建文件夹、用 Cursor 打开目录、写入输入框并发送、打开新 Agent。
依赖：pywinauto (UIA)、pyautogui（备用）。配置从 config.settings 读取。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

# 延迟导入，避免循环依赖；运行时由调用方保证已配置
def _get_config():
    from ai_project_mcp.config.settings import get_settings
    return get_settings()

def _get_logger():
    from ai_project_mcp.utils.logger import get_logger
    return get_logger(__name__)

# 方案 1：优先操作“我开的那个”窗口；projectId -> 该工程对应窗口的文件夹名
_last_opened_folder_name: Optional[str] = None
_project_windows: dict[str, str] = {}


def _resolve_cursor_exe(project_root: Optional[Path] = None) -> str:
    """解析 Cursor 可执行文件路径。"""
    cfg = _get_config()
    exe = (cfg.cursor_exe or "cursor").strip()
    path = Path(exe)
    if path.is_absolute() and path.exists():
        return str(path)
    found = __import__("shutil").which(exe)
    if found:
        return found
    if sys.platform == "win32":
        for name in ("Cursor.exe", "cursor.exe"):
            if name != exe:
                found = __import__("shutil").which(name)
                if found:
                    return found
    return exe


_pywinauto_ok = False
_pyautogui_ok = False
_pyperclip_ok = False
try:
    from pywinauto import Application  # noqa: F401
    _pywinauto_ok = True
except ImportError:
    pass
try:
    import pyautogui
    _pyautogui_ok = True
except ImportError:
    pass
try:
    import pyperclip
    _pyperclip_ok = True
except ImportError:
    pass


def _project_root_path(project_root: Optional[str] = None) -> Path:
    """用于相对路径解析的根目录。"""
    if project_root:
        return Path(project_root).resolve()
    return Path.cwd()


def create_folder(
    path: str,
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    project_root: Optional[str] = None,
) -> dict[str, Any]:
    """
    创建文件夹（含多级）。路径可为绝对或相对 project_root。
    若传入 project_id，创建成功后在目录下建 .project 子目录并写入 project.json。
    """
    logger = _get_logger()
    try:
        root = _project_root_path(project_root)
        p = Path(path)
        if not p.is_absolute():
            p = root / p
        p.mkdir(parents=True, exist_ok=True)
        resolved = str(p.resolve())

        if project_id is not None and project_id != "":
            dot_project = p / ".project"
            dot_project.mkdir(parents=True, exist_ok=True)
            name = (project_name or p.name) if project_name is not None else p.name
            project_json = dot_project / "project.json"
            data = {"projectId": project_id, "projectName": name}
            project_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("已写入 %s: projectId=%s, projectName=%s", project_json, project_id, name)

        return {"ok": True, "path": resolved}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def open_cursor(
    folder_path: str,
    project_id: Optional[str] = None,
    project_root: Optional[str] = None,
) -> dict[str, Any]:
    """用 Cursor 打开指定文件夹。若传 project_id 则登记到 projectId->窗口 映射表。"""
    global _last_opened_folder_name, _project_windows
    logger = _get_logger()
    cfg = _get_config()
    try:
        root = _project_root_path(project_root)
        p = Path(folder_path)
        if not p.is_absolute():
            p = root / p
        if not p.is_dir():
            return {"ok": False, "error": f"目录不存在: {p}"}
        path_str = str(p.resolve())
        folder_name = p.name
        _last_opened_folder_name = folder_name
        if project_id:
            _project_windows[project_id] = folder_name
            logger.info("登记 projectId=%s -> 窗口(文件夹名)=%s", project_id, folder_name)
        cursor_exe = _resolve_cursor_exe(project_root)
        subprocess = __import__("subprocess")
        subprocess.Popen(
            [cursor_exe, path_str],
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(root),
        )
        return {"ok": True, "path": path_str}
    except FileNotFoundError:
        return {"ok": False, "error": f"未找到 Cursor: {_resolve_cursor_exe(project_root)}（请设置 CURSOR_EXE 为完整路径）"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _find_cursor_window(project_id: Optional[str] = None):
    """查找 Cursor 主窗口（UIA）。"""
    if not _pywinauto_ok:
        return None
    try:
        from pywinauto import Desktop
    except Exception:
        return None
    cfg = _get_config()
    logger = _get_logger()
    preferred_folder = (_project_windows.get(project_id) if project_id else None) or _last_opened_folder_name

    try:
        desktop = Desktop(backend="uia")
        cursor_windows = desktop.windows(title_re=".*Cursor.*")
        if cursor_windows and preferred_folder:
            for wnd in cursor_windows:
                try:
                    title = wnd.window_text() or ""
                    if preferred_folder in title:
                        logger.info("按标题匹配到窗口(project_id=%s): %s", project_id, title[:80])
                        return wnd
                except Exception:
                    continue
        if cursor_windows:
            logger.info("使用第一个 Cursor 窗口: %s", (cursor_windows[0].window_text() or "")[:80])
            return cursor_windows[0]
    except Exception as e:
        logger.debug("枚举 Cursor 窗口失败: %s", e)

    try:
        logger.info("尝试按标题 .*Cursor.* 连接 Cursor 进程")
        app = Application(backend="uia").connect(title_re=".*Cursor.*", timeout=cfg.cursor_ui_timeout)
        try:
            wnd = app.window(title_re=".*Cursor.*")
            if preferred_folder and wnd.window_text() and preferred_folder not in wnd.window_text():
                logger.info("当前连接到的 Cursor 窗口标题: %s", (wnd.window_text() or "")[:80])
            return wnd
        except Exception:
            return app.top_window()
    except Exception as e:
        logger.warning("按标题 .*Cursor.* 查找 Cursor 失败: %s", e)

    try:
        exe_path = _resolve_cursor_exe(None)
        if exe_path and Path(exe_path).exists():
            logger.info("尝试按可执行文件路径连接: %s", exe_path)
            app = Application(backend="uia").connect(path=exe_path, timeout=cfg.cursor_ui_timeout)
            return app.top_window()
    except Exception as e:
        logger.warning("按 path 连接 Cursor 失败: %s", e)
    return None


def _parse_hotkey(hotkey_str: str) -> list:
    """将配置中的热键字符串解析为 pyautogui.hotkey 的参数列表。"""
    if not hotkey_str or not hotkey_str.strip():
        return []
    parts = [p.strip() for p in hotkey_str.split("+") if p.strip()]
    if not parts:
        return []
    key_map = {
        "ctrl": "ctrl", "control": "ctrl",
        "alt": "alt",
        "shift": "shift",
        "win": "win", "windows": "win", "meta": "win", "cmd": "command",
        "command": "command",
    }
    modifiers = []
    main_key = None
    for p in parts:
        lower = p.lower()
        if lower in key_map:
            mod = key_map[lower]
            if mod != "command" or sys.platform != "win32":
                modifiers.append(mod if mod != "command" else "ctrl")
            else:
                modifiers.append("ctrl")
        else:
            main_key = (p.lower() if len(p) == 1 else lower)
            break
    if main_key is None and parts:
        main_key = parts[-1].lower() if len(parts[-1]) > 1 else parts[-1].lower()
    if main_key is None:
        return []
    return [*modifiers, main_key]


def open_new_agent(project_id: Optional[str] = None) -> dict[str, Any]:
    """打开新的 Agent（Chat/Composer）：先聚焦对应 projectId 的 Cursor 窗口，再发送配置的热键。"""
    if not _pyautogui_ok:
        return {"ok": False, "error": "需要 pyautogui 才能发送热键"}
    cfg = _get_config()
    keys = _parse_hotkey(cfg.cursor_open_agent_hotkey)
    if not keys:
        return {"ok": False, "error": f"无效的热键配置: {cfg.cursor_open_agent_hotkey}"}
    try:
        if _pywinauto_ok:
            wnd = _find_cursor_window(project_id)
            if wnd:
                wnd.set_focus()
                time.sleep(0.2)
        pyautogui.hotkey(*keys)
        return {"ok": True, "hotkey": cfg.cursor_open_agent_hotkey}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _paste_text_via_clipboard(text: str) -> bool:
    """用剪贴板粘贴文本（支持中文等 Unicode），粘贴后恢复原剪贴板。"""
    if not _pyperclip_ok:
        return False
    try:
        old = pyperclip.paste()
        pyperclip.copy(text)
        time.sleep(0.05)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.05)
        pyperclip.copy(old)
        return True
    except Exception as e:
        _get_logger().debug("剪贴板粘贴失败: %s", e)
        return False


def _dump_send_candidates(wnd) -> None:
    """调试用：把窗口中发送按钮候选打到日志。"""
    if not _pywinauto_ok:
        return
    want_types = ("Button", "Hyperlink", "Image")
    logger = _get_logger()
    try:
        candidates = []
        for ctrl in wnd.descendants():
            try:
                ct = getattr(ctrl.element_info, "control_type", None)
                if ct not in want_types:
                    continue
                name = (getattr(ctrl.element_info, "name", None) or "") or ""
                auto_id = (getattr(ctrl.element_info, "automation_id", None) or "") or ""
                rect = getattr(ctrl.element_info, "rectangle", None)
                candidates.append((ct, name, auto_id, rect))
            except Exception:
                continue
        if candidates:
            logger.info("发送按钮候选控件（共 %d 个）:", len(candidates))
            for i, (ct, name, auto_id, rect) in enumerate(candidates[:30]):
                logger.info("  [%d] type=%s name=%r automation_id=%r rect=%s", i, ct, name or None, auto_id or None, rect)
    except Exception as e:
        logger.debug("dump 候选控件失败: %s", e)


def _find_and_click_send_button(wnd) -> bool:
    """在 Cursor 窗口内查找“发送”按钮并点击。"""
    if not _pywinauto_ok:
        return False
    keywords = ("send", "submit", "提交", "发送", "arrow", "composer", "chat")
    exclude = ("new", "create", "newchat", "新对话", "clear", "stop", "cancel")
    want_types = ("Button", "Hyperlink", "Image")
    logger = _get_logger()
    try:
        for ctrl in wnd.descendants():
            try:
                ct = ctrl.element_info.control_type
                if ct not in want_types:
                    continue
                name = (getattr(ctrl.element_info, "name", None) or "") or ""
                auto_id = (getattr(ctrl.element_info, "automation_id", None) or "") or ""
                combined = (name + " " + auto_id).lower()
                if any(n in combined for n in exclude):
                    continue
                if any(kw in combined for kw in keywords):
                    ctrl.click()
                    logger.info("已点击发送按钮: type=%s name=%r automation_id=%r", ct, name or None, auto_id or None)
                    return True
            except Exception:
                continue
        _dump_send_candidates(wnd)
        return False
    except Exception as e:
        logger.debug("查找发送按钮失败: %s", e)
        return False


def _try_send(wnd) -> str:
    """尝试多种方式发送已输入的内容。"""
    cfg = _get_config()
    logger = _get_logger()
    try:
        logger.info("_try_send: 尝试方法1 - 按 Enter 发送")
        pyautogui.press("enter")
        return "enter"
    except Exception as e:
        logger.debug("_try_send: Enter 发送异常: %s", e)

    send_keys = _parse_hotkey(cfg.cursor_send_hotkey)
    if send_keys and send_keys != ["enter"]:
        try:
            time.sleep(0.3)
            logger.info("_try_send: 尝试方法2 - 配置热键 %s -> %s", cfg.cursor_send_hotkey, send_keys)
            pyautogui.hotkey(*send_keys)
            return f"hotkey({cfg.cursor_send_hotkey})"
        except Exception as e:
            logger.debug("_try_send: 配置热键发送异常: %s", e)

    if wnd and _pywinauto_ok:
        try:
            time.sleep(0.3)
            logger.info("_try_send: 尝试方法3 - UIA 查找发送按钮")
            if _find_and_click_send_button(wnd):
                return "send_button"
        except Exception as e:
            logger.debug("_try_send: 点击发送按钮异常: %s", e)
    return ""


def write_and_send(text: str, project_id: Optional[str] = None) -> dict[str, Any]:
    """往输入框写入内容并发送。project_id 指定时在对应工程窗口内操作。"""
    if not text:
        return {"ok": False, "error": "内容为空"}
    if not _pyautogui_ok:
        return {"ok": False, "error": "需要 pyautogui"}

    use_clipboard = any(ord(c) > 127 for c in text)
    logger = _get_logger()

    try:
        wnd = None
        if _pywinauto_ok:
            wnd = _find_cursor_window(project_id)
            if wnd:
                wnd.set_focus()
                time.sleep(0.3)

        written = False
        if _pywinauto_ok and wnd:
            for ctrl in wnd.descendants():
                try:
                    if ctrl.element_info.control_type not in ("Edit", "Document"):
                        continue
                    ctrl.set_focus()
                    time.sleep(0.2)
                    if use_clipboard and _pyperclip_ok:
                        _paste_text_via_clipboard(text)
                    else:
                        if hasattr(ctrl, "set_value"):
                            ctrl.set_value(text)
                        elif hasattr(ctrl, "set_edit_text"):
                            ctrl.set_edit_text(text)
                        else:
                            ctrl.type_keys(
                                text.replace("}", "}}").replace("{", "{{"),
                                with_spaces=True,
                            )
                    written = True
                    logger.info("write_and_send: 已通过 UIA 写入文本（长度=%d）", len(text))
                    break
                except Exception as ex:
                    logger.debug("write_and_send: UIA 写入控件失败: %s", ex)
                    continue

        if not written and _pyautogui_ok:
            logger.info("write_and_send: UIA 未成功，改用纯键盘写入")
            if use_clipboard and _pyperclip_ok:
                _paste_text_via_clipboard(text)
            else:
                pyautogui.write(text, interval=0.02)
            written = True

        if not written:
            return {"ok": False, "error": "无法写入文本到输入框"}

        time.sleep(0.5)
        method = _try_send(wnd)
        if method:
            logger.info("write_and_send: 发送成功, method=%s", method)
            return {"ok": True, "method": method}
        logger.warning("write_and_send: 所有发送方式均失败")
        return {"ok": False, "error": "文本已写入但发送失败（Enter / 热键 / 按钮均未生效）"}
    except Exception as e:
        logger.error("write_and_send: 异常: %s", e, exc_info=True)
        return {"ok": False, "error": str(e)}
