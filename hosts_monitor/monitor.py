#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
监控模块

本模块负责使用 watchfiles 库监控系统 Hosts 文件的变化，并在检测到变化时
触发对比和修复操作。该模块在后台线程中运行，可以监控文件系统事件和响应UI事件。
主要功能包括:

1. 设置 watchfiles 监控系统 Hosts 文件
2. 在后台线程中安全地运行监控
3. 提供启动/停止监控的功能
4. 实现事件去抖动/节流逻辑，避免短时间内重复处理
5. 处理UI触发的事件
6. 全程记录日志
7. 确保正确初始化并执行初始检查
8. 与现有的对比和修复模块协同工作

使用示例:
    from hosts_monitor.monitor import start_monitoring, stop_monitoring
    
    # 启动监控
    start_monitoring()
    
    # 停止监控
    stop_monitoring()
    
    # 手动触发检查
    from hosts_monitor.monitor import trigger_check
    trigger_check()
"""

import os
import time
import threading
import queue
from typing import Dict, List, Tuple, Optional, Union, Any, Literal
from pathlib import Path
from functools import wraps
from datetime import datetime, timedelta
from watchfiles import watch, Change
import asyncio

# 导入其他模块
try:
    from hosts_monitor.contrast import check_hosts, HOSTS_PATH
    from hosts_monitor.repair import repair_hosts
    from hosts_monitor.logger import logger, auto_log
    from hosts_monitor.config import get_setting
except ImportError:
    # 简单的替代日志功能，用于模块单独测试
    import logging
    logger = logging.getLogger(__name__)
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)
    
    def auto_log(func):
        return func
    
    # 默认的 Hosts 文件路径
    HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"
    
    # 替代函数
    def check_hosts() -> bool:
        return True  # Returns bool to match the actual return type
        
    def repair_hosts() -> bool:
        return True  # Always returns True to match the expected Literal[True] return type
        
    def get_setting(key, default=None):
        settings = {
            'monitor_interval': 2000,  # 监控间隔，单位毫秒
            'monitor_debounce': 3000,  # 去抖时间，单位毫秒
            'monitor_enabled': True    # 是否启用监控
        }
        return settings.get(key, default)


# 全局变量
_monitor_thread = None             # 监控线程
_stop_event = threading.Event()    # 停止事件标志
_event_queue = queue.Queue()       # 事件队列
_last_check_time = None            # 上次检查时间
_monitoring_active = False         # 监控活动状态


@auto_log
def _debounce(interval_ms: Optional[int] = None) -> bool:
    """
    去抖动逻辑，避免短时间内多次触发检查
    
    参数:
        interval_ms: 去抖间隔(毫秒)，None则使用配置值
        
    返回:
        bool: True表示可以执行检查，False表示应该跳过
    """
    global _last_check_time
    
    if interval_ms is None:
        interval_ms = get_setting('monitor_debounce', 3000)
    
    # 确保 interval_ms 为整数类型
    debounce_ms = int(interval_ms) if interval_ms is not None else 3000
    
    now = datetime.now()
    
    # 如果是首次检查，或者超过去抖时间，则执行检查
    if _last_check_time is None or \
       (now - _last_check_time) > timedelta(milliseconds=debounce_ms):
        _last_check_time = now
        return True
    
    return False


@auto_log
def _process_file_change(change_type: Change, file_path: str) -> None:
    """
    处理文件变化事件
    
    参数:
        change_type: 变化类型
        file_path: 发生变化的文件路径
    """
    # 只处理与 Hosts 文件相关的变化
    if not file_path.lower() == Path(HOSTS_PATH).resolve().as_posix().lower():
        return
    
    logger.info(f"检测到 Hosts 文件变化: {change_type.name}, 路径: {file_path}")
    
    # 应用去抖动逻辑
    if not _debounce():
        logger.info("短时间内已处理过变化，跳过本次检查")
        return
    
    # 执行对比检查，如有需要将触发修复
    if not check_hosts():
        logger.warning("检测到 Hosts 文件与规则不一致，已触发修复流程")
    else:
        logger.info("Hosts 文件内容与规则一致，无需修复")


@auto_log
def _monitor_worker() -> None:
    """
    监控工作线程函数
    负责监听文件变化和处理队列中的事件
    """
    global _monitoring_active
    
    try:
        logger.info(f"监控线程启动，监控文件: {HOSTS_PATH}")
        _monitoring_active = True
        
        # 首次启动时执行一次检查
        logger.info("执行初始 Hosts 文件检查")
        check_hosts()
        
        # 设置异步事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 运行监控循环
        hosts_dir = str(Path(HOSTS_PATH).parent)
        
        # 启动监控循环
        for changes in watch(hosts_dir, stop_event=_stop_event):
            # 处理文件变化
            for change_type, file_path in changes:
                # 将路径转换为标准格式进行比较
                norm_path = os.path.normpath(file_path).lower()
                hosts_norm_path = os.path.normpath(HOSTS_PATH).lower()
                
                if norm_path == hosts_norm_path:
                    _process_file_change(change_type, file_path)
            
            # 处理队列中的事件
            while not _event_queue.empty():
                try:
                    event = _event_queue.get_nowait()
                    if event == "check":
                        logger.info("处理队列中的检查请求")
                        check_hosts()
                    _event_queue.task_done()
                except queue.Empty:
                    break
                
            # 检查是否应该停止
            if _stop_event.is_set():
                break
                
    except Exception as e:
        logger.error(f"监控线程异常: {str(e)}")
    finally:
        logger.info("监控线程已停止")
        _monitoring_active = False


@auto_log
def start_monitoring() -> bool:
    """
    启动 Hosts 文件监控
    
    返回:
        bool: 成功返回True，失败返回False
    """
    global _monitor_thread, _stop_event
    
    # 检查监控是否已经启动
    if _monitor_thread is not None and _monitor_thread.is_alive():
        logger.info("监控已经在运行中，无需重复启动")
        return True
    
    # 重置停止事件
    _stop_event.clear()
    
    try:
        # 创建并启动监控线程
        _monitor_thread = threading.Thread(
            target=_monitor_worker,
            name="HostsMonitor",
            daemon=True  # 设为守护线程，主程序退出时自动终止
        )
        _monitor_thread.start()
        
        # 等待线程初始化完成
        for _ in range(10):  # 最多等待1秒
            if _monitoring_active:
                break
            time.sleep(0.1)
            
        logger.info("Hosts 监控已成功启动")
        return True
    except Exception as e:
        logger.error(f"启动监控失败: {str(e)}")
        return False


@auto_log
def stop_monitoring() -> bool:
    """
    停止 Hosts 文件监控
    
    返回:
        bool: 成功返回True，失败返回False
    """
    global _monitor_thread, _stop_event
    
    if _monitor_thread is None or not _monitor_thread.is_alive():
        logger.info("监控未在运行，无需停止")
        return True
    
    try:
        # 设置停止事件
        _stop_event.set()
        
        # 等待线程终止，但设置超时
        _monitor_thread.join(timeout=3.0)
        
        if _monitor_thread.is_alive():
            logger.warning("监控线程未能在超时时间内停止")
            return False
        
        # 重置线程引用
        _monitor_thread = None
        logger.info("Hosts 监控已成功停止")
        return True
    except Exception as e:
        logger.error(f"停止监控失败: {str(e)}")
        return False


@auto_log
def trigger_check() -> None:
    """
    手动触发 Hosts 文件检查
    
    此函数将检查请求添加到事件队列中，由监控线程处理
    如果监控线程未运行，则推荐使用controller._background_check()调用
    """
    global _event_queue
    
    # 如果监控未运行，则通过日志提醒，但不直接执行
    # 这样避免阻塞调用线程，尤其是UI线程
    if _monitor_thread is None or not _monitor_thread.is_alive():
        logger.info("监控未运行，触发检查将不会执行")
        # 这里不再直接执行check_hosts()，而是建议使用后台线程执行
        return
    
    # 将检查事件加入队列
    logger.info("将检查请求加入监控队列")
    _event_queue.put("check")


@auto_log
def is_monitoring_active() -> bool:
    """
    检查监控是否处于活动状态
    
    返回:
        bool: 监控活动返回True，否则返回False
    """
    return _monitoring_active


# 如果设置为启动时自动开始监控，则启动监控
if get_setting('monitor_enabled', True):
    # 使用延迟导入避免循环依赖
    import threading
    
    def _delayed_start():
        time.sleep(1)  # 延迟1秒启动，确保应用程序已完全初始化
        start_monitoring()
    
    threading.Thread(target=_delayed_start, daemon=True).start()
