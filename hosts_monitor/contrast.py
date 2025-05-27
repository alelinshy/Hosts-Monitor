# -*- coding: utf-8 -*-
"""
对比模块
- 对比hosts文件内容与配置文件中的hosts数据
- 启动修复模块
"""

import os
import threading
from typing import Callable, Tuple

from . import logger
from .config import config
from .monitor import monitor


class ContrastModule:
    """对比模块类"""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ContrastModule, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 修复回调
        self.repair_callback = None
        
        # 工作线程
        self.contrast_thread = None
        
        self._initialized = True
    
    def set_repair_callback(self, callback: Callable[[], None]) -> None:
        """设置修复回调函数"""
        self.repair_callback = callback
    
    def _read_hosts_file(self) -> Tuple[bool, str]:
        """读取hosts文件内容"""
        hosts_path = monitor.get_hosts_path()
        
        try:
            if not os.path.exists(hosts_path):
                logger.error(f"hosts文件不存在: {hosts_path}")
                return False, ""
            
            with open(hosts_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            logger.info(f"成功读取hosts文件: {hosts_path}")
            return True, content
        except Exception as e:
            logger.error(f"读取hosts文件失败: {str(e)}")
            return False, ""
    
    def _check_hosts_content(self, hosts_content: str, config_hosts_data: str) -> bool:
        """检查hosts文件内容是否完整包含配置数据"""
        # 获取配置的hosts数据行（忽略空行，包含所有注释行）
        config_lines = []
        is_hosts_monitor_data = False
        
        for line in config_hosts_data.splitlines():
            stripped_line = line.strip()
            if not stripped_line:
                continue
                
            # 特殊处理"# Hosts Monitor 数据"等注释行
            if "# Hosts Monitor 数据" in stripped_line:
                is_hosts_monitor_data = True
                config_lines.append(stripped_line)
            # 所有注释行都加入到检查中，不再限制只检查"# Hosts Monitor 数据"部分的注释
            elif stripped_line.startswith('#'):
                config_lines.append(stripped_line)
            # 非注释行正常处理
            elif not stripped_line.startswith('#'):
                config_lines.append(stripped_line)
        
        if not config_lines:
            logger.info("配置文件中没有有效的hosts数据")
            return True
        
        # 获取hosts文件内容行
        hosts_lines = [line.strip() for line in hosts_content.splitlines()]
        
        # 检查每行配置是否存在于hosts文件中
        missing_lines = []
        for config_line in config_lines:
            if config_line not in hosts_lines:
                missing_lines.append(config_line)
        
        if missing_lines:
            logger.info(f"hosts文件缺少以下内容: {missing_lines}")
            return False
        else:
            logger.info("hosts文件内容完整")
            return True
    
    def _contrast_process(self) -> None:
        """对比处理过程"""
        try:
            logger.info("对比模块启动")
            
            # 读取hosts文件
            success, hosts_content = self._read_hosts_file()
            if not success:
                logger.error("获取hosts文件读取权限失败")
                return
            
            # 获取配置中的hosts数据
            config_hosts_data = config.get_hosts_data()
            
            # 对比内容
            is_complete = self._check_hosts_content(hosts_content, config_hosts_data)
            
            if not is_complete:
                logger.info("检测到hosts文件内容不完整，启动修复模块")
                if self.repair_callback:
                    self.repair_callback()
            else:
                logger.info("hosts文件内容完整，无需修复")
        
        except Exception as e:
            logger.error(f"对比过程中发生错误: {str(e)}")
        finally:
            logger.info("对比模块关闭")
    
    def start(self) -> None:
        """启动对比模块"""
        if self.contrast_thread and self.contrast_thread.is_alive():
            logger.warning("对比模块已在运行中")
            return
        
        self.contrast_thread = threading.Thread(target=self._contrast_process)
        self.contrast_thread.start()


# 全局对比模块对象
contrast_module = ContrastModule()
