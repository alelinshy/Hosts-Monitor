# -*- coding: utf-8 -*-
"""
日志模块
- 全局日志
- 软件所有的提示信息和操作都需要输出日志
- 跟随程序的操作输出日志
- 所有输出的日志同步更新到UI界面的日志显示界面
- 全部以中文输出
"""

import logging
import os
import sys
from datetime import datetime
from typing import Optional, Callable

# 定义日志格式
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class HostsMonitorLogger:
    """Hosts Monitor 日志类"""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(HostsMonitorLogger, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, log_level: int = logging.INFO):
        if self._initialized:
            return
            
        self.logger = logging.getLogger("hosts_monitor")
        self.logger.setLevel(log_level)
        
        # 添加控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        self.logger.addHandler(console_handler)
        
        # 确定软件运行目录
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # PyInstaller打包后的运行目录
            base_dir = os.path.dirname(sys.executable)
        else:
            # 开发环境运行目录
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 创建日志目录，直接在软件运行目录下
        log_dir = os.path.join(base_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # 添加文件处理器
        log_file = os.path.join(log_dir, f"hosts_monitor_{datetime.now().strftime('%Y%m%d')}.log")
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        self.logger.addHandler(file_handler)
        
        # UI更新回调
        self.ui_update_callback = None
        
        self._initialized = True
    
    def set_ui_callback(self, callback: Callable[[str], None]) -> None:
        """设置UI更新回调函数"""
        self.ui_update_callback = callback
    
    def _log(self, level: int, message: str) -> None:
        """内部日志记录方法"""
        self.logger.log(level, message)
        if self.ui_update_callback:
            timestamp = datetime.now().strftime(DATE_FORMAT)
            level_name = logging.getLevelName(level)
            log_message = f"{timestamp} [{level_name}] {message}"
            self.ui_update_callback(log_message)
    
    def debug(self, message: str) -> None:
        """记录调试级别日志"""
        self._log(logging.DEBUG, message)
    
    def info(self, message: str) -> None:
        """记录信息级别日志"""
        self._log(logging.INFO, message)
    
    def warning(self, message: str) -> None:
        """记录警告级别日志"""
        self._log(logging.WARNING, message)
    
    def error(self, message: str) -> None:
        """记录错误级别日志"""
        self._log(logging.ERROR, message)
    
    def critical(self, message: str) -> None:
        """记录严重错误级别日志"""
        self._log(logging.CRITICAL, message)


# 全局日志对象
logger = HostsMonitorLogger()

# 导出简便接口
debug = logger.debug
info = logger.info
warning = logger.warning
error = logger.error
critical = logger.critical
set_ui_callback = logger.set_ui_callback
