#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
启动脚本
"""

import sys


def safe_import():
    """安全导入主函数，处理可能的导入错误"""
    try:
        from hosts_monitor.main import main

        return main
    except ImportError as e:
        # 捕获特定的导入错误
        error_str = str(e)
        if "cannot import name" in error_str and (
            "TASK_NAME" in error_str
            or "create_scheduled_task" in error_str
            or "check_task_exists" in error_str
            or "win32com" in error_str
        ):
            # 显示更友好的错误信息
            print("错误：程序依赖项已更改，正在尝试修复...")
            try:
                # 尝试修复导入
                import importlib
                from hosts_monitor.utils import is_admin, run_as_admin, get_app_paths

                # 确保utils模块已经重新加载，防止缓存的旧版本
                utils_module = sys.modules.get("hosts_monitor.utils")
                if utils_module:
                    importlib.reload(utils_module)

                # 现在尝试导入main
                from hosts_monitor.main import main

                print("修复成功！程序将继续启动。")
                return main
            except Exception as fix_error:
                print(f"修复失败: {str(fix_error)}")
                print("请尝试重新启动程序。如果问题仍然存在，请重新安装应用程序。")
                input("按回车键退出...")
                return lambda: 1  # 返回一个简单函数，退出码为1
        else:
            # 其他导入错误，打印详细信息
            print(f"程序启动失败: {str(e)}")
            print("请尝试重新启动程序。如果问题仍然存在，请重新安装应用程序。")
            input("按回车键退出...")
            return lambda: 1  # 返回一个简单函数，退出码为1


if __name__ == "__main__":
    main_function = safe_import()
    sys.exit(main_function())
