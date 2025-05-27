# -*- coding: utf-8 -*-
"""
主程序入口
"""

import os
import sys
import time
import socket
import subprocess
from PyQt6.QtWidgets import QApplication

from . import logger
from .version import APP_NAME, VERSION
from .config import config
from .controller import controller
from .utils import TASK_NAME, is_admin, get_app_paths, run_as_admin, check_task_exists


def check_single_instance() -> bool:
    """检查程序是否已经运行，确保只有一个实例"""
    # 注意：这个函数保留在main.py中，因为它是主程序特有的逻辑
    # 并且utils.py中没有对应的函数实现
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


def run_as_task() -> bool:
    """通过任务计划以管理员权限运行程序"""
    try:
        # 导入工具函数
        from .utils import check_task_exists, run_task
        
        # 检查任务是否存在
        if check_task_exists():
            # 如果是重启操作，确保任务包含重启参数
            if "--restarting" in sys.argv:
                # 更新任务计划
                create_restart_task(update=True)
            
            # 运行任务
            if run_task():
                logger.info(f"已通过任务计划启动管理员权限实例")
                return True
            else:
                return False
        else:
            logger.warning("任务计划不存在，无法通过任务计划启动")
            
            # 尝试创建任务计划
            if create_restart_task():
                # 重试运行
                return run_as_task()
            
            return False
    except Exception as e:
        logger.error(f"通过任务计划启动失败: {str(e)}")
        return False


def check_and_run_as_admin() -> bool:
    """检查是否需要以管理员权限运行"""
    # 导入工具函数
    from .utils import is_admin, run_as_admin
    
    # 先检查是否已经具有管理员权限
    admin_status = is_admin()
    
    # 检查是否为重启标识
    is_restarting = "--restarting" in sys.argv
    
    # 如果是系统重启启动且已经配置了需要管理员权限
    if is_restarting and config.get("general", "run_as_admin", False):
        # 如果已经是管理员，无需处理
        if admin_status:
            logger.info("系统重启后已经以管理员权限运行")
            return False
            
        # 通过任务计划静默获取管理员权限
        if run_as_task():
            logger.info("系统重启后通过任务计划获取管理员权限成功")
            return True
    
    # 如果配置了需要管理员权限，但当前没有管理员权限，则尝试提权
    if config.get("general", "run_as_admin", False) and not admin_status:
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
            # 创建命令行参数
            app_args = "--already-trying-uac"
            # 如果是重启，保留重启标识
            if is_restarting:
                app_args += " --restarting"
            
            # 使用工具函数以管理员权限运行
            if run_as_admin(app_args=app_args):
                # 让原进程停留片刻以确保新进程有时间启动
                time.sleep(1)
                return True
        except Exception as e:
            logger.error(f"以管理员权限启动失败: {str(e)}")
    
    return False


def create_restart_task(update=False) -> bool:
    """创建重启时使用的静默管理员权限任务"""
    try:
        # 导入工具函数
        from .utils import check_task_exists, create_scheduled_task
        
        # 检查任务是否已存在，且非更新模式
        if check_task_exists() and not update:
            return True
            
        logger.info(f"{'更新' if update else '创建'}管理员权限任务计划")
        
        # 使用工具函数创建任务
        result = create_scheduled_task(add_restart_param=True)
        
        if result:
            logger.info(f"管理员权限任务计划{'更新' if update else '创建'}成功")
        else:
            logger.error(f"{'更新' if update else '创建'}任务计划失败")
            
        return result
    except Exception as e:
        logger.error(f"创建管理员权限任务计划失败: {str(e)}")
        return False


def register_system_restart() -> bool:
    """注册系统重启时的自动启动任务"""
    try:
        # 导入工具函数
        from .utils import register_system_restart as utils_register_restart
        
        # 使用工具模块的函数
        return utils_register_restart()
    except Exception as e:
        logger.error(f"注册系统重启任务失败: {str(e)}")
        return False


def main() -> int:
    """主函数"""
    logger.info(f"{APP_NAME} v{VERSION} 正在启动...")
    
    # 检查单例
    if not check_single_instance():
        logger.error("程序已经在运行中，不允许多个实例同时运行")
        return 1
    
    # 检查是否为系统重启
    is_restarting = "--restarting" in sys.argv
    if is_restarting:
        logger.info("检测到系统重启后启动")
    
    # 检查并以管理员权限运行
    if check_and_run_as_admin():
        logger.info("正在以管理员权限重新启动程序...")
        # 正常退出，让新实例接管运行
        return 0
    
    # 检查是否已具有管理员权限
    admin_status = is_admin()
        
    if admin_status:
        logger.info("程序已经以管理员权限运行")
        # 如果是管理员权限且需要管理员权限运行，注册系统重启任务
        if config.get("general", "run_as_admin", False):
            # 确保已创建系统重启任务
            register_system_restart()
    
    # 创建应用程序
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)
    
    # 初始化UI
    controller.init_ui(app)
    
    # 运行主程序
    return controller.run()
