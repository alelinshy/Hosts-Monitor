#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Hosts Monitor 启动脚本

本脚本是 Hosts Monitor 应用程序的启动入口点，提供一个方便的方式来运行软件。
用户可以直接通过运行此脚本来启动整个应用程序。

本脚本不包含任何业务逻辑，仅仅导入主程序模块并调用其中的启动函数。
所有的初始化、UI显示和应用逻辑都由主程序模块处理。

使用方法:
    直接运行脚本:
    $ python run.py
"""

import os
import sys
import shutil
import locale
from pathlib import Path

# 设置控制台输出编码为UTF-8，避免中文乱码
if sys.platform.startswith('win'):
    # Windows平台特殊处理 - 使用chcp命令设置控制台代码页
    try:
        os.system("chcp 65001 > nul")  # 设置控制台代码页为UTF-8
    except Exception as e:
        print(f"设置控制台编码失败: {str(e)}，但程序将继续运行")

# 打印当前工作目录，帮助调试路径问题
print(f"当前工作目录: {os.getcwd()}")
script_dir = os.path.dirname(os.path.abspath(__file__))
print(f"脚本目录: {script_dir}")

# 设置工作目录为项目根目录
# 这确保了相对路径引用的一致性，无论从哪里启动应用
try:
    os.chdir(script_dir)
    print(f"工作目录已设置为: {os.getcwd()}")
except Exception as e:
    print(f"设置工作目录失败: {str(e)}")
    sys.exit(1)

# 添加项目根目录到Python路径，确保imports可以正常工作
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)
    print(f"已将 {script_dir} 添加到Python路径")

# 导入主模块
try:
    from hosts_monitor import main
    print("成功导入主模块")
except ImportError as e:
    print(f"导入主模块失败: {str(e)}")
    print(f"Python路径: {sys.path}")
    sys.exit(1)

if __name__ == '__main__':
    # 首次运行时，将打包内嵌的 icon.ico 解压到当前工作目录
    if getattr(sys, 'frozen', False):
        _meipass = getattr(sys, '_MEIPASS', None)
        if _meipass:
            src_icon = os.path.join(_meipass, 'resources', 'icon.ico')
            dst_icon = os.path.join(os.getcwd(), 'icon.ico')
            try:
                if os.path.isfile(src_icon) and not os.path.exists(dst_icon):
                    shutil.copy(src_icon, dst_icon)
            except Exception:
                pass
    try:
        # 启动应用程序
        print("正在启动应用程序...")
        sys.exit(main.main())
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        sys.exit(0)
    except ModuleNotFoundError as e:
        print(f"启动失败: 找不到必要的模块 - {str(e)}")
        print("请确保已安装所有依赖项。可以运行: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"启动失败: {str(e)}")
        print(f"错误类型: {type(e).__name__}")
        import traceback
        print("\n详细错误信息:")
        traceback.print_exc()
        sys.exit(1)
