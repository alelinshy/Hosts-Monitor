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
        import traceback
        from .utils import (
            check_task_exists,
            run_task,
            create_scheduled_task,
            delete_scheduled_task,
        )

        # 先删除可能存在的旧任务
        if check_task_exists():
            logger.info("发现已存在的管理员权限任务计划，将先删除")
            delete_scheduled_task()
            time.sleep(0.5)  # 给系统一点时间处理删除操作

        # 获取当前参数，准备添加到任务中
        current_args = " ".join(sys.argv[1:])
        if "--skip-admin-check" not in current_args:
            current_args += (
                " --skip-admin-check" if current_args else "--skip-admin-check"
            )

        if "--restarting" in sys.argv and "--restarting" not in current_args:
            current_args += " --restarting" if current_args else "--restarting"

        # 创建一次性任务 - 运行后自动删除
        logger.info("正在创建一次性管理员权限任务计划...")
        task_created = create_scheduled_task(
            args=current_args,
            add_restart_param="--restarting" in sys.argv,
            delete_after_run=True,  # 重要：运行一次后自动删除
        )

        if not task_created:
            logger.error("创建一次性管理员权限任务计划失败")
            return False

        # 使用任务运行程序
        logger.info("正在通过任务计划启动管理员权限实例...")
        if run_task():
            logger.info(f"已通过一次性任务计划启动管理员权限实例")
            # 增加额外等待时间，确保新实例有足够时间启动
            time.sleep(1)
            return True
        else:
            logger.error("通过任务计划启动失败")
            # 清理失败的任务
            delete_scheduled_task()
            return False
    except Exception as e:
        # 获取详细的异常信息
        exc_info = traceback.format_exc()
        logger.error(f"通过任务计划启动失败: {str(e)}")
        logger.error(f"详细异常信息: {exc_info}")
        return False


def check_and_run_as_admin() -> bool:
    """检查是否需要以管理员权限运行"""
    # 导入工具函数
    import traceback
    from .utils import is_admin, run_as_admin, get_app_paths

    try:
        # 先检查是否已经具有管理员权限
        admin_status = is_admin()

        # 检查是否为重启标识
        is_restarting = "--restarting" in sys.argv

        # 检查是否是通过UAC提权重启的
        is_uac_restart = "--already-trying-uac" in sys.argv

        # 检查是否跳过管理员权限检查（由任务计划自动添加的参数）
        skip_admin_check = "--skip-admin-check" in sys.argv

        # 记录启动信息，用于调试
        logger.info(
            f"启动信息 - 管理员权限: {admin_status}, 重启标识: {is_restarting}, UAC提权: {is_uac_restart}, 跳过权限检查: {skip_admin_check}"
        )
        logger.info(f"启动参数: {sys.argv}")

        # 如果是由任务计划启动并要求跳过管理员权限检查，直接返回
        if skip_admin_check:
            logger.info("检测到跳过管理员权限检查的参数，继续启动")
            return False

        # 如果已经通过UAC提权重启且已具备管理员权限，直接返回
        if is_uac_restart and admin_status:
            logger.info("已通过UAC成功获取管理员权限")
            return False

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
            if is_uac_restart:
                logger.error("已经尝试过请求管理员权限但失败")
                return False

            # 首先尝试通过任务计划启动
            if run_as_task():
                # 如果成功通过任务计划启动，则退出当前实例
                logger.info("通过任务计划成功启动管理员权限实例")
                return True

            # 如果任务计划不存在或启动失败，则使用传统的UAC提权方式
            try:
                # 获取程序路径信息
                paths = get_app_paths()

                # 准备应用程序路径和参数
                app_path = paths["app_path"]

                # 创建命令行参数，添加跳过UAC检查参数
                if paths["is_frozen"]:
                    app_args = "--already-trying-uac --skip-admin-check"
                    # 如果是重启，保留重启标识
                    if is_restarting:
                        app_args += " --restarting"
                else:
                    # 对于Python脚本，确保使用正确的入口脚本
                    # 尝试找到项目根目录下的run.py
                    run_script_path = os.path.abspath(
                        os.path.join(paths["app_dir"], "..", "run.py")
                    )

                    if os.path.exists(run_script_path):
                        # 如果存在run.py，使用它作为入口
                        script_path = run_script_path
                        logger.info(f"找到入口脚本: {script_path}")
                    else:
                        # 否则使用当前脚本路径
                        script_path = paths["script_path"]
                        logger.info(f"使用当前脚本: {script_path}")

                    app_args = (
                        f'"{script_path}" --already-trying-uac --skip-admin-check'
                    )
                    if is_restarting:
                        app_args += " --restarting"

                # 获取工作目录 - 对于Python脚本，使用项目根目录
                if paths["is_frozen"]:
                    work_dir = paths["app_dir"]
                else:
                    # 获取项目根目录（向上一级）
                    work_dir = os.path.abspath(os.path.join(paths["app_dir"], ".."))

                logger.info(f"尝试通过UAC提权启动")
                logger.info(f"应用路径: {app_path}")
                logger.info(f"应用参数: {app_args}")
                logger.info(f"工作目录: {work_dir}")

                # 直接使用工具函数以管理员权限运行，依赖系统UAC弹窗进行确认
                if run_as_admin(
                    app_path=app_path, app_args=app_args, work_dir=work_dir
                ):
                    logger.info("已成功通过UAC请求管理员权限，等待新实例启动")
                    # 让原进程停留片刻以确保新进程有时间启动
                    time.sleep(2)
                    return True
                else:
                    logger.error("UAC提权失败")
            except Exception as e:
                # 获取详细的异常信息
                exc_info = traceback.format_exc()
                logger.error(f"以管理员权限启动失败: {str(e)}")
                logger.error(f"详细异常信息: {exc_info}")

        return False
    except Exception as e:
        # 捕获整个函数的异常
        exc_info = traceback.format_exc()
        logger.error(f"检查管理员权限过程中发生错误: {str(e)}")
        logger.error(f"详细异常信息: {exc_info}")
        return False


def create_restart_task(update=False, delete_after_run=False) -> bool:
    """创建重启时使用的静默管理员权限任务

    参数:
        update: 是否是更新现有任务
        delete_after_run: 是否在运行一次后自动删除任务
    """
    try:
        import traceback

        # 导入工具函数
        from .utils import (
            check_task_exists,
            create_scheduled_task,
            delete_scheduled_task,
        )

        # 如果是更新模式，先删除现有任务
        if update and check_task_exists():
            logger.info("正在删除现有任务以进行更新")
            delete_scheduled_task()
            time.sleep(0.5)  # 给系统一点时间处理删除操作
        # 如果是非更新模式且任务已存在，直接返回成功
        elif not update and check_task_exists():
            logger.info("任务计划已存在，无需创建")
            return True

        logger.info(f"{'更新' if update else '创建'}管理员权限任务计划")
        logger.info(f"任务配置: 运行后{'自动删除' if delete_after_run else '保留'}")

        # 准备额外参数
        extra_args = "--skip-admin-check"

        # 使用工具函数创建任务
        result = create_scheduled_task(
            args=extra_args,
            add_restart_param=True,
            delete_after_run=delete_after_run,  # 传递是否自动删除选项
        )

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
    import traceback

    logger.info(f"{APP_NAME} v{VERSION} 正在启动...")

    # 检查单例
    if not check_single_instance():
        logger.error("程序已经在运行中，不允许多个实例同时运行")
        return 1

    # 检查是否为系统重启
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
            register_system_restart()
            logger.info("已配置系统重启任务，下次开机将静默以管理员权限启动")
    # 同步开机自启动状态，确保配置文件与系统实际状态一致
    from .utils import sync_autostart_state

    sync_autostart_state()

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
