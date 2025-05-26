# -*- coding: utf-8 -*-
"""
配置文件模块
1. 配置文件默认生成在软件运行目录
2. 使用toml做为配置文件
3. 兼容PyInstaller打包
4. 如果不存在则创建默认配置
5. 记录配置hosts数据及软件的设置
"""

import os
import sys
import toml
from typing import Dict, Any, Optional

from . import logger
from .version import APP_NAME


class Config:
    """配置文件类"""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        # 默认配置
        self.default_config = {
            "general": {
                "auto_start": False,
                "run_as_admin": False,
                "delay_time": 3000,  # 默认延迟3000毫秒
                "minimize_to_tray": True
            },
            "hosts": {
                "data": "# Hosts Monitor 数据\n127.0.0.1 localhost\n"
            }
        }
        
        # 获取配置文件路径
        self.config_path = self._get_config_path()
        
        # 加载配置
        self.config = self.load_config()
        
        self._initialized = True
    
    def _get_config_path(self) -> str:
        """获取配置文件路径"""
        # 判断是否是PyInstaller打包的环境
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        config_file = f"{APP_NAME.lower().replace(' ', '_')}.toml"
        return os.path.join(base_path, config_file)
    
    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if os.path.exists(self.config_path):
                logger.info(f"正在从 {self.config_path} 加载配置")
                config = toml.load(self.config_path)
                
                # 保证配置完整性
                for section, items in self.default_config.items():
                    if section not in config:
                        config[section] = items
                    else:
                        for key, value in items.items():
                            if key not in config[section]:
                                config[section][key] = value
                
                return config
            else:
                logger.info(f"未找到配置文件，创建默认配置: {self.config_path}")
                self.save_config(self.default_config)
                return self.default_config
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
            return self.default_config
    
    def save_config(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """保存配置文件"""
        if config is None:
            config = self.config
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                toml.dump(config, f)
            logger.info(f"配置已保存到: {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"保存配置文件失败: {str(e)}")
            return False
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """获取配置项"""
        try:
            return self.config[section][key]
        except KeyError:
            if default is not None:
                return default
            try:
                return self.default_config[section][key]
            except KeyError:
                logger.warning(f"配置项 {section}.{key} 不存在且没有提供默认值")
                return None
    
    def set(self, section: str, key: str, value: Any) -> bool:
        """设置配置项"""
        try:
            if section not in self.config:
                self.config[section] = {}
            
            self.config[section][key] = value
            return True
        except Exception as e:
            logger.error(f"设置配置项失败: {str(e)}")
            return False
    
    def get_hosts_data(self) -> str:
        """获取hosts数据"""
        return self.get("hosts", "data", self.default_config["hosts"]["data"])
    
    def set_hosts_data(self, data: str) -> bool:
        """设置hosts数据"""
        result = self.set("hosts", "data", data)
        if result:
            self.save_config()
        return result


# 全局配置对象
config = Config()
