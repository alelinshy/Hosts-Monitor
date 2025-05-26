# -*- coding: utf-8 -*-
"""
修复模块
- 使用pywin32强制共享写访问
- 按修复逻辑修复hosts文件
"""

import os
import threading
import time
import win32file
import win32con
import ctypes
from typing import List, Tuple, Optional

from . import logger
from .config import config
from .monitor import monitor


class RepairModule:
    """修复模块类"""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(RepairModule, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 工作线程
        self.repair_thread = None
        
        # 文件句柄
        self.file_handle = None
        
        self._initialized = True
    
    def _get_write_access(self, path: str) -> Tuple[bool, Optional[int]]:
        """获取文件写入权限"""
        try:
            handle = win32file.CreateFile(
                path,
                win32con.GENERIC_READ | win32con.GENERIC_WRITE,
                win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
                None,
                win32con.OPEN_EXISTING,
                win32con.FILE_ATTRIBUTE_NORMAL,
                None
            )
            
            if handle == win32file.INVALID_HANDLE_VALUE:
                logger.error("无法获取hosts文件写入权限")
                return False, None
            
            logger.info("成功获取hosts文件写入权限")
            return True, handle
        except Exception as e:
            logger.error(f"获取写入权限时发生错误: {str(e)}")
            return False, None
    
    def _release_write_access(self, handle: int) -> None:
        """释放文件写入权限"""
        try:
            if handle:
                win32file.CloseHandle(handle)
                logger.info("已释放hosts文件写入权限")
        except Exception as e:
            logger.error(f"释放写入权限时发生错误: {str(e)}")
    
    def _read_file_content(self, handle: int) -> Tuple[bool, str]:
        """读取文件内容"""
        try:
            # 将文件指针移动到文件开头
            win32file.SetFilePointer(handle, 0, win32file.FILE_BEGIN)
            
            # 读取文件内容
            _, content = win32file.ReadFile(handle, 1024 * 1024)  # 最大读取1MB
            
            # 解码内容
            text = content.decode('utf-8')
            return True, text
        except Exception as e:
            logger.error(f"读取文件内容时发生错误: {str(e)}")
            return False, ""
    
    def _write_file_content(self, handle: int, content: str) -> bool:
        """写入文件内容"""
        try:
            # 将文件指针移动到文件开头
            win32file.SetFilePointer(handle, 0, win32file.FILE_BEGIN)
            
            # 截断文件
            win32file.SetEndOfFile(handle)
            
            # 写入新内容
            win32file.WriteFile(handle, content.encode('utf-8'))
            
            # 刷新缓冲区
            win32file.FlushFileBuffers(handle)
            
            logger.info("成功写入新的hosts文件内容")
            return True
        except Exception as e:
            logger.error(f"写入文件内容时发生错误: {str(e)}")
            return False
    
    def _find_match_positions(self, hosts_lines: List[str], config_lines: List[str]) -> List[int]:
        """查找匹配位置"""
        match_positions = []
        is_hosts_monitor_data = False
        
        for config_line in config_lines:
            config_line = config_line.strip()
            if not config_line:
                continue
                
            # 特殊处理"# Hosts Monitor 数据"等注释行
            if "# Hosts Monitor 数据" in config_line:
                is_hosts_monitor_data = True
                
            # 对于普通注释行，如果不是特定的"# Hosts Monitor 数据"部分，则跳过
            if config_line.startswith('#') and not is_hosts_monitor_data and "# Hosts Monitor 数据" not in config_line:
                continue
                
            for i, hosts_line in enumerate(hosts_lines):
                hosts_line = hosts_line.strip()
                if hosts_line == config_line:
                    match_positions.append(i)
        
        return match_positions
    
    def _repair_hosts_file(self, handle: int) -> bool:
        """修复hosts文件"""
        # 读取文件内容
        success, hosts_content = self._read_file_content(handle)
        if not success:
            return False
        
        # 获取配置中的hosts数据
        config_hosts_data = config.get_hosts_data()
        
        # 分割为行
        hosts_lines = hosts_content.splitlines()
        config_lines = config_hosts_data.splitlines()
        
        # 移除配置数据中的前后空行，稍后会规范化添加
        while config_lines and not config_lines[0].strip():
            config_lines.pop(0)
        while config_lines and not config_lines[-1].strip():
            config_lines.pop()
            
        # 查找匹配位置（包含"# Hosts Monitor 数据"等特定注释行）
        match_positions = self._find_match_positions(hosts_lines, config_lines)
        
        # 按照修复逻辑处理
        if not match_positions:
            # 情况1: 没有匹配项，在末尾添加
            logger.info("本地hosts文件中没有匹配的数据，将在末尾添加")
            
            # 移除末尾的所有空行，然后添加一个空行
            while hosts_lines and not hosts_lines[-1].strip():
                hosts_lines.pop()
                
            # 确保文件有内容后添加一个空行
            if hosts_lines:
                hosts_lines.append("")
            
            # 添加配置数据
            hosts_lines.extend(config_lines)
            
            # 在配置数据后添加一个空行
            hosts_lines.append("")
            
        elif len(match_positions) == 1:
            # 情况2: 只有一行匹配，以此为基准点插入
            position = match_positions[0]
            logger.info(f"本地hosts文件中有一行匹配的数据，在位置 {position} 处插入")
            
            # 检查是否是"# Hosts Monitor 数据"标记行的匹配
            is_comment_match = hosts_lines[position].strip().startswith('#')
            
            # 如果是注释行匹配，查找此注释行后的所有连续数据行并删除
            if is_comment_match:
                # 先删除匹配的注释行
                del hosts_lines[position]
                
                # 删除匹配行后的连续非空行，直到遇到空行或注释行为止
                while (position < len(hosts_lines) and 
                      hosts_lines[position].strip() and 
                      not hosts_lines[position].strip().startswith('#')):
                    del hosts_lines[position]
                    
                # 删除可能存在的多余空行
                while position < len(hosts_lines) and not hosts_lines[position].strip():
                    del hosts_lines[position]
            else:
                # 不是注释行匹配，按原有逻辑处理
                del hosts_lines[position]
                
                # 删除可能存在的多余空行
                if position < len(hosts_lines) and not hosts_lines[position].strip():
                    del hosts_lines[position]
            
            # 在匹配位置前确保有一个空行（不多不少）
            if position > 0:
                # 检查前面是否已有空行
                if hosts_lines[position-1].strip():
                    # 如果前面不是空行，添加一个空行
                    hosts_lines.insert(position, "")
                    position += 1
            else:
                # 在文件开头，直接添加一个空行
                hosts_lines.insert(0, "")
                position += 1
                
            # 插入配置数据
            for i, line in enumerate(config_lines):
                hosts_lines.insert(position + i, line)
                
            # 在配置数据后确保有一个空行（不多不少）
            new_position = position + len(config_lines)
            if new_position < len(hosts_lines):
                # 检查后面是否已有空行
                if hosts_lines[new_position].strip():
                    # 如果后面不是空行，添加一个空行
                    hosts_lines.insert(new_position, "")
            else:
                # 已到文件末尾，添加一个空行
                hosts_lines.append("")
                
        else:
            # 情况3: 有多行匹配，以第一行为基准，删除其余匹配行
            first_match = match_positions[0]
            logger.info(f"本地hosts文件中有多行匹配的数据，以位置 {first_match} 为基准")
            
            # 删除第一个匹配之后的所有匹配行
            # 从后向前删除，避免索引问题
            for pos in reversed(match_positions[1:]):
                del hosts_lines[pos]
            
            # 检查第一个匹配是否是"# Hosts Monitor 数据"标记行
            is_comment_match = hosts_lines[first_match].strip().startswith('#')
            
            # 如果是注释行匹配，查找此注释行后的所有连续数据行并删除
            if is_comment_match:
                # 先删除匹配的注释行
                del hosts_lines[first_match]
                
                # 删除匹配行后的连续非空行，直到遇到空行或注释行为止
                while (first_match < len(hosts_lines) and 
                      hosts_lines[first_match].strip() and 
                      not hosts_lines[first_match].strip().startswith('#')):
                    del hosts_lines[first_match]
                    
                # 删除可能存在的多余空行
                while first_match < len(hosts_lines) and not hosts_lines[first_match].strip():
                    del hosts_lines[first_match]
            else:
                # 不是注释行匹配，按原有逻辑处理
                del hosts_lines[first_match]
                
                # 删除可能存在的多余空行
                if first_match < len(hosts_lines) and not hosts_lines[first_match].strip():
                    del hosts_lines[first_match]
            
            # 在匹配位置前确保有一个空行（不多不少）
            if first_match > 0:
                # 检查前面是否已有空行
                if hosts_lines[first_match-1].strip():
                    # 如果前面不是空行，添加一个空行
                    hosts_lines.insert(first_match, "")
                    first_match += 1
            else:
                # 在文件开头，直接添加一个空行
                hosts_lines.insert(0, "")
                first_match += 1
                
            # 插入配置数据
            for i, line in enumerate(config_lines):
                hosts_lines.insert(first_match + i, line)
                
            # 在配置数据后确保有一个空行（不多不少）
            new_position = first_match + len(config_lines)
            if new_position < len(hosts_lines):
                # 检查后面是否已有空行
                if hosts_lines[new_position].strip():
                    # 如果后面不是空行，添加一个空行
                    hosts_lines.insert(new_position, "")
            else:
                # 已到文件末尾，添加一个空行
                hosts_lines.append("")
        
        # 处理文件末尾：
        # 1. 移除所有末尾空行
        while hosts_lines and not hosts_lines[-1].strip():
            hosts_lines.pop()
        
        # 2. 确保文件最后有且仅有一个换行符
        hosts_lines.append("")
        
        # 将行组合成文本
        new_content = "\n".join(hosts_lines)
        
        # 写入文件
        return self._write_file_content(handle, new_content)
    
    def _repair_process(self) -> None:
        """修复处理过程"""
        try:
            logger.info("修复模块启动")
            
            # 首先检查软件是否以管理员权限运行
            if not self._is_admin():
                logger.error("当前程序没有管理员权限，无法修复hosts文件，修复模块关闭")
                return
            
            logger.info("已验证管理员权限，继续修复流程")
            
            # 获取延迟时间（毫秒）并转换为秒
            delay_time_ms = config.get("general", "delay_time", 3000)
            delay_time_sec = delay_time_ms / 1000.0
            
            # 等待延迟时间
            logger.info(f"等待延迟时间: {delay_time_ms}毫秒 ({delay_time_sec:.2f}秒)")
            time.sleep(delay_time_sec)
            
            # 获取hosts文件路径
            hosts_path = monitor.get_hosts_path()
            
            # 获取文件写入权限
            success, handle = self._get_write_access(hosts_path)
            if not success:
                logger.error("无法获取hosts文件写入权限，修复失败")
                return
            
            try:
                # 修复hosts文件
                if self._repair_hosts_file(handle):
                    logger.info("hosts文件修复成功")
                else:
                    logger.error("hosts文件修复失败")
            finally:
                # 释放文件写入权限
                self._release_write_access(handle)
        
        except Exception as e:
            logger.error(f"修复过程中发生错误: {str(e)}")
        finally:
            logger.info("修复模块关闭")
    
    def _is_admin(self) -> bool:
        """检查是否以管理员权限运行"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception as e:
            logger.error(f"检查管理员权限时出错: {str(e)}")
            return False
                
    def start(self) -> None:
        """启动修复模块"""
        if self.repair_thread and self.repair_thread.is_alive():
            logger.warning("修复模块已在运行中")
            return
        
        self.repair_thread = threading.Thread(target=self._repair_process)
        self.repair_thread.start()


# 全局修复模块对象
repair_module = RepairModule()
