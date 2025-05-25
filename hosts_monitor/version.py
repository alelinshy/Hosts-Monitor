#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
版本信息模块

本模块提供 Hosts Monitor 软件的版本信息，作为全局常量供程序中所有
需要显示版本号的地方引用。这样可以确保在整个应用程序中版本号的一致性，
并且在发布新版本时只需在此处更新一处即可。

使用语义化版本格式(Semantic Versioning): 主版本号.次版本号.修订号
- 主版本号：当做了不兼容的 API 修改时递增
- 次版本号：当做了向下兼容的功能性新增时递增
- 修订号：当做了向下兼容的问题修正时递增

使用示例:
    from hosts_monitor.version import VERSION
    print(f"Hosts Monitor 版本: {VERSION}")

    # 或使用获取版本信息的函数
    from hosts_monitor.version import get_version
    print(f"当前版本: {get_version()}")
"""

# 版本号常量 - 使用语义化版本格式
__version__ = "1.0.0"
VERSION = __version__

# 构建日期 - 可选，记录此版本的构建/发布日期
BUILD_DATE = "2025-05-22"


def get_version():
    """
    获取软件当前版本号
    
    返回:
        str: 表示当前软件版本的字符串
    """
    return __version__


def get_full_version_info():
    """
    获取完整的版本信息，包括版本号和构建日期
    
    返回:
        str: 包含版本号和构建日期的格式化字符串
    """
    return f"{__version__} (构建于 {BUILD_DATE})"


# 如果直接运行此文件，则显示版本信息
if __name__ == "__main__":
    print(f"Hosts Monitor 版本: {get_full_version_info()}")
