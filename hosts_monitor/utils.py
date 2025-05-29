# -*- coding: utf-8 -*-
"""
工具函数模块 - 存放公共函数，避免代码重复
"""

import ctypes
import getpass
import logging
import os
import subprocess
import sys
import tempfile
import traceback
import winreg
import time
import win32com.client

# 检查win32com是否可用
try:
    win32com.client
    win32com_available = True
except ImportError:
    win32com_available = False
    logging.error("无法导入win32com.client模块，部分功能将不可用")

# 从版本模块导入常量
from .version import APP_NAME

# 创建日志记录器
logger = logging.getLogger(__name__)

# 应用名称常量
# APP_NAME 已从版本模块导入


def is_admin() -> bool:
    """检查当前进程是否具有管理员权限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False


def clean_up_admin_tasks() -> None:
    """清理管理员任务相关资源
    当程序退出时应调用此函数
    """
    try:
        # 获取配置
        from .config import config

        if config.get("general", "run_as_admin", False) and is_admin():
            # 仅在配置了管理员权限且当前是管理员权限运行时保留设置
            logger.info("保留管理员权限配置以供下次使用")
            return

        # 清理配置
        logger.info("清理管理员权限相关配置")
    except Exception as e:
        logger.error(f"清理管理员权限配置时出错: {str(e)}")


def get_app_paths():
    """获取应用程序路径信息"""
    # 确定是否是打包的可执行文件
    is_frozen = getattr(sys, "frozen", False)

    if is_frozen:
        # 打包后的应用程序路径
        app_path = sys.executable
        app_dir = os.path.dirname(app_path)
    else:
        # 脚本模式下的路径
        app_path = sys.executable  # Python解释器路径
        script_path = os.path.abspath(sys.argv[0])
        app_dir = os.path.dirname(script_path)

    return {
        "is_frozen": is_frozen,
        "app_path": app_path,
        "app_dir": app_dir,
        "script_path": os.path.abspath(sys.argv[0]) if not is_frozen else None,
    }


# 这里保留空间，但删除了任务计划相关的函数


def run_as_task() -> bool:
    """
    通过任务计划以管理员权限运行程序
    此函数被main.py调用以请求管理员权限

    返回:
        bool: 是否成功通过任务计划启动
    """
    # 首先检查win32com是否可用
    if not win32com_available:
        logger.error("win32com模块不可用，无法通过任务计划启动")
        return False

    try:
        # 获取当前程序信息
        paths = get_app_paths()
        task_name = f"{APP_NAME}_AdminImmediateTask"

        if paths["is_frozen"]:
            # 打包后的可执行文件
            python_exec = paths["app_path"]
            script_path = ""
        else:
            # 未打包的Python脚本
            python_exec = "pythonw.exe"
            script_path = paths["script_path"]
            # 尝试找到项目根目录下的run.py作为入口
            run_script_path = os.path.abspath(
                os.path.join(paths["app_dir"], "..", "run.py")
            )
            if os.path.exists(run_script_path):
                script_path = run_script_path

        # 检查任务是否已存在并删除
        try:
            if task_exists(task_name):
                scheduler = get_task_service()
                if scheduler:
                    root_folder = scheduler.GetFolder("\\")
                    root_folder.DeleteTask(task_name, 0)
                    logger.info(f"已删除旧的即时启动任务: {task_name}")
        except:
            pass

        # 创建新的计划任务
        if paths["is_frozen"]:
            # 为打包后的可执行文件添加参数
            args = "--already-trying-uac --skip-admin-check"
            # 创建任务
            result = create_admin_task(task_name, args, python_exec)
        else:
            # 未打包的Python脚本
            result = create_admin_task(task_name, script_path, python_exec)

        if not result:
            logger.error("创建即时管理员任务计划失败")
            return False

        try:
            # 立即运行任务
            scheduler = get_task_service()
            if scheduler:
                root_folder = scheduler.GetFolder("\\")
                task = root_folder.GetTask(task_name)
                task.Run("")
                logger.info(f"已立即启动任务: {task_name}")
                return True
        except Exception as e:
            logger.error(f"运行任务失败: {str(e)}")
            return False

        return False
    except Exception as e:
        logger.error(f"通过任务计划启动失败: {str(e)}")
        return False


def run_as_admin(app_path=None, app_args=None, work_dir=None):
    """
    使用UAC提权方式以管理员权限运行程序

    参数:
        app_path: 应用程序路径，如果为None则使用当前程序
        app_args: 应用程序参数
        work_dir: 工作目录

    返回:
        bool: 是否成功启动
    """
    # 导入必要的模块
    import os
    import sys
    import time
    import ctypes
    import traceback

    try:
        # 如果未提供参数，则获取当前程序信息
        paths = get_app_paths()

        if app_path is None:
            app_path = paths["app_path"]

        if app_args is None:
            if paths["is_frozen"]:
                app_args = ""
            else:
                # 确保脚本路径正确传递
                app_args = f'"{paths["script_path"]}"'

        if work_dir is None:
            work_dir = paths["app_dir"]

        # 记录详细的启动信息以便调试
        logger.info(f"===== 提权启动详细信息 =====")
        logger.info(f"应用路径: {app_path}")
        logger.info(f"应用参数: {app_args}")
        logger.info(f"工作目录: {work_dir}")
        logger.info(f"是否打包: {paths['is_frozen']}")

        # 确保路径存在
        if not os.path.exists(app_path):
            logger.error(f"应用程序路径不存在: {app_path}")
            return False

        # 以管理员权限启动 - 直接使用系统UAC弹窗，无需额外确认
        # 注意：某些情况下参数可能需要特殊处理，特别是包含空格的路径
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", app_path, app_args, work_dir, 1
        )

        # 如果ShellExecuteW返回值大于32表示成功
        if ret > 32:
            logger.info("已成功请求管理员权限，程序将以管理员权限重新启动")
            # 添加短暂延迟，确保新进程有足够时间启动
            time.sleep(0.5)
            return True
        else:
            error_codes = {
                0: "系统内存或资源不足",
                2: "指定的文件未找到",
                3: "指定的路径未找到",
                5: "拒绝访问",
                8: "内存不足",
                11: "无效的格式",
                26: "共享冲突",
                27: "文件名不完整或无效",
                28: "打印机脱机",
                29: "已超时",
                30: "文件已在使用中",
                31: "没有关联的应用程序可执行此文件",
                32: "操作已取消",
            }

            error_msg = error_codes.get(ret, f"未知错误代码: {ret}")
            logger.error(f"请求管理员权限失败，返回值: {ret}，错误: {error_msg}")
            return False
    except Exception as e:
        # 获取详细的异常信息
        exc_info = traceback.format_exc()
        logger.error(f"以管理员权限启动失败: {str(e)}")
        logger.error(f"详细异常信息: {exc_info}")
        return False


def set_autostart(enable=True, restart_param=False, update_config=True):
    """
    设置程序开机自启动

    参数:
        enable: 是否启用开机自启动
        restart_param: 是否添加重启参数
        update_config: 是否同步更新配置文件

    返回:
        bool: 操作是否成功
    """
    try:
        # 注册表路径
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"

        # 获取应用路径信息
        paths = get_app_paths()

        try:
            # 打开注册表项
            if is_admin():
                # 以管理员权限运行时，写入HKEY_LOCAL_MACHINE
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    key_path,
                    0,
                    winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE,
                )
            else:
                # 普通用户权限，写入HKEY_CURRENT_USER
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    key_path,
                    0,
                    winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE,
                )
        except WindowsError:
            # 如果键不存在，则创建
            if is_admin():
                key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            else:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)

        if enable:
            # 构建启动命令
            if paths["is_frozen"]:
                start_cmd = f'"{paths["app_path"]}"'
            else:
                start_cmd = f'"{paths["app_path"]}" "{paths["script_path"]}"'

            # 添加重启参数
            if restart_param:
                start_cmd += " --restarting"

            logger.info(f"设置开机自启动命令: {start_cmd}")

            # 设置自启动
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, start_cmd)
            logger.info("已启用开机自启动")
        else:
            # 删除自启动
            try:
                winreg.DeleteValue(key, APP_NAME)
                logger.info("已禁用开机自启动")
            except WindowsError as e:
                # 值不存在时不视为错误
                if e.winerror != 2:  # ERROR_FILE_NOT_FOUND
                    raise
                logger.info("开机自启动项不存在，无需删除")

        winreg.CloseKey(key)

        # 同步更新配置文件
        if update_config:
            try:
                from .config import config

                config.set("general", "auto_start", enable)
                config.save_config()
                logger.info(f"已将配置中的开机自启动设置更新为: {enable}")
            except Exception as config_e:
                logger.error(f"更新配置文件的开机自启动设置失败: {str(config_e)}")
                # 注意：即使配置更新失败，我们仍然认为注册表操作成功

        return True
    except Exception as e:
        logger.error(f"设置开机自启动失败: {str(e)}")
        return False


def check_autostart():
    """
    检查程序是否设置了开机自启动

    返回:
        bool: 是否已设置开机自启动
    """
    try:
        # 注册表路径
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"

        # 首先检查HKEY_LOCAL_MACHINE
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ
            )
            try:
                value, _ = winreg.QueryValueEx(key, APP_NAME)
                winreg.CloseKey(key)
                return True
            except WindowsError:
                pass
        except WindowsError:
            pass

        # 然后检查HKEY_CURRENT_USER
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            try:
                value, _ = winreg.QueryValueEx(key, APP_NAME)
                winreg.CloseKey(key)
                return True
            except WindowsError:
                pass
        except WindowsError:
            pass

        return False
    except Exception as e:
        logger.error(f"检查开机自启动设置失败: {str(e)}")
        return False


def sync_autostart_state():
    """
    同步开机自启动的配置状态和系统实际状态

    此函数确保配置文件中的auto_start设置与系统注册表中的设置一致

    返回:
        bool: 操作是否成功
    """
    try:
        # 获取系统实际自启动状态（只检查注册表）
        system_autostart = check_autostart()

        # 获取配置中的自启动状态
        from .config import config

        config_autostart = config.get("general", "auto_start", False)

        # 如果两者不一致，则同步
        if system_autostart != config_autostart:
            logger.info(
                f"开机自启动状态不一致 - 系统: {system_autostart}, 配置: {config_autostart}"
            )

            # 以系统实际状态为准
            if config.set("general", "auto_start", system_autostart):
                config.save_config()
                logger.info(
                    f"已将配置中的开机自启动设置更新为系统实际状态: {system_autostart}"
                )
                return True
            else:
                logger.error("更新配置中的开机自启动设置失败")
                return False

        logger.info(
            f"开机自启动状态已同步 - 系统: {system_autostart}, 配置: {config_autostart}"
        )
        return True
    except Exception as e:
        logger.error(f"同步开机自启动状态失败: {str(e)}")
        return False


def get_task_service():
    """获取Windows计划任务服务对象"""
    try:
        # 检查是否导入成功
        if not win32com_available:
            logger.error("win32com.client 模块未成功导入")
            return None

        # 使用已导入的模块
        scheduler = win32com.client.Dispatch("Schedule.Service")
        scheduler.Connect()
        return scheduler
    except Exception as e:
        logger.error(f"获取任务计划服务失败: {str(e)}")
        return None


def task_exists(task_name: str) -> bool:
    """检查指定名称的任务计划是否存在"""
    try:
        scheduler = get_task_service()
        if not scheduler:
            return False

        root_folder = scheduler.GetFolder("\\")
        try:
            root_folder.GetTask(task_name)
            return True
        except:
            return False
    except Exception as e:
        logger.error(f"检查任务计划是否存在时出错: {str(e)}")
        return False


def create_admin_task(
    task_name: str, script_path: str, python_exec: str = "pythonw.exe"
):
    """
    创建管理员权限的计划任务

    参数:
        task_name: 任务名称
        script_path: 脚本路径
        python_exec: Python执行文件
    """
    try:
        scheduler = get_task_service()
        if not scheduler:
            logger.error("无法获取任务计划服务")
            return False

        root_folder = scheduler.GetFolder("\\")
        task_def = scheduler.NewTask(0)

        task_def.RegistrationInfo.Description = f"{APP_NAME} 管理员权限静默启动任务"
        task_def.RegistrationInfo.Author = APP_NAME

        trigger = task_def.Triggers.Create(1)  # 登录时
        action = task_def.Actions.Create(0)  # 执行文件
        action.Path = python_exec
        action.Arguments = f'"{script_path}" --skip-admin-check'
        action.WorkingDirectory = os.path.dirname(script_path)

        task_def.Principal.UserId = ""
        task_def.Principal.LogonType = 3  # TASK_LOGON_INTERACTIVE_TOKEN
        task_def.Principal.RunLevel = 1  # TASK_RUNLEVEL_HIGHEST (管理员权限)

        task_def.Settings.Enabled = True
        task_def.Settings.Hidden = True
        task_def.Settings.StartWhenAvailable = True
        task_def.Settings.DisallowStartIfOnBatteries = False

        root_folder.RegisterTaskDefinition(
            task_name, task_def, 6, "", "", "", ""  # TASK_CREATE_OR_UPDATE
        )

        logger.info(f"成功注册计划任务：{task_name}，将在开机时以管理员权限静默运行")
        return True
    except Exception as e:
        import traceback

        exc_info = traceback.format_exc()
        logger.error(f"创建管理员任务计划失败: {str(e)}")
        logger.error(f"详细信息: {exc_info}")
        return False


def ensure_admin_task_if_elevated(
    task_name: str, script_path: str, python_exec="pythonw.exe"
):
    """仅在管理员权限下，创建计划任务"""
    if not is_admin():
        logger.warning("当前程序未以管理员权限运行，跳过计划任务创建")
        return False

    if task_exists(task_name):
        logger.info(f"计划任务已存在：{task_name}")
        return True
    else:
        logger.info(f"创建计划任务中：{task_name}")
        return create_admin_task(task_name, script_path, python_exec)


def register_system_restart() -> bool:
    """
    使用Windows任务计划程序实现静默管理员权限启动
    """
    # 检查win32com是否可用
    if not win32com_available:
        logger.error("win32com模块不可用，无法注册系统重启任务")
        return False

    try:
        task_name = f"{APP_NAME}_AdminAutostart"

        # 确保已获取管理员权限
        if not is_admin():
            logger.warning("没有管理员权限，无法注册系统重启任务")
            return False

        logger.info("正在配置静默管理员权限启动...")

        # 获取应用路径信息
        paths = get_app_paths()

        # 确定要执行的脚本路径
        if paths["is_frozen"]:
            # 打包后的可执行文件
            executable_path = paths["app_path"]
            python_exec = executable_path
            script_path = ""
        else:
            # 未打包的Python脚本
            python_exec = "pythonw.exe"
            script_path = paths["script_path"]
            # 尝试找到项目根目录下的run.py作为入口
            run_script_path = os.path.abspath(
                os.path.join(paths["app_dir"], "..", "run.py")
            )
            if os.path.exists(run_script_path):
                script_path = run_script_path
                logger.info(f"使用入口脚本: {script_path}")

        # 检查任务是否已存在
        if task_exists(task_name):
            logger.info(f"计划任务已存在：{task_name}")

            # 更新配置
            from .config import config

            config.set("general", "auto_start", True)
            config.set("general", "run_as_admin", True)
            config.save_config()
            return True
        else:
            logger.info(f"开始创建计划任务：{task_name}")

            if paths["is_frozen"]:
                # 打包后的应用直接使用可执行文件
                result = create_admin_task(task_name, "", python_exec)
            else:
                # 未打包的Python脚本
                result = create_admin_task(task_name, script_path, python_exec)

            if result:
                # 更新配置
                from .config import config

                config.set("general", "auto_start", True)
                config.set("general", "run_as_admin", True)
                config.save_config()

                logger.info("已使用任务计划程序配置开机自启并静默提升权限")
                return True
            else:
                logger.error("创建管理员任务计划失败")
                return False
    except ImportError:
        logger.error("win32com库不可用，请确保已安装pywin32")
        return False
    except Exception as e:
        # 获取详细的异常信息
        import traceback

        exc_info = traceback.format_exc()
        logger.error(f"配置自启动失败: {str(e)}")
        logger.error(f"详细信息: {exc_info}")
        return False
