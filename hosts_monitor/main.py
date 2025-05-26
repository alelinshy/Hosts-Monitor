# -*- coding: utf-8 -*-
"""
主程序入口
"""

import os
import sys
import ctypes
import subprocess
from PyQt6.QtWidgets import QApplication

from . import logger
from .version import APP_NAME, VERSION
from .config import config
from .controller import controller

# 任务计划名称常量
TASK_NAME = f"{APP_NAME.replace(' ', '_')}_AdminTask"


def check_single_instance() -> bool:
    """检查程序是否已经运行，确保只有一个实例"""
    import socket
    
    # 使用socket锁定一个端口来实现单例
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # 尝试绑定一个本地端口，如果绑定失败，说明已经有一个实例在运行
        sock.bind(("127.0.0.1", 47652))  # 选择一个不常用的端口
        # 保持socket连接
        return True
    except socket.error:
        return False


def check_task_exists() -> bool:
    """检查管理员权限任务计划是否存在"""
    try:
        # 使用schtasks命令查询任务是否存在
        result = subprocess.run(
            ['schtasks', '/query', '/tn', TASK_NAME], 
            capture_output=True, 
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        # 如果返回码为0，表示任务存在
        return result.returncode == 0
    except Exception as e:
        logger.error(f"检查任务计划时发生错误: {str(e)}")
        return False


def run_as_task() -> bool:
    """通过任务计划以管理员权限运行程序"""
    try:
        # 检查任务是否存在
        if check_task_exists():
            # 获取当前程序的路径
            if getattr(sys, 'frozen', False):
                app_path = sys.executable
            else:
                app_path = sys.executable
                app_args = f'"{os.path.abspath(sys.argv[0])}"'
            
            # 使用schtasks命令运行任务
            subprocess.Popen(
                ['schtasks', '/run', '/tn', TASK_NAME],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            logger.info(f"已通过任务计划启动管理员权限实例")
            return True
        else:
            logger.warning("任务计划不存在，无法通过任务计划启动")
            return False
    except Exception as e:
        logger.error(f"通过任务计划启动失败: {str(e)}")
        return False


def check_and_run_as_admin() -> bool:
    """检查是否需要以管理员权限运行"""
    # 先检查是否已经具有管理员权限
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        is_admin = False
    
    # 如果配置了需要管理员权限，但当前没有管理员权限，则尝试提权
    if config.get("general", "run_as_admin", False) and not is_admin:
        # 检查参数以防止无限循环
        if "--already-trying-uac" in sys.argv:
            logger.error("已经尝试过请求管理员权限但失败")
            return False
        
        # 首先尝试通过任务计划启动
        if run_as_task():
            # 如果成功通过任务计划启动，则退出当前实例
            return True
            
        # 如果任务计划不存在或启动失败，则使用传统的UAC提权方式
        try:
            # 获取当前程序路径
            if getattr(sys, 'frozen', False):
                app_path = sys.executable
                # 创建命令行参数，添加一个标记防止死循环
                app_args = "--already-trying-uac"
            else:
                # 对于脚本，使用Python解释器启动
                app_path = sys.executable
                app_args = f'"{os.path.abspath(sys.argv[0])}" --already-trying-uac'
            
            # 设置工作目录
            work_dir = os.path.dirname(os.path.abspath(app_path if getattr(sys, 'frozen', False) else sys.argv[0]))
            
            logger.info(f"尝试以管理员权限运行: {app_path} {app_args}")
            logger.info(f"工作目录: {work_dir}")
            
            # 以管理员权限重启
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", app_path, app_args, work_dir, 1
            )
            
            # 如果ShellExecuteW返回值大于32表示成功
            if ret > 32:
                logger.info("已成功请求管理员权限，程序将以管理员权限重新启动")
                # 让原进程停留片刻以确保新进程有时间启动
                import time
                time.sleep(1)
                return True
            else:
                error_msg = "未知错误"
                if ret == 0:
                    error_msg = "系统内存或资源不足"
                elif ret == 2:
                    error_msg = "指定的文件未找到"
                elif ret == 3:
                    error_msg = "指定的路径未找到"
                elif ret == 5:
                    error_msg = "拒绝访问"
                elif ret == 8:
                    error_msg = "内存不足"
                elif ret == 11:
                    error_msg = "无效的格式"
                elif ret == 26:
                    error_msg = "共享冲突"
                elif ret == 27:
                    error_msg = "文件名不完整或无效"
                elif ret == 28:
                    error_msg = "打印机脱机"
                elif ret == 29:
                    error_msg = "已超时"
                elif ret == 30:
                    error_msg = "文件已在使用中"
                elif ret == 31:
                    error_msg = "没有关联的应用程序可执行此文件"
                elif ret == 32:
                    error_msg = "操作已取消"
                
                logger.error(f"请求管理员权限失败，返回值: {ret}，错误: {error_msg}")
                logger.error(f"程序路径: {app_path}")
                logger.error(f"参数: {app_args}")
                logger.error(f"工作目录: {work_dir}")
        except Exception as e:
            logger.error(f"以管理员权限启动失败: {str(e)}")
    
    return False


def main() -> int:
    """主函数"""
    logger.info(f"{APP_NAME} v{VERSION} 正在启动...")
    
    # 检查单例
    if not check_single_instance():
        logger.error("程序已经在运行中，不允许多个实例同时运行")
        return 1
    
    # 检查并以管理员权限运行
    if check_and_run_as_admin():
        logger.info("正在以管理员权限重新启动程序...")
        # 正常退出，让新实例接管运行
        return 0
    
    # 检查是否已具有管理员权限
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        is_admin = False
        
    if is_admin:
        logger.info("程序已经以管理员权限运行")
    
    # 创建应用程序
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)
    
    # 初始化UI
    controller.init_ui(app)
    
    # 运行主程序
    return controller.run()
