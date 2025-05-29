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
from .utils import (
    is_admin,
    get_app_paths,
    run_as_admin,
    run_as_task,
    register_system_restart,
    sync_autostart_state,
    clean_up_admin_tasks,
)


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


def check_and_run_as_admin() -> bool:
    """
    检查是否需要以管理员权限运行
    注意：此函数保留在main.py中，因为它是主程序特有的流程控制逻辑
    """
    # 导入工具函数
    import traceback
    from .utils import is_admin, run_as_admin, get_app_paths

    try:
        # 先检查是否已经具有管理员权限
        admin_status = is_admin()

        # 检查命令行参数
        is_restarting = "--restarting" in sys.argv
        is_uac_restart = "--already-trying-uac" in sys.argv
        skip_admin_check = "--skip-admin-check" in sys.argv

        # 记录启动信息
        logger.info(
            f"启动信息 - 管理员权限: {admin_status}, 重启标识: {is_restarting}, UAC提权: {is_uac_restart}, 跳过权限检查: {skip_admin_check}"
        )
        logger.info(f"启动参数: {sys.argv}")

        # 如果跳过管理员检查，直接返回
        if skip_admin_check:
            logger.info("检测到跳过管理员检查标记，直接启动程序")
            # 确保配置正确
            if admin_status and config.get("general", "run_as_admin", False) != True:
                config.set("general", "run_as_admin", True)
                config.save_config()
            return False

        # 如果已提权成功，直接返回
        if is_uac_restart and admin_status:
            logger.info("已通过UAC成功获取管理员权限")
            return False

        # 如果是重启且需要管理员权限，但已经有管理员权限，直接返回
        if (
            is_restarting
            and config.get("general", "run_as_admin", False)
            and admin_status
        ):
            logger.info("系统重启后已经以管理员权限运行")
            return False

        # 如果配置了需要管理员权限，但当前没有管理员权限，则尝试提权
        if config.get("general", "run_as_admin", False) and not admin_status:
            # 防止无限循环
            if is_uac_restart:
                logger.error("已经尝试过请求管理员权限但失败")
                return False

            # 首先尝试通过任务计划启动
            if run_as_task():
                logger.info("通过任务计划成功启动管理员权限实例")
                return True

            # 如果任务计划失败，使用UAC提权
            try:
                paths = get_app_paths()
                app_path = paths["app_path"]

                # 准备命令行参数
                if paths["is_frozen"]:
                    app_args = "--already-trying-uac --skip-admin-check"
                    if is_restarting:
                        app_args += " --restarting"
                else:
                    # 查找入口脚本
                    run_script_path = os.path.abspath(
                        os.path.join(paths["app_dir"], "..", "run.py")
                    )
                    script_path = (
                        run_script_path
                        if os.path.exists(run_script_path)
                        else paths["script_path"]
                    )
                    app_args = (
                        f'"{script_path}" --already-trying-uac --skip-admin-check'
                    )
                    if is_restarting:
                        app_args += " --restarting"

                # 设置工作目录
                work_dir = (
                    paths["app_dir"]
                    if paths["is_frozen"]
                    else os.path.abspath(os.path.join(paths["app_dir"], ".."))
                )

                # 尝试UAC提权
                logger.info(f"尝试通过UAC提权启动")
                if run_as_admin(
                    app_path=app_path, app_args=app_args, work_dir=work_dir
                ):
                    logger.info("已成功通过UAC请求管理员权限，等待新实例启动")
                    time.sleep(2)  # 给新实例启动的时间
                    return True
                else:
                    logger.error("UAC提权失败")
            except Exception as e:
                exc_info = traceback.format_exc()
                logger.error(f"以管理员权限启动失败: {str(e)}")
                logger.error(f"详细异常信息: {exc_info}")

        return False
    except Exception as e:
        exc_info = traceback.format_exc()
        logger.error(f"检查管理员权限过程中发生错误: {str(e)}")
        logger.error(f"详细异常信息: {exc_info}")
        return False


# 注意：此处已经从utils.py中导入了register_system_restart


def main() -> int:
    """主函数"""
    import traceback

    logger.info(f"{APP_NAME} v{VERSION} 正在启动...")

    # 检查单例
    if not check_single_instance():
        logger.error("程序已经在运行中，不允许多个实例同时运行")
        return 1  # 检查是否为系统重启
    is_restarting = "--restarting" in sys.argv
    if is_restarting:
        logger.info("检测到系统重启后启动")

    # 检查命令行参数中是否有跳过管理员检查的标记
    skip_admin_check = "--skip-admin-check" in sys.argv

    # 如果没有跳过检查，则执行管理员权限检查
    if not skip_admin_check:
        # 检查并以管理员权限运行
        if check_and_run_as_admin():
            logger.info("正在以管理员权限重新启动程序...")
            # 延长等待时间，确保新实例有足够时间启动
            time.sleep(3)
            logger.info("退出当前实例，由管理员权限实例接管")
            # 正常退出，让新实例接管运行
            return 0
    else:
        logger.info("检测到跳过管理员检查标记，直接启动程序")

    # 检查是否已具有管理员权限
    admin_status = is_admin()
    if admin_status:
        logger.info("程序已经以管理员权限运行")
        # 如果是管理员权限且需要管理员权限运行，注册系统重启任务
        if config.get("general", "run_as_admin", False):
            # 确保已创建系统重启任务
            # 如果是重启，确保任务是最新的
            from .utils import register_system_restart

            register_system_restart()
            logger.info(
                "已配置系统重启任务，下次开机将静默以管理员权限启动"
            )  # 同步开机自启动状态，确保配置文件与系统实际状态一致
    from .utils import sync_autostart_state

    sync_autostart_state(config)

    # 创建应用程序
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)

    # 初始化UI
    controller.init_ui(app)

    # 导入任务清理函数
    from .utils import clean_up_admin_tasks

    # 注册退出时清理函数
    import atexit

    atexit.register(clean_up_admin_tasks)

    try:
        # 运行主程序
        return_code = controller.run()
    finally:
        # 确保退出前清理任务
        try:
            clean_up_admin_tasks()
        except Exception as e:
            logger.error(f"退出时清理任务失败: {str(e)}")

    return return_code
