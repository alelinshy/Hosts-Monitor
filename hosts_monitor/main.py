#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
主程序入口模块

本模块是 Hosts Monitor 应用程序的入口点，负责启动整个应用程序。
主要职责包括:
1. 创建应用上下文（QApplication对象）
2. 初始化日志系统
3. 实例化UI控制器
4. 启动事件循环
5. 在应用退出时进行清理

使用示例:
    # 直接运行
    python main.py
    
    # 或导入后运行
    from main import main
    main()
"""

import os
import sys
from pathlib import Path
import logging

# 获取适合的路径，但不修改当前工作目录（由运行入口负责）
if getattr(sys, 'frozen', False):
    # PyInstaller打包后的环境
    base_path = os.path.dirname(sys.executable)
else:
    # 开发环境 - 使用项目根目录
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 导入自定义模块
from hosts_monitor.logger import logger
from hosts_monitor.controller import MainController
from hosts_monitor.version import VERSION, get_version
from hosts_monitor import config


def main():
    """
    主函数，实现程序启动逻辑
    """
    # 记录应用启动日志
    logger.info(f"Hosts Monitor 正在启动，版本: {get_version()}")
    
    try:
        # 确保配置文件已加载
        config.load_config()
        
        # 创建控制器实例，并启动应用
        controller = MainController()
        
        # 开始应用（显示UI、启动监控、进入事件循环）
        controller.start()
        
        # 注意: controller.start() 包含了 app.exec() 并不会返回，
        # 下面的代码只有在特殊情况下才会执行（如被其他函数导入调用）
        
    except Exception as e:
        # 捕获未处理异常，记录日志
        logger.exception(f"应用启动失败: {str(e)}")
        sys.exit(1)
    
    # 正常退出（通常不会执行到这里，因为 app.exec() 在退出时已调用 sys.exit()）
    logger.info("应用已退出")
    return 0


# 注意：由于使用了相对导入，此模块不能直接作为主程序运行
# 必须通过 run.py 或其他方式导入后调用
if __name__ == "__main__":
    print("此模块不能直接运行，请通过 run.py 启动应用")
    sys.exit(1)
