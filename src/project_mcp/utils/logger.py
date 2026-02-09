"""日志工具模块"""
import sys
import io
import os
from pathlib import Path
from loguru import logger as loguru_logger
from typing import Optional

# 全局logger实例
_logger_initialized = False

def setup_logger(log_level: str = "INFO", log_file: Optional[Path] = None):
    """设置日志配置"""
    global _logger_initialized
    
    if _logger_initialized:
        return

    # 在 Windows / Cursor 等环境下强制使用 UTF-8，避免中文乱码
    # 特别是 MCP 通过 stdio 与 Cursor 通信时，必须保证 stdout/stderr 是 UTF-8
    try:
        if os.name == "nt":
            # 只在编码不是 UTF-8 时包一层 TextIOWrapper，避免重复包装
            if getattr(sys.stderr, "encoding", "").lower() != "utf-8":
                sys.stderr = io.TextIOWrapper(
                    sys.stderr.buffer,
                    encoding="utf-8",
                    errors="replace",
                )
    except Exception:
        # 如果包装失败，不影响后续日志输出，只是可能仍有乱码
        pass
    
    # 移除默认处理器
    loguru_logger.remove()
    
    # 添加控制台输出
    loguru_logger.add(
        sys.stderr,
        level=log_level,
        # 关闭颜色，避免在 Cursor 的 MCP 输出里出现 ESC[32m 之类的转义序列
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        colorize=False,
    )
    
    # 添加文件输出（如果指定了文件）
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        loguru_logger.add(
            str(log_file),
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation="10 MB",
            retention="7 days",
            compression="zip"
        )
    
    _logger_initialized = True

def get_logger(name: str):
    """获取logger实例"""
    if not _logger_initialized:
        setup_logger()
    
    return loguru_logger.bind(name=name)


# 便捷的日志记录函数
def log_debug(message: str, **kwargs) -> None:
    """记录调试日志"""
    logger.debug(message, **kwargs)


def log_info(message: str, **kwargs) -> None:
    """记录信息日志"""
    logger.info(message, **kwargs)


def log_warning(message: str, **kwargs) -> None:
    """记录警告日志"""
    logger.warning(message, **kwargs)


def log_error(message: str, exception: Optional[Exception] = None, **kwargs) -> None:
    """记录错误日志"""
    if exception:
        logger.error(f"{message}: {exception}", **kwargs)
    else:
        logger.error(message, **kwargs)


def log_critical(message: str, exception: Optional[Exception] = None, **kwargs) -> None:
    """记录严重错误日志"""
    if exception:
        logger.critical(f"{message}: {exception}", **kwargs)
    else:
        logger.critical(message, **kwargs)


# 日志装饰器
def log_function_call(func):
    """装饰器：记录函数调用"""
    def wrapper(*args, **kwargs):
        logger.debug(f"调用函数 {func.__name__} with args={args}, kwargs={kwargs}")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"函数 {func.__name__} 返回: {result}")
            return result
        except Exception as e:
            logger.error(f"函数 {func.__name__} 执行出错: {e}")
            raise
    return wrapper


def log_async_function_call(func):
    """装饰器：记录异步函数调用"""
    async def wrapper(*args, **kwargs):
        logger.debug(f"调用异步函数 {func.__name__} with args={args}, kwargs={kwargs}")
        try:
            result = await func(*args, **kwargs)
            logger.debug(f"异步函数 {func.__name__} 返回: {result}")
            return result
        except Exception as e:
            logger.error(f"异步函数 {func.__name__} 执行出错: {e}")
            raise
    return wrapper


class LogContext:
    """日志上下文管理器"""
    
    def __init__(self, context_name: str, **context_data):
        self.context_name = context_name
        self.context_data = context_data
        self.logger = logger.bind(context=context_name, **context_data)
    
    def __enter__(self):
        self.logger.info(f"进入上下文: {self.context_name}")
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.logger.error(f"上下文 {self.context_name} 执行出错: {exc_val}")
        else:
            self.logger.info(f"退出上下文: {self.context_name}")


class AsyncLogContext:
    """异步日志上下文管理器"""
    
    def __init__(self, context_name: str, **context_data):
        self.context_name = context_name
        self.context_data = context_data
        self.logger = logger.bind(context=context_name, **context_data)
    
    async def __aenter__(self):
        self.logger.info(f"进入异步上下文: {self.context_name}")
        return self.logger
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.logger.error(f"异步上下文 {self.context_name} 执行出错: {exc_val}")
        else:
            self.logger.info(f"退出异步上下文: {self.context_name}")


# 性能日志记录
class PerformanceLogger:
    """性能日志记录器"""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        self.logger = logger.bind(operation=operation_name)
    
    def start(self):
        """开始计时"""
        import time
        self.start_time = time.time()
        self.logger.info(f"开始执行操作: {self.operation_name}")
    
    def end(self):
        """结束计时"""
        if self.start_time is None:
            self.logger.warning(f"操作 {self.operation_name} 未开始计时")
            return
        
        import time
        duration = time.time() - self.start_time
        self.logger.info(f"操作 {self.operation_name} 完成，耗时: {duration:.2f}秒")
        return duration
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end()
        if exc_type:
            self.logger.error(f"操作 {self.operation_name} 执行出错: {exc_val}")


# 模块级别的日志器实例
module_logger = get_logger(__name__) 