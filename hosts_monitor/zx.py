import win32com.client
import os
import ctypes
import sys


def is_admin() -> bool:
    """判断当前是否为管理员权限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def get_task_service():
    scheduler = win32com.client.Dispatch("Schedule.Service")
    scheduler.Connect()
    return scheduler


def task_exists(task_name: str) -> bool:
    scheduler = get_task_service()
    root_folder = scheduler.GetFolder("\\")
    try:
        root_folder.GetTask(task_name)
        return True
    except:
        return False


def create_admin_task(
    task_name: str, script_path: str, python_exec: str = "pythonw.exe"
):
    scheduler = get_task_service()
    root_folder = scheduler.GetFolder("\\")
    task_def = scheduler.NewTask(0)

    task_def.RegistrationInfo.Description = "管理员权限静默启动任务"
    task_def.RegistrationInfo.Author = "PythonApp"

    trigger = task_def.Triggers.Create(1)  # 登录时
    action = task_def.Actions.Create(0)  # 执行文件
    action.Path = python_exec
    action.Arguments = f'"{script_path}"'
    action.WorkingDirectory = os.path.dirname(script_path)

    task_def.Principal.UserId = ""
    task_def.Principal.LogonType = 3  # TASK_LOGON_INTERACTIVE_TOKEN
    task_def.Principal.RunLevel = 1  # TASK_RUNLEVEL_HIGHEST

    task_def.Settings.Enabled = True
    task_def.Settings.Hidden = True
    task_def.Settings.StartWhenAvailable = True
    task_def.Settings.DisallowStartIfOnBatteries = False

    root_folder.RegisterTaskDefinition(
        task_name, task_def, 6, "", "", "", ""  # TASK_CREATE_OR_UPDATE
    )

    print(f"[✓] 成功注册计划任务：{task_name}，将在开机时以管理员权限静默运行。")


def ensure_admin_task_if_elevated(
    task_name: str, script_path: str, python_exec="pythonw.exe"
):
    """仅在管理员权限下，创建计划任务"""
    if not is_admin():
        print("[!] 当前程序未以管理员权限运行，跳过计划任务创建。")
        return

    if task_exists(task_name):
        print(f"[✔] 计划任务已存在：{task_name}")
    else:
        print(f"[+] 创建计划任务中：{task_name}")
        create_admin_task(task_name, script_path, python_exec)


if __name__ == "__main__":
    # === 可配置部分 ===
    TASK_NAME = "MySilentAdminTask"
    SCRIPT_PATH = os.path.abspath("your_script.py")  # 改成你的主程序
    PYTHON_EXECUTABLE = "pythonw.exe"

    # === 仅在管理员状态下尝试注册任务 ===
    ensure_admin_task_if_elevated(TASK_NAME, SCRIPT_PATH, PYTHON_EXECUTABLE)

    # 其余普通权限下也可以正常执行主逻辑
    print("[✓] 程序正常启动（无论是否为管理员权限）")
