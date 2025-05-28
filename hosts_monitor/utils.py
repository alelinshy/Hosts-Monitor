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
import winreg

import time

# 从版本模块导入常量
from .version import APP_NAME

# 创建日志记录器
logger = logging.getLogger(__name__)

# 任务计划名称常量
TASK_NAME = f"{APP_NAME.replace(' ', '_')}_AdminTask"


def is_admin() -> bool:
    """检查当前进程是否具有管理员权限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False


def check_task_exists(task_name=None) -> bool:
    """检查管理员权限任务计划是否存在"""
    if task_name is None:
        task_name = TASK_NAME

    try:
        # 使用schtasks命令查询任务是否存在
        result = subprocess.run(
            ["schtasks", "/query", "/tn", task_name],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        # 如果返回码为0，表示任务存在
        return result.returncode == 0
    except Exception as e:
        logger.error(f"检查任务计划时发生错误: {str(e)}")
        return False


def delete_scheduled_task(task_name=None) -> bool:
    """删除计划任务

    参数:
        task_name: 要删除的任务名称，默认使用TASK_NAME

    返回:
        bool: 操作是否成功
    """
    if task_name is None:
        task_name = TASK_NAME

    try:
        # 首先检查任务是否存在
        if not check_task_exists(task_name):
            logger.info(f"任务计划 {task_name} 不存在，无需删除")
            return True

        # 使用schtasks命令删除任务
        logger.info(f"正在删除任务计划: {task_name}")
        result = subprocess.run(
            ["schtasks", "/delete", "/tn", task_name, "/f"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        if result.returncode == 0:
            logger.info(f"已成功删除任务计划: {task_name}")
            return True
        else:
            logger.error(f"删除任务计划失败: {result.stderr.strip()}")
            return False
    except Exception as e:
        logger.error(f"删除任务计划过程中发生错误: {str(e)}")
        return False


def clean_up_admin_tasks() -> None:
    """清理管理员任务相关资源
    当程序退出时应调用此函数，确保不留下任务计划
    """
    try:
        # 如果配置了run_as_admin且已是管理员，则可以保留任务
        from .config import config

        if config.get("general", "run_as_admin", False) and is_admin():
            # 仅在配置了管理员权限且当前是管理员权限运行时保留任务
            logger.info("保留管理员权限任务计划以供下次使用")
            return

        # 其他情况删除任务计划，避免影响下次普通启动
        if delete_scheduled_task():
            logger.info("已清理管理员任务计划")
        else:
            logger.warning("清理管理员任务计划失败，可能会影响下次启动")
    except Exception as e:
        logger.error(f"清理管理员任务时出错: {str(e)}")


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


def create_task_xml(
    executable_path, args="", add_restart_param=False, user_id=None, logon_type="S4U"
):
    """
    生成用于注册计划任务的 XML 内容，任务将在用户登录时以最高权限静默运行。
    """
    # 如果需要添加重启参数且参数中尚未包含
    if add_restart_param and "--restarting" not in args:
        args += " --restarting" if args else "--restarting"

    # 获取当前用户信息
    if not user_id:
        domain = os.environ.get("USERDOMAIN", "")
        username = getpass.getuser()
        user_id = f"{domain}\\{username}" if domain else username

    # 工作目录 - 获取绝对路径，避免相对路径问题
    working_dir = os.path.abspath(os.path.dirname(executable_path))

    # 处理可执行文件路径 - 确保使用绝对路径
    executable_path = os.path.abspath(executable_path)

    # 记录详细配置信息
    logger.info(f"任务计划配置 - 可执行文件: {executable_path}")
    logger.info(f"任务计划配置 - 参数: {args}")
    logger.info(f"任务计划配置 - 工作目录: {working_dir}")
    logger.info(f"任务计划配置 - 用户: {user_id}")

    # 创建任务XML
    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>{APP_NAME} 管理员权限任务</Description>
  </RegistrationInfo>
  <Triggers>
    <!-- 用户登录后触发 -->
    <LogonTrigger>
      <Enabled>true</Enabled>
    </LogonTrigger>
    <!-- 如果你希望在系统启动时就运行，可以同时加上 BootTrigger：
    <BootTrigger>
      <Enabled>true</Enabled>
    </BootTrigger>
    -->
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{user_id}</UserId>
      <LogonType>{logon_type}</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>"{executable_path}"</Command>
      <Arguments>{args}</Arguments>
      <WorkingDirectory>{working_dir}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""

    return xml


def create_scheduled_task(
    task_name=None,
    xml_content=None,
    executable_path=None,
    args="",
    add_restart_param=False,
):
    """
    创建或更新计划任务

    参数:
        task_name: 任务名称，默认使用TASK_NAME
        xml_content: 任务XML内容，如果未提供则自动生成
        executable_path: 可执行文件路径，用于生成XML
        args: 命令行参数
        add_restart_param: 是否添加重启参数

    返回:
        bool: 操作是否成功
    """
    import traceback

    if task_name is None:
        task_name = TASK_NAME

    try:
        # 如果未提供XML内容，则根据参数生成
        if xml_content is None:
            if executable_path is None:
                # 获取应用路径信息
                paths = get_app_paths()
                executable_path = (
                    paths["app_path"] if paths["is_frozen"] else sys.executable
                )
                if not paths["is_frozen"] and not args:
                    # 对于Python脚本，确保路径正确传递
                    script_path = paths["script_path"]
                    args = f'"{script_path}"'

                logger.info(f"任务配置 - 可执行文件: {executable_path}")
                logger.info(f"任务配置 - 参数: {args}")

            # 生成XML内容
            xml_content = create_task_xml(
                executable_path=executable_path,
                args=args,
                add_restart_param=add_restart_param,
            )

        # 创建临时XML文件
        temp_xml_path = None
        with tempfile.NamedTemporaryFile(
            suffix=".xml", delete=False, mode="w", encoding="utf-16"
        ) as temp:
            temp_xml_path = temp.name
            temp.write(xml_content)
            logger.info(f"已创建临时XML文件: {temp_xml_path}")

        # 使用schtasks创建任务
        logger.info(f"正在创建管理员权限任务计划: {task_name}")
        result = subprocess.run(
            ["schtasks", "/create", "/tn", task_name, "/xml", temp_xml_path, "/f"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        # 删除临时文件
        try:
            if temp_xml_path and os.path.exists(temp_xml_path):
                os.unlink(temp_xml_path)
                logger.info(f"已删除临时XML文件: {temp_xml_path}")
        except Exception as e:
            logger.warning(f"删除临时XML文件失败: {str(e)}")

        # 检查结果
        if result.returncode != 0:
            logger.error(f"创建任务计划失败: {result.stderr.strip()}")
            # 输出完整的命令行和返回值以便调试
            logger.error(
                f"命令行: schtasks /create /tn {task_name} /xml {temp_xml_path} /f"
            )
            logger.error(f"返回代码: {result.returncode}")
            logger.error(f"标准输出: {result.stdout.strip()}")
            return False

        logger.info(f"管理员权限任务计划创建成功")

        # 确认任务是否真的存在
        if check_task_exists(task_name):
            logger.info(f"已确认任务计划 {task_name} 存在")
            return True
        else:
            logger.error(f"任务计划创建后无法找到: {task_name}")
            return False
    except Exception as e:
        # 获取详细的异常信息
        exc_info = traceback.format_exc()
        logger.error(f"创建管理员权限任务计划过程中发生错误: {str(e)}")
        logger.error(f"详细异常信息: {exc_info}")

        # 确保删除临时文件
        if (
            "temp_xml_path" in locals()
            and temp_xml_path
            and os.path.exists(temp_xml_path)
        ):
            try:
                os.unlink(temp_xml_path)
                logger.info(f"已删除临时XML文件: {temp_xml_path}")
            except Exception as clean_err:
                logger.warning(f"清理临时文件时出错: {str(clean_err)}")
        return False


def run_task(task_name=None):
    """运行指定的任务计划"""
    if task_name is None:
        task_name = TASK_NAME

    try:
        # 检查任务是否存在
        if not check_task_exists(task_name):
            logger.warning(f"任务计划不存在: {task_name}")
            return False

        # 使用subprocess.run阻塞方式运行任务，确保任务已启动
        result = subprocess.run(
            ["schtasks", "/run", "/tn", task_name],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        # 检查启动结果
        if result.returncode == 0:
            logger.info(f"已启动任务计划: {task_name}")
            # 等待一段时间，确保任务有足够时间启动
            time.sleep(1.5)
            return True
        else:
            logger.error(f"启动任务计划失败: {result.stderr.strip()}")
            return False
    except Exception as e:
        logger.error(f"运行任务计划失败: {str(e)}")
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

        # 准备启动命令
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
        # 获取系统实际自启动状态
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


def register_system_restart():
    """
    只通过计划任务实现开机/登录自启，并移除注册表 Run 项，避免 UAC 弹窗。
    """
    try:
        # 确保已获取管理员权限
        if not is_admin():
            logger.warning("没有管理员权限，无法注册系统重启任务")
            return False

        # 创建或更新计划任务
        success = create_scheduled_task(add_restart_param=True)
        if not success:
            logger.error("无法创建重启任务")
            return False

        # 清除原来的注册表自启动项，仅保留计划任务
        try:
            set_autostart(enable=False)
            logger.info("注册表自启动已移除")
        except Exception as e:
            logger.warning(f"移除注册表自启动失败: {e}")

        logger.info("系统重启任务注册成功（仅计划任务）")
        return True
    except Exception as e:
        logger.error(f"注册系统重启任务失败: {str(e)}")
        return False
