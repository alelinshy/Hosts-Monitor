#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
日志模块

本模块提供全局日志记录功能，结合Python内置的logging模块和装饰器机制
自动记录程序运行信息。初始化日志系统，输出软件运行过程中的重要信息到
日志文件，并提供装饰器用于自动记录函数调用详情。所有日志均采用中文描述，
并实现自动同步到UI界面显示。

使用示例:
    1. 直接使用日志记录函数:
       from hosts_monitor.logger import logger
       logger.info("这是一条普通信息")
       logger.warning("这是一条警告信息")
       logger.error("这是一条错误信息")
       
    2. 使用自动日志装饰器:
       from hosts_monitor.logger import auto_log
       
       @auto_log
       def my_function(param1, param2):
           # 函数体...
           return result
"""

import os
import logging
import datetime
import sys
from functools import wraps
from pathlib import Path
from typing import Callable, Any, Optional, List, Dict, Union

# PyQt6 导入，用于UI信号机制
try:
    from PyQt6.QtCore import QObject, pyqtSignal
    
    # 创建一个全局QObject类，用于发送日志信号
    class QtLogSignalEmitter(QObject):
        """日志信号发射器，用于将日志消息同步到UI"""
        # 定义一个Qt信号，当有新日志产生时发送
        new_log = pyqtSignal(str, str)  # 参数: 日志级别, 日志内容
    
    # 使用Qt版本的信号发射器
    LogSignalEmitter = QtLogSignalEmitter
except ImportError:
    # 如果在没有PyQt6的环境中运行，提供一个模拟的QObject类
    class MockQObject:
        pass
    
    # 定义一个MockSignal类型用于模拟PyQt信号
    class MockSignal:
        def connect(self, callback):
            pass
        
        def emit(self, *args):
            pass
    
    def create_mock_signal(*args, **kwargs) -> MockSignal:
        return MockSignal()
    
    class MockLogSignalEmitter(MockQObject):
        """日志信号发射器的模拟版本"""
        def __init__(self):
            self.new_log = create_mock_signal(str, str)
            
        def connect(self, callback):
            pass
    
    # 使用模拟版本的信号发射器
    LogSignalEmitter = MockLogSignalEmitter


# 创建全局信号发射器实例
log_emitter = LogSignalEmitter()


class UILogHandler(logging.Handler):
    """自定义日志处理器，将日志发送到UI界面"""
    
    def __init__(self):
        super().__init__()
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    
    def emit(self, record):
        """发送日志记录到UI"""
        try:
            # 格式化日志消息
            msg = self.format(record)
            # 发送信号，将日志消息推送到UI
            log_emitter.new_log.emit(record.levelname, msg)
        except Exception:
            self.handleError(record)


def initialize_logger() -> logging.Logger:
    """
    初始化日志系统
    
    返回:
        logging.Logger: 配置好的日志记录器
    """
    # 创建日志记录器
    logger = logging.getLogger("hosts_monitor")
    logger.setLevel(logging.INFO)
    
    # 避免重复添加处理器
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # 确定日志文件路径
    # 如果是通过PyInstaller打包的程序，使用应用程序根目录
    if getattr(sys, 'frozen', False):
        app_path = os.path.dirname(sys.executable)
    else:
        app_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    log_dir = os.path.join(app_path, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 创建日期格式的日志文件名
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    log_file = os.path.join(log_dir, f'hosts_monitor_{today}.log')
    
    # 创建文件处理器，指定编码为 utf-8 以支持中文
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    # 添加处理器到记录器
    logger.addHandler(file_handler)
    
    # 添加UI处理器
    ui_handler = UILogHandler()
    logger.addHandler(ui_handler)
    
    # 记录初始化完成信息
    logger.info("日志系统初始化完成")
    
    return logger


# 初始化全局日志记录器
logger = initialize_logger()


def auto_log(func: Callable) -> Callable:
    """
    自动记录函数调用的装饰器
    
    参数:
        func: 被装饰的函数
        
    返回:
        装饰后的函数
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 记录函数调用信息
        args_str = ', '.join([str(arg) for arg in args])
        kwargs_str = ', '.join([f'{k}={v}' for k, v in kwargs.items()])
        params = f"{args_str}{', ' if args_str and kwargs_str else ''}{kwargs_str}"
        
        # 限制参数长度，避免日志过长
        if len(params) > 200:
            params = params[:200] + "... [参数过长已截断]"
        
        logger.info(f"调用函数: {func.__name__}({params})")
        
        # 调用原始函数并捕获结果
        try:
            result = func(*args, **kwargs)
            
            # 记录返回值，同样限制长度
            result_str = str(result)
            if len(result_str) > 200:
                result_str = result_str[:200] + "... [返回值过长已截断]"
            
            logger.info(f"函数返回: {func.__name__} -> {result_str}")
            return result
        except Exception as e:
            # 记录异常信息
            logger.error(f"函数异常: {func.__name__} -> {str(e)}")
            raise  # 重新抛出异常，让调用者处理
    
    return wrapper


def connect_to_ui(callback_function: Callable[[str, str], None]) -> None:
    """
    连接日志信号到UI回调函数
    
    参数:
        callback_function: 接收日志级别和日志消息的回调函数
    """
    log_emitter.new_log.connect(callback_function)


def log_function_call(func_name: str, *args, **kwargs) -> None:
    """
    手动记录函数调用信息
    
    参数:
        func_name: 函数名称
        *args: 位置参数
        **kwargs: 关键字参数
    """
    args_str = ', '.join([str(arg) for arg in args])
    kwargs_str = ', '.join([f'{k}={v}' for k, v in kwargs.items()])
    params = f"{args_str}{', ' if args_str and kwargs_str else ''}{kwargs_str}"
    
    if len(params) > 200:
        params = params[:200] + "... [参数过长已截断]"
    
    logger.info(f"调用函数: {func_name}({params})")


def log_function_return(func_name: str, result: Any) -> None:
    """
    手动记录函数返回值
    
    参数:
        func_name: 函数名称
        result: 返回值
    """
    result_str = str(result)
    if len(result_str) > 200:
        result_str = result_str[:200] + "... [返回值过长已截断]"
    
    logger.info(f"函数返回: {func_name} -> {result_str}")


# 扩展日志功能，可根据需要添加更多辅助函数

def log_startup() -> None:
    """记录程序启动信息"""
    # 导入版本信息
    try:
        from hosts_monitor.version import VERSION
        logger.info(f"Hosts Monitor v{VERSION} 启动")
    except ImportError:
        logger.info("Hosts Monitor 启动")


def log_shutdown() -> None:
    """记录程序关闭信息"""
    logger.info("Hosts Monitor 关闭")


def log_config_loaded(config_path: str) -> None:
    """
    记录配置文件加载信息
    
    参数:
        config_path: 配置文件路径
    """
    logger.info(f"配置文件已加载: {config_path}")


def log_repair_attempt(hosts_file: str) -> None:
    """
    记录hosts文件修复尝试信息
    
    参数:
        hosts_file: hosts文件路径
    """
    logger.info(f"尝试修复hosts文件: {hosts_file}")


def log_repair_success(hosts_file: str) -> None:
    """
    记录hosts文件修复成功信息
    
    参数:
        hosts_file: hosts文件路径
    """
    logger.info(f"hosts文件修复成功: {hosts_file}")


def log_repair_failure(hosts_file: str, error: str) -> None:
    """
    记录hosts文件修复失败信息
    
    参数:
        hosts_file: hosts文件路径
        error: 错误信息
    """
    logger.error(f"hosts文件修复失败: {hosts_file}, 错误: {error}")


def log_rules_update(rule_count: int) -> None:
    """
    记录规则更新信息
    
    参数:
        rule_count: 更新的规则数量
    """
    logger.info(f"更新了 {rule_count} 条规则")


def log_monitor_start() -> None:
    """记录监控模块启动信息"""
    logger.info("监控模块启动")


def log_monitor_stop() -> None:
    """记录监控模块停止信息"""
    logger.info("监控模块停止")


def log_file_change(file_path: str) -> None:
    """
    记录文件变更信息
    
    参数:
        file_path: 发生变更的文件路径
    """
    logger.info(f"检测到文件变更: {file_path}")


# 如果直接运行此文件，则执行简单的测试
if __name__ == "__main__":
    # 简单测试日志功能
    logger.info("这是一条测试信息")
    logger.warning("这是一条警告信息")
    logger.error("这是一条错误信息")
    
    # 测试装饰器
    @auto_log
    def test_function(a, b, c=None):
        return a + b
    
    result = test_function(1, 2, c="测试")
    print(f"测试结果: {result}")
