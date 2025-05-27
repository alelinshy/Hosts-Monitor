#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
打包脚本
- 使用PyInstaller打包应用程序
"""

import shutil
import subprocess
import sys
from pathlib import Path


def main():
    """主函数"""
    print("开始构建 Hosts Monitor...")
    
    # 获取当前目录
    current_dir = Path(__file__).parent.absolute()
    
    # 输出目录
    dist_dir = current_dir / "dist"
    build_dir = current_dir / "build"
    
    # 清理旧的构建文件
    if dist_dir.exists():
        print(f"清理旧的构建目录: {dist_dir}")
        shutil.rmtree(dist_dir)
    
    if build_dir.exists():
        print(f"清理旧的构建目录: {build_dir}")
        shutil.rmtree(build_dir)
    
    # 图标路径
    icon_path = current_dir / "resources" / "icon.ico"
    if not icon_path.exists():
        print(f"错误: 未找到图标文件 {icon_path}")
        return 1
    
    # 构建命令
    pyinstaller_args = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--name", "Hosts Monitor",
        "--icon", str(icon_path),
        "--add-data", f"{icon_path};resources",
        "--onefile",  # 单文件模式
        "--windowed",  # 无控制台窗口
        "run.py"
    ]
    
    # 执行PyInstaller
    print("正在执行 PyInstaller...")
    process = subprocess.run(pyinstaller_args)
    
    if process.returncode != 0:
        print("构建失败!")
        return process.returncode
    
    print("构建成功!")
    print(f"可执行文件位于: {dist_dir}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
