#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复模块

本模块负责修复系统 Hosts 文件，使其包含配置文件中指定的规则。
使用 pywin32 库以强制共享写访问方式打开 Hosts 文件，避免文件锁或权限问题。
根据规则匹配逻辑和格式规范，将缺失或不正确的规则更新到 Hosts 文件中。

修复逻辑：
1. 按照配置延迟指定时间
2. 获取 Hosts 文件的写入权限
3. 读取当前 Hosts 内容
4. 将配置中启用的规则应用到 Hosts 文件
5. 规范化格式（规则间空行、去除多余空行等）
6. 写入更新后的内容
7. 释放文件写入权限

使用示例:
    from hosts_monitor.repair import repair_hosts
    
    # 修复 Hosts 文件
    success = repair_hosts()
    if success:
        print("Hosts 文件修复成功")
    else:
        print("Hosts 文件修复失败")
"""

import os
import time
import re
from typing import Dict, List, Tuple, Optional, Union, Any

# pywin32 导入
import win32file
import win32con
import pywintypes

# 导入配置和日志模块
try:
    from hosts_monitor.config import get_enabled_rules, get_setting
    from hosts_monitor.logger import logger, auto_log
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
    
    def get_setting(key, default=None):
        if key == "delay_ms":
            return 3000
        return default


# Windows 平台下 Hosts 文件路径
HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"


@auto_log
def open_hosts_for_writing() -> Tuple[Any, bool]:
    """
    以强制共享写访问方式打开 Hosts 文件
    
    返回:
        Tuple[Any, bool]: 文件句柄和是否成功的标志
    """
    try:
        # 尝试以共享模式打开文件
        handle = win32file.CreateFile(
            HOSTS_PATH,
            win32con.GENERIC_READ | win32con.GENERIC_WRITE,  # 读写权限
            win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,  # 共享读写
            None,  # 默认安全属性
            win32con.OPEN_EXISTING,  # 打开已有文件
            win32con.FILE_ATTRIBUTE_NORMAL,  # 普通文件属性
            None  # 无模板文件
        )
        logger.info("成功获取 Hosts 文件写入权限")
        return handle, True
    except pywintypes.error as e:
        error_code = e.args[0]
        error_message = e.args[2]
        
        if error_code == 5:  # 访问被拒绝
            logger.error(f"获取 Hosts 文件写入权限失败: 权限不足。请以管理员身份运行程序。错误详情: {error_message}")
        else:
            logger.error(f"获取 Hosts 文件写入权限失败: 错误码 {error_code}, 错误信息: {error_message}")
        
        return None, False


@auto_log
def read_hosts_content(handle: Any) -> str:
    """
    读取 Hosts 文件内容
    
    参数:
        handle: 文件句柄
        
    返回:
        str: Hosts 文件内容
    """
    try:
        # 将文件指针移到文件开头
        win32file.SetFilePointer(handle, 0, win32file.FILE_BEGIN)
        
        # 读取文件内容
        result, data = win32file.ReadFile(handle, 1024 * 1024)  # 最大读取 1MB，足够 Hosts 文件使用
        
        # 将字节数据转换为字符串
        if isinstance(data, bytes):
            content = data.decode('utf-8', errors='replace')
        else:
            content = str(data)
        
        logger.info(f"成功读取 Hosts 文件内容，共 {len(content)} 字符")
        return content
    except Exception as e:
        logger.error(f"读取 Hosts 文件内容失败: {str(e)}")
        return ""


@auto_log
def write_hosts_content(handle: Any, content: str) -> bool:
    """
    写入内容到 Hosts 文件
    
    参数:
        handle: 文件句柄
        content: 要写入的内容
        
    返回:
        bool: 写入是否成功
    """
    try:
        # 将文件指针移到文件开头
        win32file.SetFilePointer(handle, 0, win32file.FILE_BEGIN)
        
        # 将内容编码为字节并写入文件
        bytes_data = content.encode('utf-8')
        win32file.WriteFile(handle, bytes_data)
        
        # 截断文件，删除可能的残留内容
        win32file.SetEndOfFile(handle)
        
        logger.info(f"成功写入更新后的 Hosts 文件内容，共 {len(content)} 字符")
        return True
    except Exception as e:
        logger.error(f"写入 Hosts 文件内容失败: {str(e)}")
        return False


@auto_log
def find_rule_position(hosts_content: str, rule: Dict[str, Any]) -> Dict[str, Any]:
    """
    在 Hosts 文件中查找规则位置
    
    查找规则注释行或第一个匹配的 IP+域名 条目的位置
    
    参数:
        hosts_content: Hosts 文件内容
        rule: 要查找的规则数据
        
    返回:
        Dict[str, Any]: 包含规则位置信息的字典
    """
    rule_name = rule['name']
    result = {
        'found': False,        # 是否找到规则
        'comment_pos': -1,     # 注释行位置
        'first_entry_pos': -1, # 第一个条目位置
        'match_type': None     # 匹配类型：'comment', 'entry', None
    }
    
    # 查找规则注释行
    comment_pattern = re.compile(rf"^\s*#\s*{re.escape(rule_name)}\s*$", re.MULTILINE)
    comment_match = comment_pattern.search(hosts_content)
    
    if comment_match:
        result['found'] = True
        result['comment_pos'] = comment_match.start()
        result['match_type'] = 'comment'
    
    # 查找规则条目
    for entry in rule.get('entries', []):
        ip = entry['ip']
        domain = entry['domain']
        entry_pattern = re.compile(rf"^\s*{re.escape(ip)}\s+{re.escape(domain)}\s*$", re.MULTILINE)
        entry_match = entry_pattern.search(hosts_content)
        
        if entry_match:
            result['found'] = True
            entry_pos = entry_match.start()
            
            # 如果是第一个找到的条目，或者比之前找到的条目更靠前
            if result['first_entry_pos'] == -1 or entry_pos < result['first_entry_pos']:
                result['first_entry_pos'] = entry_pos
                if result['match_type'] != 'comment':  # 注释匹配优先级高于条目匹配
                    result['match_type'] = 'entry'
    
    # 确定规则起始位置
    if result['comment_pos'] != -1 and result['first_entry_pos'] != -1:
        # 如果注释行和条目都找到，使用较靠前的位置
        result['start_pos'] = min(result['comment_pos'], result['first_entry_pos'])
    elif result['comment_pos'] != -1:
        # 只找到注释行
        result['start_pos'] = result['comment_pos']
    elif result['first_entry_pos'] != -1:
        # 只找到条目
        result['start_pos'] = result['first_entry_pos']
    else:
        # 都没找到
        result['start_pos'] = -1
    
    return result


@auto_log
def find_rule_end(hosts_content: str, start_pos: int) -> int:
    """
    查找规则块的结束位置
    
    规则块结束定义为第一个空行，或者下一个以 # 开头的注释行
    
    参数:
        hosts_content: Hosts 文件内容
        start_pos: 规则开始位置
        
    返回:
        int: 规则结束位置
    """
    if start_pos < 0 or start_pos >= len(hosts_content):
        return len(hosts_content)
    
    # 从规则开始位置向后查找第一个空行或下一条注释
    lines = hosts_content[start_pos:].split('\n')
    
    # 跳过第一行（开始行）
    line_offset = len(lines[0]) + 1  # +1 是换行符
    cumulative_offset = start_pos + line_offset
    
    for i, line in enumerate(lines[1:], 1):  # 从第二行开始
        # 空行或者下一条注释行表示当前规则结束
        if line.strip() == '' or (line.strip().startswith('#') and i > 1):  # 避免将当前规则注释行视为下一条规则开始
            return cumulative_offset
        
        cumulative_offset += len(line) + 1  # +1 是换行符
    
    # 如果没找到结束标志，返回文本末尾
    return len(hosts_content)


@auto_log
def format_rule_content(rule: Dict[str, Any]) -> str:
    """
    格式化规则内容
    
    将规则格式化为适合写入 Hosts 文件的文本
    
    参数:
        rule: 规则数据
        
    返回:
        str: 格式化后的规则文本
    """
    lines = []
    
    # 添加规则注释
    lines.append(f"# {rule['name']}")
    
    # 添加规则条目
    for entry in rule.get('entries', []):
        lines.append(f"{entry['ip']} {entry['domain']}")
    
    # 组合成文本，不添加前后空行（在应用规则时处理空行）
    return '\n'.join(lines)


@auto_log
def apply_rule_to_content(hosts_content: str, rule: Dict[str, Any]) -> str:
    """
    将规则应用到 Hosts 内容
    
    根据规则匹配情况，更新或添加规则到 Hosts 内容
    
    参数:
        hosts_content: Hosts 文件内容
        rule: 要应用的规则
        
    返回:
        str: 更新后的 Hosts 内容
    """
    # 查找规则位置
    position_info = find_rule_position(hosts_content, rule)
    
    # 格式化规则内容
    rule_content = format_rule_content(rule)
    
    if not position_info['found']:
        # 规则不存在，追加到文件末尾
        logger.info(f"规则 '{rule['name']}' 不存在，追加到文件末尾")
        
        # 确保文件末尾有空行
        if hosts_content and not hosts_content.endswith('\n'):
            hosts_content += '\n'
        
        # 如果文件末尾已经有空行，则直接添加规则；否则先添加一个空行
        if hosts_content and hosts_content.endswith('\n\n'):
            hosts_content += rule_content + '\n\n'
        else:
            hosts_content += '\n' + rule_content + '\n\n'
    else:
        # 规则已存在，更新规则内容
        logger.info(f"规则 '{rule['name']}' 已存在，更新规则内容")
        
        # 查找规则块结束位置
        end_pos = find_rule_end(hosts_content, position_info['start_pos'])
        
        # 提取规则块之前的内容
        before_rule = hosts_content[:position_info['start_pos']]
        
        # 提取规则块之后的内容，并去除规则块之后内容中的重复项
        after_rule = hosts_content[end_pos:]
        
        # 去除重复：先查找 after_rule 中有没有相同的注释行或同样的 IP+域名 映射
        # 如果有，将它们从 after_rule 中移除
        if position_info['match_type'] == 'comment':
            # 移除重复的注释行
            after_rule = re.sub(rf"^\s*#\s*{re.escape(rule['name'])}\s*$", "", after_rule, flags=re.MULTILINE)
        
        # 移除重复的条目
        for entry in rule.get('entries', []):
            ip = entry['ip']
            domain = entry['domain']
            after_rule = re.sub(rf"^\s*{re.escape(ip)}\s+{re.escape(domain)}\s*$", "", after_rule, flags=re.MULTILINE)
        
        # 确保规则前有空行（如果不是文件开头）
        if before_rule and not before_rule.endswith('\n\n'):
            if before_rule.endswith('\n'):
                before_rule += '\n'
            else:
                before_rule += '\n\n'
        
        # 拼接内容
        hosts_content = before_rule + rule_content + '\n' + after_rule
    
    return hosts_content


@auto_log
def normalize_hosts_format(hosts_content: str) -> str:
    """
    规范化 Hosts 文件格式
    
    处理连续空行，确保格式符合要求
    
    参数:
        hosts_content: Hosts 文件内容
        
    返回:
        str: 规范化后的内容
    """
    # 替换连续的多个空行为单个空行
    hosts_content = re.sub(r'\n{3,}', '\n\n', hosts_content)
    
    # 确保文件末尾最多有一个空行
    hosts_content = re.sub(r'\n+$', '\n', hosts_content)
    
    return hosts_content


@auto_log
def repair_hosts() -> bool:
    """
    修复 Hosts 文件的主函数
    
    按照流程：延迟 -> 获取权限 -> 修复逻辑 -> 释放权限
    
    返回:
        bool: 修复是否成功
    """
    # 获取延迟时间设置
    delay_ms = get_setting('delay_ms', 3000)  # 默认延迟 3 秒
    logger.info(f"开始修复 Hosts 文件，等待延迟 {delay_ms} 毫秒...")
    
    # 等待指定延迟时间
    time.sleep(delay_ms / 1000.0)
    
    # 尝试获取文件写入权限
    handle, success = open_hosts_for_writing()
    
    if not success:
        logger.error("无法获取 Hosts 文件写入权限，修复终止")
        return False
    
    try:
        # 读取当前 Hosts 文件内容
        hosts_content = read_hosts_content(handle)
        if not hosts_content:
            logger.error("读取 Hosts 文件内容失败，修复终止")
            return False
        
        # 保存原始内容用于比较
        original_content = hosts_content
        
        # 获取启用的规则
        enabled_rules = get_enabled_rules()
        logger.info(f"获取到 {len(enabled_rules)} 条启用的规则")
        
        # 将每条启用的规则应用到 Hosts 内容
        for rule in enabled_rules:
            hosts_content = apply_rule_to_content(hosts_content, rule)
        
        # 规范化 Hosts 文件格式
        hosts_content = normalize_hosts_format(hosts_content)
        
        # 检查内容是否发生变化
        if hosts_content == original_content:
            logger.info("Hosts 文件内容无需修改")
            return True
        
        # 写入更新后的内容
        if write_hosts_content(handle, hosts_content):
            logger.info("Hosts 文件修复完成")
            return True
        else:
            logger.error("写入 Hosts 文件失败，修复失败")
            return False
        
    except Exception as e:
        logger.error(f"修复 Hosts 文件时发生异常: {str(e)}")
        return False
    finally:
        # 无论成功还是失败，都释放文件句柄
        try:
            if handle:
                win32file.CloseHandle(handle)
                logger.info("释放 Hosts 文件句柄")
        except Exception as e:
            logger.error(f"释放 Hosts 文件句柄时发生异常: {str(e)}")


# 当脚本直接运行时，执行测试修复
if __name__ == "__main__":
    # 简单的测试规则
    from hosts_monitor.config import add_rule, update_setting
    
    # 添加测试规则
    add_rule('Test Rule', [
        {'ip': '127.0.0.1', 'domain': 'test1.example.com'},
        {'ip': '127.0.0.1', 'domain': 'test2.example.com'}
    ])
    
    # 设置延迟为 1 秒
    update_setting('delay_ms', 1000)
    
    # 执行修复
    success = repair_hosts()
    print(f"修复结果: {'成功' if success else '失败'}")
