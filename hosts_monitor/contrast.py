#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
对比模块

本模块负责检查系统 Hosts 文件内容是否与配置中启用的规则一致。
主要功能包括:
1. 读取当前 Hosts 文件内容
2. 获取配置中启用的规则列表
3. 比较 Hosts 文件是否包含所有启用规则的内容
4. 根据对比结果决定是否触发修复模块进行更新

对比模块不直接修改 Hosts 文件，而是在发现不一致时调用修复模块来完成更新。

使用示例:
    from hosts_monitor.contrast import check_hosts
    
    # 执行对比检查
    result = check_hosts()
    if result:
        print("Hosts 文件内容完整，无需修复")
    else:
        print("Hosts 文件内容不完整或已触发修复")
"""

import os
import re
from typing import Dict, List, Tuple, Optional, Union, Any, Set

# 导入配置、日志和修复模块
try:
    from hosts_monitor.config import get_enabled_rules
    from hosts_monitor.logger import logger, auto_log
    # 修复模块按需导入，避免循环依赖
except ImportError:
    # 简单的替代日志功能，用于模块单独测试
    import logging
    logger = logging.getLogger(__name__)
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)
    
    def auto_log(func):
        return func
    
    # 简单的替代配置功能，用于模块单独测试
    def get_enabled_rules():
        return []

# Windows 平台下 Hosts 文件路径
HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"


@auto_log
def read_hosts_file() -> Tuple[str, bool]:
    """
    读取 Hosts 文件内容
    
    返回:
        Tuple[str, bool]: Hosts 文件内容和是否成功的标志
    """
    try:
        logger.info("尝试读取 Hosts 文件内容")
        
        # 以只读模式打开 Hosts 文件
        with open(HOSTS_PATH, 'r', encoding='utf-8') as file:
            content = file.read()
        
        logger.info(f"成功读取 Hosts 文件，共 {len(content)} 字符")
        return content, True
    
    except PermissionError:
        logger.error("获取 Hosts 文件读取权限失败：权限不足。请以管理员身份运行程序")
        return "", False
    except FileNotFoundError:
        logger.error(f"Hosts 文件不存在：{HOSTS_PATH}")
        return "", False
    except UnicodeDecodeError:
        # 如果 UTF-8 编码失败，尝试使用系统默认编码
        try:
            with open(HOSTS_PATH, 'r') as file:
                content = file.read()
            logger.info(f"使用系统默认编码成功读取 Hosts 文件，共 {len(content)} 字符")
            return content, True
        except Exception as e:
            logger.error(f"读取 Hosts 文件失败（编码错误）：{str(e)}")
            return "", False
    except Exception as e:
        logger.error(f"读取 Hosts 文件失败：{str(e)}")
        return "", False


@auto_log
def check_rule_in_hosts(hosts_content: str, rule: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    检查规则是否在 Hosts 文件中存在且完整
    
    参数:
        hosts_content: Hosts 文件内容
        rule: 要检查的规则数据
        
    返回:
        Tuple[bool, List[str]]: 规则是否完整及缺失项列表
    """
    rule_name = rule['name']
    missing_items = []
    
    # 检查规则注释是否存在
    comment = f"# {rule_name}"
    if comment not in hosts_content:
        missing_items.append(f"注释行 '{comment}'")
    
    # 检查规则条目是否存在
    for entry in rule.get('entries', []):
        ip = entry['ip']
        domain = entry['domain']
        
        # 创建一个正则表达式模式，匹配IP和域名（忽略前后空白和中间空白数量）
        pattern = re.compile(rf"^\s*{re.escape(ip)}\s+{re.escape(domain)}\s*$", re.MULTILINE)
        
        if not pattern.search(hosts_content):
            missing_items.append(f"映射条目 '{ip} {domain}'")
    
    # 如果没有缺失项，则规则完整
    return len(missing_items) == 0, missing_items


@auto_log
def check_hosts() -> bool:
    """
    检查 Hosts 文件内容是否与配置中的启用规则一致
    
    如果发现内容不一致，会触发修复模块进行更新
    
    返回:
        bool: True 表示内容完整无需修复，False 表示内容不完整或已触发修复
    """
    # 读取 Hosts 文件内容
    hosts_content, success = read_hosts_file()
    if not success:
        logger.error("无法读取 Hosts 文件，对比终止")
        return False
    
    # 获取启用的规则列表
    enabled_rules = get_enabled_rules()
    logger.info(f"获取到 {len(enabled_rules)} 条启用的规则")
    
    if not enabled_rules:
        logger.info("当前没有启用的规则，无需对比")
        return True
    
    # 检查每条启用规则是否在 Hosts 文件中存在且完整
    missing_rules = []
    incomplete_rules = []
    
    for rule in enabled_rules:
        is_complete, missing_items = check_rule_in_hosts(hosts_content, rule)
        
        if not is_complete:
            incomplete_rules.append(rule['name'])
            missing_rules.append({
                'name': rule['name'],
                'missing': missing_items
            })
    
    # 根据对比结果决定是否触发修复
    if missing_rules:
        # 记录不完整的规则信息
        logger.info(f"对比结果: Hosts 文件内容不完整，有 {len(incomplete_rules)} 条规则需要修复")
        for mr in missing_rules:
            logger.info(f"规则 '{mr['name']}' 缺失项: {', '.join(mr['missing'])}")
        
        # 调用修复模块
        logger.info("检测到 Hosts 内容不完整，正在启动修复模块...")
        
        # 延迟导入修复模块，避免循环依赖
        try:
            from hosts_monitor.repair import repair_hosts
            repair_result = repair_hosts()
            
            if repair_result:
                logger.info("修复模块执行成功")
            else:
                logger.error("修复模块执行失败")
            
            # 无论修复结果如何，都返回 False 表示本次对比发现了不一致
            return False
        except ImportError as e:
            logger.error(f"导入修复模块失败: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"调用修复模块时发生异常: {str(e)}")
            return False
    else:
        logger.info("对比结果: Hosts 文件内容完整，无需修复")
        return True


@auto_log
def check_for_excessive_entries(hosts_content: str) -> Tuple[bool, List[str]]:
    """
    检查 Hosts 文件中是否存在多余的条目（未在启用规则中的映射）
    
    参数:
        hosts_content: Hosts 文件内容
        
    返回:
        Tuple[bool, List[str]]: 是否存在多余条目及多余条目列表
    """
    # 获取启用的规则中所有合法的映射
    enabled_rules = get_enabled_rules()
    valid_mappings = set()
    
    for rule in enabled_rules:
        for entry in rule.get('entries', []):
            valid_mappings.add(f"{entry['ip']} {entry['domain']}")
    
    # 从 Hosts 文件中提取所有非注释的映射行
    pattern = re.compile(r'^\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+([^\s#]+).*$', re.MULTILINE)
    actual_mappings = pattern.findall(hosts_content)
    
    # 检查每个实际映射是否在有效映射列表中
    excessive_entries = []
    for ip, domain in actual_mappings:
        mapping = f"{ip} {domain}"
        if mapping not in valid_mappings and not domain.lower() in ['localhost', 'localhost.localdomain', 'broadcasthost']:
            # 排除系统默认的 localhost 等映射
            excessive_entries.append(mapping)
    
    return len(excessive_entries) > 0, excessive_entries


@auto_log
def detailed_comparison() -> Dict[str, Any]:
    """
    执行详细的 Hosts 文件与配置规则的比较，返回完整对比报告
    
    返回:
        Dict[str, Any]: 包含完整对比信息的字典
    """
    # 读取 Hosts 文件内容
    hosts_content, success = read_hosts_file()
    if not success:
        return {
            'success': False,
            'error': '无法读取 Hosts 文件',
            'needs_repair': False
        }
    
    # 获取启用的规则列表
    enabled_rules = get_enabled_rules()
    
    # 对比结果
    comparison_result = {
        'success': True,
        'enabled_rules_count': len(enabled_rules),
        'missing_rules': [],
        'incomplete_rules': [],
        'excessive_entries': [],
        'needs_repair': False
    }
    
    # 检查每条启用规则
    for rule in enabled_rules:
        is_complete, missing_items = check_rule_in_hosts(hosts_content, rule)
        
        if not is_complete:
            comparison_result['incomplete_rules'].append(rule['name'])
            comparison_result['missing_rules'].append({
                'name': rule['name'],
                'missing': missing_items
            })
    
    # 检查多余条目
    has_excessive, excessive_entries = check_for_excessive_entries(hosts_content)
    if has_excessive:
        comparison_result['excessive_entries'] = excessive_entries
    
    # 确定是否需要修复
    comparison_result['needs_repair'] = (
        len(comparison_result['missing_rules']) > 0 or 
        len(comparison_result['excessive_entries']) > 0
    )
    
    return comparison_result


# 当脚本直接运行时的测试
if __name__ == "__main__":
    # 执行对比检查
    result = check_hosts()
    print(f"对比结果: {'内容完整，无需修复' if result else '内容不完整或已触发修复'}")
    
    # 执行详细对比并打印报告
    detailed_result = detailed_comparison()
    print("\n详细对比报告:")
    for key, value in detailed_result.items():
        print(f"{key}: {value}")
