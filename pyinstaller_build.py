#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PyInstaller 打包脚本

本脚本用于将 Hosts Monitor 应用打包成 Windows 可执行文件(.exe)
使用 PyInstaller 进行打包，并自动配置相关打包选项

使用方法:
    python pyinstaller_build.py
"""

import os
import sys
import shutil
from pathlib import Path

# 尝试导入PyInstaller
try:
    from PyInstaller.__main__ import run
except ImportError:
    print("错误: 未安装PyInstaller。请先运行 'pip install pyinstaller' 安装。")
    sys.exit(1)

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 主脚本路径
MAIN_SCRIPT = os.path.join(PROJECT_ROOT, 'run.py')

# 资源路径
ICON_PATH = os.path.join(PROJECT_ROOT, 'resources', 'icon.ico')

# 打包命令选项
pyinstaller_args = [
    '--name=Hosts_Monitor',  # 指定生成的exe文件名
    '--windowed',            # 使用窗口模式 (不显示控制台)
    f'--icon={ICON_PATH}',   # 指定应用图标
    '--noconfirm',           # 不询问确认，直接覆盖输出目录
    '--clean',               # 在构建之前清理PyInstaller缓存
    '--onefile',             # 生成单个可执行文件
    '--add-data=resources/icon.ico;resources/',  # 添加图标资源文件
    MAIN_SCRIPT              # 主脚本
]

def main():
    """执行PyInstaller打包命令"""
    print("开始打包 Hosts Monitor 应用...")
    
    # 检查图标文件是否存在
    if not os.path.isfile(ICON_PATH):
        print(f"警告: 图标文件不存在 ({ICON_PATH})，将使用默认图标")
    
    # 执行PyInstaller打包命令
    print(f"使用参数: {' '.join(pyinstaller_args)}")
    run(pyinstaller_args)
    
    print("打包完成！")
    print(f"可执行文件位于: {os.path.join(PROJECT_ROOT, 'dist', 'Hosts_Monitor.exe')}")

if __name__ == "__main__":
    main()
