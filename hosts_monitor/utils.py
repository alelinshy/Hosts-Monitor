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
import pythoncom

# 检查win32com是否可用
win32com_available = False
try:
    import win32com.client

    win32com_available = True
except ImportError:
    logging.error("无法导入win32com.client模块，部分功能将不可用")

# 检查winshell是否可用
winshell_available = False
try:
    import winshell

    winshell_available = True
except ImportError:
    logging.error("无法导入winshell模块，部分功能将使用替代方法")

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


def configure_autostart_and_privileges(config):
    """
    配置应用程序的权限和自启动
    根据当前权限和用户设置处理三种情况:
    1. 非管理员权限，开机自启为关：提权仅对本次程序运行生效
    2. 非管理员权限，开机自启为开：使用快捷方式以正确权限自启动
    3. 管理员权限，开机自启为开：使用任务计划实现以管理员权限静默自启动

    参数:
        config: 应用程序配置对象

    返回:
        bool: 配置是否成功
    """
    is_admin_mode = is_admin()
    auto_start = config.get("general", "auto_start", False)
    run_as_admin = config.get("general", "run_as_admin", False)

    logger.info(
        f"配置权限和自启动: 管理员权限={is_admin_mode}, 开机自启={auto_start}, 管理员模式={run_as_admin}"
    )

    # 情况1: 非管理员权限，开机自启为关
    if not is_admin_mode and not auto_start:
        logger.info("配置为: 非管理员权限，开机自启为关，提权仅对本次程序运行生效")
        # 不执行额外操作，提权通过其他函数处理
        return True

    # 情况2: 非管理员权限，开机自启为开
    elif not is_admin_mode and auto_start:
        logger.info("配置为: 非管理员权限，开机自启为开，使用快捷方式实现自启动")
        # 创建快捷方式到启动文件夹
        return create_startup_shortcut(run_as_admin)

    # 情况3: 管理员权限，开机自启为开
    elif is_admin_mode and auto_start:
        logger.info("配置为: 管理员权限，开机自启为开，使用任务计划实现静默自启动")
        # 使用任务计划实现静默自启动
        return register_system_restart()

    # 其他情况: 管理员权限，开机自启为关
    else:
        logger.info("配置为: 管理员权限，开机自启为关，无需额外操作")
        return True


def create_startup_shortcut(run_as_admin=False):
    """
    在Windows启动文件夹中创建快捷方式

    参数:
        run_as_admin: 是否以管理员权限运行

    返回:
        bool: 是否成功创建快捷方式
    """
    try:
        # 确认win32com模块是否可用
        if not win32com_available:
            logger.error("win32com模块不可用，无法创建启动快捷方式")
            return False

        # 导入Dispatch类用于创建快捷方式
        from win32com.client import Dispatch

        # 获取应用路径信息
        paths = get_app_paths()

        # 获取启动文件夹路径（手动方法）
        startup_folder = os.path.join(
            os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup"
        )

        shortcut_path = os.path.join(startup_folder, f"{APP_NAME}.lnk")

        # 如果快捷方式已存在，先删除
        if os.path.exists(shortcut_path):
            os.remove(shortcut_path)
            logger.info(f"已删除旧的启动快捷方式: {shortcut_path}")

        # 创建新的快捷方式
        shell = Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)

        # 设置目标路径和工作目录
        if paths["is_frozen"]:
            shortcut.Targetpath = paths["app_path"]
        else:
            # 未打包的Python脚本
            shortcut.Targetpath = sys.executable
            # 尝试找到项目根目录下的run.py作为入口
            run_script_path = os.path.abspath(
                os.path.join(paths["app_dir"], "..", "run.py")
            )
            if os.path.exists(run_script_path):
                shortcut.Arguments = f'"{run_script_path}"'
            else:
                shortcut.Arguments = f'"{paths["script_path"]}"'

        shortcut.WorkingDirectory = paths["app_dir"]
        shortcut.IconLocation = (
            paths["app_path"] if paths["is_frozen"] else sys.executable
        )

        # 先保存快捷方式
        shortcut.save()

        # 设置管理员权限标志
        if run_as_admin:
            # 打开文件并修改字节
            with open(shortcut_path, "rb+") as f:
                # 定位到包含管理员标志的偏移位置
                f.seek(0x15)
                # 设置"以管理员身份运行"标志
                f.write(bytes([0x20]))

        logger.info(f"成功创建启动快捷方式: {shortcut_path}")
        logger.info(
            f"快捷方式属性: 目标={shortcut.Targetpath}, 参数={shortcut.Arguments}, 管理员权限={run_as_admin}"
        )
        return True

    except Exception as e:
        logger.error(f"创建启动快捷方式失败: {str(e)}")
        return False


def get_task_service():
    """获取Windows计划任务服务对象"""
    try:
        global win32com_available
        # 检查是否导入成功
        if not win32com_available:
            try:
                import win32com.client

                win32com_available = True
            except ImportError:
                logger.error("win32com.client 模块未成功导入")
                return None

        # 使用已导入的模块
        import win32com.client

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
        # 获取任务计划服务
        scheduler = get_task_service()
        if not scheduler:
            logger.error("无法获取任务计划服务")
            return False

        # 获取根文件夹
        root_folder = scheduler.GetFolder("\\")

        # 创建新任务定义
        task_def = scheduler.NewTask(0)

        # 设置任务注册信息
        task_def.RegistrationInfo.Description = f"{APP_NAME} 管理员权限静默启动任务"
        # 创建登录触发器
        task_def.RegistrationInfo.Author = APP_NAME
        # 直接创建登录触发器，TASK_TRIGGER_LOGON(8)表示用户登录时
        trigger = task_def.Triggers.Create(8)  # 明确设置仅在特定用户登录时触发
        username = "ALEARNER\\Splrad"  # 直接指定用户账户
        logger.info(f"设置触发器在用户 {username} 登录时启动，延迟5秒")

        # 设置触发用户和延迟时间
        try:
            trigger.UserId = username  # 指定用户
            trigger.Delay = "PT5S"  # 设置延迟时间为5秒 (格式为ISO8601持续时间)
        except Exception as e:
            logger.info(f"设置触发器属性时出错: {str(e)}，将使用默认设置")

        # 确保触发器启用
        trigger.Enabled = True  # 创建执行动作
        action = task_def.Actions.Create(0)
        action.Path = python_exec

        # 根据是否是打包的可执行文件设置不同的参数
        if script_path and script_path.strip():
            # 对于脚本路径，需要正确处理引号
            # 如果是字符串参数，确保用引号包裹
            if script_path.startswith('"') and script_path.endswith('"'):
                action.Arguments = f"{script_path} --skip-admin-check"
            else:
                action.Arguments = f'"{script_path}" --skip-admin-check'
        else:  # 对于打包的可执行文件，直接设置参数
            action.Arguments = "--minimized"

        # 设置工作目录
        if script_path:
            action.WorkingDirectory = os.path.dirname(script_path)  # 设置执行账户和权限
        username = getpass.getuser()  # 获取当前用户名
        task_def.Principal.UserId = username  # 使用当前用户
        task_def.Principal.LogonType = 3  # TASK_LOGON_INTERACTIVE_TOKEN
        task_def.Principal.RunLevel = 1  # TASK_RUNLEVEL_HIGHEST (管理员权限)

        # 设置其他任务选项
        task_def.Settings.Enabled = True
        task_def.Settings.Hidden = False  # 可见任务，便于调试
        task_def.Settings.StartWhenAvailable = True
        task_def.Settings.DisallowStartIfOnBatteries = (
            False  # 设置任务文件夹位置为程序目录
        )
        task_folder_path = ""  # 根文件夹 (默认)

        # 尝试获取程序所在位置作为任务文件夹
        paths = get_app_paths()
        if paths and "app_dir" in paths:
            folder_name = os.path.basename(paths["app_dir"])
            if folder_name:
                try:
                    # 先检查文件夹是否存在，不存在则创建
                    try:
                        task_folder = scheduler.GetFolder("\\" + folder_name)
                        logger.info(f"任务计划文件夹已存在: {folder_name}")
                    except:
                        # 创建文件夹
                        root_folder.CreateFolder(folder_name)
                        logger.info(f"已创建任务计划文件夹: {folder_name}")
                        task_folder = scheduler.GetFolder("\\" + folder_name)

                    # 使用程序文件夹作为任务位置
                    task_folder_path = "\\" + folder_name
                    logger.info(f"将使用自定义任务文件夹: {task_folder_path}")
                    root_folder = task_folder
                except Exception as e:
                    logger.warning(f"创建任务文件夹失败: {str(e)}，将使用根文件夹")

        # 注册任务定义
        # 使用数字常量而不是空字符串，避免类型转换错误
        root_folder.RegisterTaskDefinition(
            task_name,  # 任务名称
            task_def,  # 任务定义
            6,  # TASK_CREATE_OR_UPDATE
            None,  # 用户名 (使用None代替空字符串)
            None,  # 密码 (使用None代替空字符串)
            3,  # TASK_LOGON_INTERACTIVE_TOKEN
            None,  # sddl (使用None代替空字符串)
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

        # 确保任务不存在，先删除旧任务
        try:
            if task_exists(task_name):
                scheduler = get_task_service()
                if scheduler:
                    root_folder = scheduler.GetFolder("\\")
                    root_folder.DeleteTask(task_name, 0)
                    logger.info(f"已删除旧的自启动任务: {task_name}")
        except Exception as e:
            logger.warning(f"删除旧任务失败，将尝试覆盖: {str(e)}")

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

            if paths["is_frozen"]:  # 打包后的应用直接使用可执行文件
                # 确保添加必要的启动参数
                result = create_admin_task(task_name, "--minimized", python_exec)
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


def sync_autostart_state(config):
    """
    同步自启动状态到系统

    根据配置中的自启动和管理员权限设置，确保系统中的自启动状态与配置一致

    参数:
        config: 应用程序配置对象

    返回:
        bool: 是否成功同步
    """
    auto_start = config.get("general", "auto_start", False)
    run_as_admin = config.get("general", "run_as_admin", False)
    is_admin_mode = is_admin()

    logger.info(
        f"同步自启动状态: 管理员权限={is_admin_mode}, 开机自启={auto_start}, 管理员模式={run_as_admin}"
    )

    task_name = f"{APP_NAME}_AdminAutostart"
    shortcut_path = os.path.join(
        os.path.join(
            os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup"
        ),
        f"{APP_NAME}.lnk",
    )

    try:
        # 检查现有的自启动方式并清理
        task_exists_flag = task_exists(task_name)
        shortcut_exists_flag = os.path.exists(shortcut_path)

        # 如果配置为不自启动，则移除所有自启动方式
        if not auto_start:
            if task_exists_flag:
                try:
                    scheduler = get_task_service()
                    if scheduler:
                        root_folder = scheduler.GetFolder("\\")
                        root_folder.DeleteTask(task_name, 0)
                        logger.info(f"已删除计划任务: {task_name}")
                except Exception as e:
                    logger.error(f"删除计划任务失败: {str(e)}")

            if shortcut_exists_flag:
                try:
                    os.remove(shortcut_path)
                    logger.info(f"已删除启动快捷方式: {shortcut_path}")
                except Exception as e:
                    logger.error(f"删除快捷方式失败: {str(e)}")

            logger.info("已关闭所有自启动方式")
            return True

        # 如果配置为自启动且需要管理员权限
        if auto_start and run_as_admin:
            # 删除快捷方式，使用任务计划
            if shortcut_exists_flag:
                try:
                    os.remove(shortcut_path)
                    logger.info(f"已删除常规启动快捷方式: {shortcut_path}")
                except Exception as e:
                    logger.error(f"删除快捷方式失败: {str(e)}")

            # 如果有管理员权限，创建任务计划
            if is_admin_mode:
                return register_system_restart()
            else:
                logger.warning("需要管理员权限才能创建计划任务，请以管理员身份运行程序")
                return False

        # 如果配置为自启动但不需要管理员权限
        if auto_start and not run_as_admin:
            # 删除任务计划，使用快捷方式
            if task_exists_flag:
                try:
                    scheduler = get_task_service()
                    if scheduler:
                        root_folder = scheduler.GetFolder("\\")
                        root_folder.DeleteTask(task_name, 0)
                        logger.info(f"已删除计划任务: {task_name}")
                except Exception as e:
                    logger.error(f"删除计划任务失败: {str(e)}")

            # 创建快捷方式
            return create_startup_shortcut(False)

        return True
    except Exception as e:
        logger.error(f"同步自启动状态失败: {str(e)}")
        return False


def check_autostart() -> bool:
    """
    检查应用程序是否设置了开机自启动

    返回:
        bool: 是否已设置开机自启动
    """
    task_name = f"{APP_NAME}_AdminAutostart"
    shortcut_path = os.path.join(
        os.path.join(
            os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup"
        ),
        f"{APP_NAME}.lnk",
    )

    # 检查任务计划或快捷方式是否存在
    has_task = task_exists(task_name)
    has_shortcut = os.path.exists(shortcut_path)

    logger.info(f"自启动检查: 计划任务={has_task}, 快捷方式={has_shortcut}")

    # 任一存在则表示已设置自启动
    return has_task or has_shortcut


def set_autostart(enable: bool = True) -> bool:
    """
    设置或取消开机自启动

    参数:
        enable: 是否启用开机自启动

    返回:
        bool: 操作是否成功
    """
    try:
        # 从配置中获取管理员权限设置
        from .config import config

        run_as_admin = config.get("general", "run_as_admin", False)

        # 更新配置
        config.set("general", "auto_start", enable)
        config.save_config()

        logger.info(
            f"正在{'启用' if enable else '禁用'}开机自启动，管理员权限={run_as_admin}"
        )

        # 同步自启动状态到系统
        result = sync_autostart_state(config)

        if result:
            logger.info(f"已{'启用' if enable else '禁用'}开机自启动")
        else:
            logger.error(f"{'启用' if enable else '禁用'}开机自启动失败")

        return result

    except Exception as e:
        logger.error(f"设置开机自启动失败: {str(e)}")
        import traceback

        logger.error(f"详细错误: {traceback.format_exc()}")
        return False
