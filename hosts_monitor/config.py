#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置文件模块

本模块负责管理应用程序的配置，使用 TOML 格式存储配置数据。
主要功能包括：
1. 加载/创建配置文件
2. 提供对规则数据和设置的读取接口
3. 提供更新配置和保存到磁盘的功能

配置文件默认保存在软件运行目录下，支持 PyInstaller 打包场景。
如果配置文件不存在，则创建包含默认配置的文件。

使用示例:
    # 读取配置
    from hosts_monitor.config import get_enabled_rules, get_setting
    
    rules = get_enabled_rules()  # 获取启用的规则列表
    delay = get_setting('delay_ms')  # 获取延迟设置
    
    # 修改配置
    from hosts_monitor.config import add_rule, update_setting
    
    add_rule('Block Ads', [
        {'ip': '127.0.0.1', 'domain': 'ads.example.com'},
        {'ip': '127.0.0.1', 'domain': 'banner.example.org'}
    ])
    update_setting('delay_ms', 5000)  # 更新延迟为 5 秒
"""

import os
import sys
import threading
import toml
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import datetime

# 导入日志模块
try:
    from hosts_monitor.logger import logger, auto_log
except ImportError:
    # 如果日志模块尚未可用，提供简单的日志记录
    import logging
    logger = logging.getLogger(__name__)
    logger.addHandler(logging.NullHandler())
    
    def auto_log(func):
        # 简单版本的装饰器，当主日志模块不可用时使用
        return func


# 全局变量
CONFIG_DATA = {}  # 用于存储配置数据的字典
CONFIG_LOCK = threading.Lock()  # 线程锁，用于保护配置读写操作


def get_config_path() -> str:
    """
    获取配置文件的路径
    
    根据程序运行环境确定配置文件应该存放的位置。
    如果是 PyInstaller 打包的程序，使用可执行文件所在目录。
    否则使用当前工作目录。
    
    返回:
        str: 配置文件的完整路径
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包的环境
        base_dir = os.path.dirname(sys.executable)
    else:
        # 开发环境 - 使用项目根目录
        # 如果已经在main.py中设置了工作目录，这里会获取到设置后的路径
        # 否则，我们计算项目根目录（假设config.py在hosts_monitor包内）
        base_dir = os.getcwd()
        module_dir = os.path.dirname(os.path.abspath(__file__))
        if os.path.basename(module_dir) == 'hosts_monitor':
            # 如果当前工作目录不是项目根目录，则重新计算
            if os.path.basename(base_dir) == 'hosts_monitor':
                base_dir = os.path.dirname(module_dir)
    
    return os.path.join(base_dir, 'config.toml')


def create_default_config() -> Dict[str, Any]:
    """
    创建默认配置数据
    
    当配置文件不存在时，提供默认的配置内容。
    
    返回:
        Dict[str, Any]: 包含默认配置项的字典
    """
    # 默认配置数据
    default_config = {
        'settings': {
            'auto_start': False,       # 开机自启动，默认关闭
            'run_as_admin': False,     # 管理员运行，默认关闭
            'delay_ms': 3000,          # 修复延迟时间，默认 3 秒
            'create_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        'rules': []                    # 规则列表，默认为空
    }
    # 如果需要，可以在这里添加其他默认设置
    # 例如:
    # - 日志级别
    # - 代理设置
    return default_config


@auto_log
def load_config() -> Dict[str, Any]:
    """
    加载配置文件
    
    读取配置文件并解析为字典。如果文件不存在，则创建默认配置。
    
    返回:
        Dict[str, Any]: 配置数据字典
    """
    global CONFIG_DATA
    
    config_path = get_config_path()
    logger.info(f"尝试从 {config_path} 加载配置文件")
    
    try:
        if os.path.exists(config_path):
            # 配置文件存在，直接加载
            CONFIG_DATA = toml.load(config_path)
            logger.info("配置文件加载成功")
        else:
            # 配置文件不存在，创建默认配置
            CONFIG_DATA = create_default_config()
            save_config()  # 将默认配置保存到文件
            logger.info("已创建并加载默认配置")
            
        return CONFIG_DATA
        
    except Exception as e:
        logger.error(f"加载配置文件失败: {str(e)}")
        # 出错时使用默认配置
        CONFIG_DATA = create_default_config()
        return CONFIG_DATA


@auto_log
def save_config() -> bool:
    """
    保存配置到文件
    
    将当前内存中的配置数据写入 TOML 文件。
    
    返回:
        bool: 保存成功返回 True，否则返回 False
    """
    config_path = get_config_path()
    
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        # 写入文件
        with open(config_path, 'w', encoding='utf-8') as f:
            toml.dump(CONFIG_DATA, f)
        
        logger.info(f"配置已保存到 {config_path}")
        return True
        
    except Exception as e:
        logger.error(f"保存配置失败: {str(e)}")
        return False


# ===== 规则相关接口 =====

@auto_log
def get_all_rules() -> List[Dict[str, Any]]:
    """
    获取所有规则（与get_rules函数相同，提供额外的命名以保持一致性）
    
    返回:
        List[Dict[str, Any]]: 包含所有规则数据的列表
    """
    return get_rules()

@auto_log
def get_rules() -> List[Dict[str, Any]]:
    """
    获取所有规则
    
    返回:
        List[Dict[str, Any]]: 包含所有规则数据的列表
    """
    with CONFIG_LOCK:
        return CONFIG_DATA.get('rules', [])


@auto_log
def get_enabled_rules() -> List[Dict[str, Any]]:
    """
    获取所有启用的规则
    
    返回:
        List[Dict[str, Any]]: 包含所有已启用规则数据的列表
    """
    with CONFIG_LOCK:
        rules = CONFIG_DATA.get('rules', [])
        return [rule for rule in rules if rule.get('enabled', False)]


@auto_log
def get_rule(name: str) -> Optional[Dict[str, Any]]:
    """
    根据名称获取指定规则
    
    参数:
        name: 要获取的规则名称
        
    返回:
        Optional[Dict[str, Any]]: 找到的规则数据，如果不存在则返回 None
    """
    with CONFIG_LOCK:
        for rule in CONFIG_DATA.get('rules', []):
            if rule.get('name') == name:
                return rule
        return None


@auto_log
def add_rule(name: str, entries: List[Dict[str, str]], enabled: bool = True) -> bool:
    """
    添加新规则
    
    参数:
        name: 规则名称
        entries: 规则项列表，每项包含 'ip' 和 'domain' 两个键
        enabled: 规则是否启用，默认为 True
        
    返回:
        bool: 添加成功返回 True，失败返回 False
    """
    with CONFIG_LOCK:
        # 检查规则名称是否已存在
        for rule in CONFIG_DATA.get('rules', []):
            if rule.get('name') == name:
                logger.warning(f"规则 '{name}' 已存在，添加失败")
                return False
        
        # 添加新规则
        new_rule = {
            'name': name,
            'enabled': enabled,
            'entries': entries
        }
        
        if 'rules' not in CONFIG_DATA:
            CONFIG_DATA['rules'] = []
        
        CONFIG_DATA['rules'].append(new_rule)
        
        # 保存配置
        result = save_config()
        if result:
            logger.info(f"已添加新规则: {name}")
        
        return result


@auto_log
def remove_rule(name: str) -> bool:
    """
    删除指定规则
    
    参数:
        name: 要删除的规则名称
        
    返回:
        bool: 删除成功返回 True，失败返回 False
    """
    with CONFIG_LOCK:
        rules = CONFIG_DATA.get('rules', [])
        
        # 查找并删除规则
        for i, rule in enumerate(rules):
            if rule.get('name') == name:
                del rules[i]
                
                # 保存配置
                result = save_config()
                if result:
                    logger.info(f"已删除规则: {name}")
                
                return result
        
        logger.warning(f"规则 '{name}' 不存在，删除失败")
        return False


@auto_log
def update_rule(name: str, new_data: Dict[str, Any]) -> bool:
    """
    更新指定规则
    
    参数:
        name: 要更新的规则名称
        new_data: 包含新数据的字典，可以包含 'name'、'enabled' 和 'entries' 键
        
    返回:
        bool: 更新成功返回 True，失败返回 False
    """
    with CONFIG_LOCK:
        # 查找规则
        rule = get_rule(name)
        if not rule:
            logger.warning(f"规则 '{name}' 不存在，更新失败")
            return False
        
        # 更新规则数据
        if 'name' in new_data and new_data['name'] != name:
            # 检查新名称是否与其他规则冲突
            if get_rule(new_data['name']):
                logger.warning(f"规则名称 '{new_data['name']}' 已存在，更新失败")
                return False
            rule['name'] = new_data['name']
        
        if 'enabled' in new_data:
            rule['enabled'] = bool(new_data['enabled'])
        
        if 'entries' in new_data:
            rule['entries'] = new_data['entries']
        
        # 保存配置
        result = save_config()
        if result:
            logger.info(f"已更新规则: {name}")
        
        return result


@auto_log
def enable_rule(name: str, enabled: bool = True) -> bool:
    """
    启用或禁用指定规则
    
    参数:
        name: 规则名称
        enabled: True 表示启用，False 表示禁用
        
    返回:
        bool: 操作成功返回 True，失败返回 False
    """
    return update_rule(name, {'enabled': enabled})


# ===== 设置相关接口 =====

@auto_log
def get_setting(key: str, default: Any = None) -> Any:
    """
    获取指定设置项的值
    
    参数:
        key: 设置项的键名
        default: 默认值，如果设置项不存在则返回该值
        
    返回:
        Any: 设置项的值
    """
    with CONFIG_LOCK:
        settings = CONFIG_DATA.get('settings', {})
        return settings.get(key, default)


@auto_log
def update_setting(key: str, value: Any) -> bool:
    """
    更新指定设置项
    
    参数:
        key: 设置项的键名
        value: 新的值
        
    返回:
        bool: 更新成功返回 True，失败返回 False
    """
    with CONFIG_LOCK:
        if 'settings' not in CONFIG_DATA:
            CONFIG_DATA['settings'] = {}
        
        CONFIG_DATA['settings'][key] = value
        
        # 保存配置
        result = save_config()
        if result:
            logger.info(f"已更新设置 {key} = {value}")
        
        return result


@auto_log
def get_all_settings() -> Dict[str, Any]:
    """
    获取所有设置项
    
    返回:
        Dict[str, Any]: 包含所有设置项的字典
    """
    with CONFIG_LOCK:
        return CONFIG_DATA.get('settings', {})


@auto_log
def get_default_settings() -> Dict[str, Any]:
    """
    获取默认设置项
    
    返回:
        Dict[str, Any]: 包含默认设置项的字典
    """
    # 从默认配置中获取设置部分
    default_config = create_default_config()
    return default_config.get('settings', {})


# 初始化配置
# 在模块导入时加载配置文件
try:
    load_config()
except Exception as e:
    logger.error(f"配置模块初始化失败: {str(e)}")


# 如果直接运行此脚本，则输出当前配置
if __name__ == "__main__":
    import json
    print("当前配置:")
    print(json.dumps(CONFIG_DATA, indent=4, ensure_ascii=False))
    
    print("\n所有规则:")
    for rule in get_rules():
        status = "启用" if rule.get('enabled') else "禁用"
        print(f"- {rule['name']} ({status}): {len(rule.get('entries', []))} 项")
    
    print("\n已启用的规则:")
    for rule in get_enabled_rules():
        print(f"- {rule['name']}: {len(rule.get('entries', []))} 项")
    
    print("\n设置项:")
    for key, value in get_all_settings().items():
        print(f"- {key} = {value}")
