# -*- coding: utf-8 -*-
"""
Hosts Monitor 主程序包
- 用于监控和修复hosts文件
"""

# 版本信息
from .version import VERSION, APP_NAME

# 导出主要模块
__version__ = VERSION
__app_name__ = APP_NAME

# 导出必要的模块，使它们可以通过包直接访问
from .logger import logger, set_ui_callback
from .config import config
from .monitor import monitor
from .contrast import contrast_module
from .repair import repair_module