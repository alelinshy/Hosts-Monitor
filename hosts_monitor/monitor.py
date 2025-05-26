# -*- coding: utf-8 -*-
"""
监控模块
- 使用watchfiles监控hosts文件变化
- 监控配置文件变化
"""

import os
import sys
import time
import threading
from typing import Callable, Optional, Set, List, Dict, Any
import watchfiles
from watchfiles import watch, Change

from . import logger
from .config import config


class HostsMonitor:
    """Hosts文件监控类"""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(HostsMonitor, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # hosts文件路径
        self.hosts_path = self._get_hosts_path()
        
        # 配置文件路径
        self.config_path = config.config_path
        
        # 上次处理时间
        self.last_process_time = 0
        
        # 去抖动时间（秒）
        self.debounce_time = 2
        
        # 监控线程
        self.monitor_thread = None
        self.stop_event = threading.Event()
        
        # 比对回调
        self.contrast_callback = None
        
        self._initialized = True
        
        logger.info("监控模块初始化完成")
        logger.info(f"watchfiles版本: {watchfiles.__version__}")
    
    def _get_hosts_path(self) -> str:
        """获取hosts文件路径"""
        if sys.platform.startswith('win'):
            return os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'drivers', 'etc', 'hosts')
        else:
            return '/etc/hosts'
    
    def set_contrast_callback(self, callback: Callable[[], None]) -> None:
        """设置比对回调函数"""
        self.contrast_callback = callback
    
    def _debounce(self) -> bool:
        """去抖动/节流，避免短时间内重复处理"""
        current_time = time.time()
        if current_time - self.last_process_time < self.debounce_time:
            logger.debug(f"触发去抖动逻辑，跳过此次处理 (间隔: {current_time - self.last_process_time:.2f}秒)")
            return False
        
        self.last_process_time = current_time
        return True
    
    def _monitor_files(self) -> None:
        """监控文件变化的内部方法"""
        try:
            # 检查监控的文件是否存在
            valid_paths = []
            
            if os.path.exists(self.hosts_path):
                valid_paths.append(self.hosts_path)
            else:
                logger.warning(f"hosts文件不存在: {self.hosts_path}")
            
            if os.path.exists(self.config_path):
                valid_paths.append(self.config_path)
            else:
                logger.warning(f"配置文件不存在: {self.config_path}")
            
            if not valid_paths:
                logger.error("没有可监控的有效文件路径")
                return
            
            logger.info(f"开始监控文件: {valid_paths}")
            
            # 初始化完成后触发一次比对
            if self.contrast_callback:
                self.contrast_callback()
                
            # 直接监控指定文件列表
            watch_kwargs = {
                "watch_filter": None,  # 不过滤任何事件
                "stop_event": self.stop_event,
                "debounce": 500,  # 内部去抖动，单位毫秒
                "debug": False,  # 启用调试以获取更多信息
                "yield_on_timeout": True,  # 即使没有变化也定期返回，使停止更可靠
            }
            
            try:
                # 直接传入文件路径列表，而不是目录
                for changes in watch(*valid_paths, **watch_kwargs):
                    if self.stop_event.is_set():
                        break
                    
                    # 如果没有变化则继续循环
                    if not changes:
                        continue
                    
                    if not self._debounce():
                        continue
                    
                    # 检查是否有我们关注的文件变化
                    for change_type, path in changes:
                        if path in valid_paths:
                            logger.info(f"检测到文件变化: {path} (变化类型: {change_type})")
                            
                            # 触发对比模块
                            if self.contrast_callback:
                                logger.info("触发对比模块")
                                self.contrast_callback()
                                break  # 一批变化只需触发一次比对
            
            except Exception as e:
                logger.error(f"监控文件时发生错误: {str(e)}")
                
                # 错误后短暂延迟并重试
                if not self.stop_event.is_set():
                    logger.info("3秒后尝试重新启动文件监控...")
                    self.stop_event.wait(3.0)
                    if not self.stop_event.is_set():
                        return self._monitor_files()  # 递归调用重新开始监控
        
        except Exception as e:
            logger.error(f"监控文件主循环发生错误: {str(e)}")
        finally:
            logger.info("文件监控已停止")
    
    def start(self) -> None:
        """启动监控"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.warning("监控已在运行中")
            return
        
        self.stop_event.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_files, daemon=True)
        self.monitor_thread.start()
        logger.info("监控模块已启动")
    
    def stop(self) -> None:
        """停止监控"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.info("正在停止监控模块...")
            self.stop_event.set()
            try:
                self.monitor_thread.join(timeout=3.0)
                logger.info("监控模块已停止")
            except Exception as e:
                logger.error(f"停止监控模块时发生错误: {str(e)}")
                
            if self.monitor_thread.is_alive():
                logger.warning("监控线程未能在指定时间内退出")
    
    def get_hosts_path(self) -> str:
        """获取hosts文件路径"""
        return self.hosts_path

    def set_debounce_time(self, seconds: float) -> None:
        """设置去抖动时间（秒）
        
        参数:
            seconds: 去抖动时间（秒），通常由毫秒转换而来
        """
        if seconds <= 0:
            logger.warning(f"去抖动时间必须大于0，设置为默认值2秒")
            self.debounce_time = 2
        else:
            self.debounce_time = seconds
            logger.info(f"监控去抖动时间已设置为 {self.debounce_time:.2f} 秒（{self.debounce_time * 1000:.0f}毫秒）")
    

# 全局监控对象
monitor = HostsMonitor()

# 为兼容导入添加
__all__ = ['monitor']
