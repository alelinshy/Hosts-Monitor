#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Hosts Monitor 包

此包包含 Hosts Monitor 应用程序的所有模块。
Hosts Monitor 是一个用于监控和维护 hosts 文件的工具，
可以确保指定的 DNS 规则始终保持在 hosts 文件中。

主要模块:
- main: 主程序入口点
- ui: 用户界面
- controller: UI 控制器
- monitor: 文件监控
- repair: 规则修复
- contrast: 规则对比
- logger: 日志处理
- config: 配置管理
- version: 版本信息

使用示例:
    # 通过 run.py 启动整个应用
    $ python run.py
    
    # 或作为包导入使用部分功能
    from hosts_monitor.config import get_rules
    rules = get_rules()
"""

# 版本信息
from .version import VERSION, get_version, get_full_version_info

# 为方便导入，直接暴露一些常用函数
__version__ = VERSION