# -*- coding: utf-8 -*-
"""
UI控制器模块
- 处理UI与业务逻辑的交互事件
"""

import atexit

from . import logger
from .config import config
from .contrast import contrast_module
from .monitor import monitor
from .repair import repair_module
from .ui import HostsMonitorUI


class Controller:
    """控制器类"""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Controller, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.ui = None
        self.app = None
        self._initialized = True
    
    def init_ui(self, app) -> None:
        """初始化UI"""
        self.app = app
        self.ui = HostsMonitorUI()
        
        # 设置日志UI回调
        logger.set_ui_callback(self.log_to_ui)
        
        # 连接UI初始化完成信号
        self.ui.ui_initialized.connect(self.on_ui_initialized)
        
        # 显示UI（根据配置决定是否最小化）
        if self._should_minimize_on_startup():
            logger.info("程序已启动并自动最小化到系统托盘")
        else:
            self.ui.show()
            logger.info("程序已启动")
    
    def _should_minimize_on_startup(self) -> bool:
        """是否在启动时最小化到托盘"""
        # 当设置为开机自启动时，默认最小化到托盘
        return config.get("general", "auto_start", False)
    
    def setup_connections(self) -> None:
        """设置模块之间的连接"""
        # 监控模块 -> 对比模块
        monitor.set_contrast_callback(contrast_module.start)
        
        # 对比模块 -> 修复模块
        contrast_module.set_repair_callback(repair_module.start)
    
    def log_to_ui(self, message: str) -> None:
        """将日志消息更新到UI"""
        if self.ui:
            self.ui.log_updated.emit(message)
            
    def on_ui_initialized(self) -> None:
        """UI初始化完成后的处理"""
        # 设置模块连接
        self.setup_connections()
        
        # 启动监控
        self.start_monitor()
        
        logger.info("UI初始化完成，已启动监控服务")
    
    def start_monitor(self) -> None:
        """启动监控服务"""
        # 先检查监控是否已在运行
        if hasattr(monitor, 'monitor_thread') and monitor.monitor_thread and monitor.monitor_thread.is_alive():
            logger.info("监控服务已在运行中")
        else:
            logger.info("正在启动监控服务...")
            monitor.start()
            
        # 注册程序退出时的清理函数（如果尚未注册）
        try:
            atexit.unregister(self.stop_monitor)  # 先取消已有的注册，防止重复
        except:
            pass
        atexit.register(self.stop_monitor)
    
    def stop_monitor(self) -> None:
        """停止监控服务"""
        logger.info("正在停止监控服务...")
        try:
            monitor.stop()
            logger.info("监控服务已停止")
        except Exception as e:
            logger.error(f"停止监控服务时发生错误: {str(e)}")
            
        # 如果退出函数已注册，则取消注册，防止多次调用
        try:
            atexit.unregister(self.stop_monitor)
        except:
            pass
    
    def run(self) -> int:
        """运行主程序"""
        try:
            # 监控已经在UI初始化完成后启动，这里不需要重复启动
            
            # 运行UI事件循环
            if self.app and self.ui:
                return self.app.exec()
            
            return 0
            
        except Exception as e:
            logger.error(f"程序运行时发生错误: {str(e)}")
            return 1
        finally:
            # 停止监控
            self.stop_monitor()
            
            logger.info("程序已退出")


# 全局控制器对象
controller = Controller()
