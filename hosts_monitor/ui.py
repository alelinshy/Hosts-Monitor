# -*- coding: utf-8 -*-
"""
UI模块
- 使用PyQt6
- 软件界面分为上中下三栏
"""

import os
import sys
import ctypes
import subprocess
from typing import Optional, Tuple
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QCheckBox, QLineEdit, 
                            QTextEdit, QLabel, QMessageBox, QSystemTrayIcon, 
                            QMenu, QFileDialog)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QAction, QCloseEvent, QFont, QIntValidator

from . import logger
from .version import VERSION, APP_NAME
from .config import config
from .monitor import monitor
from .contrast import contrast_module
from .repair import repair_module


class HostsMonitorUI(QMainWindow):
    """Hosts Monitor UI类"""
    
    # 信号定义
    log_updated = pyqtSignal(str)
    admin_status_changed = pyqtSignal(bool)
    config_saved = pyqtSignal()
    monitor_status_changed = pyqtSignal(bool)
    ui_initialized = pyqtSignal()  # 新增UI初始化完成信号
    
    def __init__(self):
        super().__init__()
        
        # 窗口标题和图标
        self.setWindowTitle(f"{APP_NAME} v{VERSION}")
        self.icon_path = self._get_icon_path()
        self.setWindowIcon(QIcon(self.icon_path))
        
        # 窗口大小
        self.resize(800, 600)
        
        # 监控状态
        self.is_monitoring = False
        
        # 初始化监控模块的去抖动时间
        delay_time = config.get("general", "delay_time", 5)
        debounce_time = delay_time / 1000.0
        monitor.set_debounce_time(debounce_time)
        
        # 系统托盘
        self.setup_tray_icon()
        
        # 初始化UI
        self.setup_ui()
        
        # 连接信号
        self.connect_signals()
        
        # 检查管理员权限
        QTimer.singleShot(500, self.check_admin_privileges)
        
        # 检查监控状态
        QTimer.singleShot(1000, self.check_monitor_status)
        
        # 发送UI初始化完成信号
        QTimer.singleShot(100, self.ui_initialized.emit)
    
    def _get_icon_path(self) -> str:
        """获取图标路径，如果是打包环境且本地没有图标文件则释放"""
        # 检查是否是打包环境
        is_frozen = getattr(sys, 'frozen', False)
        
        if is_frozen:
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 图标的相对路径
        icon_relative_path = os.path.join("resources", "icon.ico")
        icon_path = os.path.join(base_dir, icon_relative_path)
        
        # 检查图标文件是否存在
        if not os.path.exists(icon_path) and is_frozen:
            try:
                # 创建resources目录
                os.makedirs(os.path.dirname(icon_path), exist_ok=True)
                
                # 从打包资源中提取图标
                internal_icon_path = os.path.join(sys._MEIPASS, icon_relative_path)
                if os.path.exists(internal_icon_path):
                    with open(internal_icon_path, 'rb') as src, open(icon_path, 'wb') as dst:
                        dst.write(src.read())
                    logger.info(f"已释放图标文件到: {icon_path}")
            except Exception as e:
                logger.error(f"释放图标文件时发生错误: {str(e)}")
        
        return icon_path
    
    def setup_tray_icon(self) -> None:
        """设置系统托盘图标"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(self.icon_path))
        self.tray_icon.setToolTip(f"{APP_NAME} v{VERSION}")
        
        # 托盘菜单
        tray_menu = QMenu()
        
        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self.show_main_window)
        tray_menu.addAction(show_action)
        
        manual_check_action = QAction("手动对比", self)
        manual_check_action.triggered.connect(self.manual_contrast)
        tray_menu.addAction(manual_check_action)
        
        tray_menu.addSeparator()
        
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        
        # 显示托盘图标
        self.tray_icon.show()
    
    def show_main_window(self) -> None:
        """显示主窗口"""
        self.show()
        self.raise_()
        self.activateWindow()
    
    def tray_icon_activated(self, reason):
        """托盘图标被激活"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_main_window()
    
    def setup_ui(self) -> None:
        """设置UI界面"""
        # 中央部件
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 上栏
        top_layout = QHBoxLayout()
        
        self.admin_btn = QPushButton("以管理员权限运行")
        self.admin_btn.clicked.connect(self.run_as_admin)
        top_layout.addWidget(self.admin_btn)
        
        self.autostart_cb = QCheckBox("开机自启")
        self.autostart_cb.setChecked(config.get("general", "auto_start", False))
        self.autostart_cb.stateChanged.connect(self.toggle_autostart)
        top_layout.addWidget(self.autostart_cb)
        
        self.open_hosts_btn = QPushButton("打开hosts文件")
        self.open_hosts_btn.clicked.connect(self.open_hosts_file)
        top_layout.addWidget(self.open_hosts_btn)
        
        # 监控状态标签
        self.monitor_status_label = QLabel("监控状态: 未知")
        top_layout.addWidget(self.monitor_status_label)
        
        self.manual_check_btn = QPushButton("手动对比")
        self.manual_check_btn.clicked.connect(self.manual_contrast)
        top_layout.addWidget(self.manual_check_btn)
        
        top_layout.addWidget(QLabel("延迟时间(ms):"))
        
        self.delay_edit = QLineEdit()
        self.delay_edit.setFixedWidth(80)
        self.delay_edit.setText(str(config.get("general", "delay_time", 5)))        
        self.delay_edit.setValidator(QIntValidator(1, 10000))
        top_layout.addWidget(self.delay_edit)
        
        self.apply_delay_btn = QPushButton("应用")
        self.apply_delay_btn.setToolTip("应用延迟时间设置")
        self.apply_delay_btn.clicked.connect(self.apply_delay_time)
        top_layout.addWidget(self.apply_delay_btn)
        
        top_layout.addStretch(1)
        
        main_layout.addLayout(top_layout)
        
        # 中栏 - hosts数据
        middle_layout = QVBoxLayout()
        
        middle_layout.addWidget(QLabel("hosts数据:"))
        
        self.hosts_edit = QTextEdit()
        self.hosts_edit.setPlaceholderText("在这里输入需要监控的hosts数据...")
        self.hosts_edit.setFont(QFont("Courier New", 10))
        self.hosts_edit.setText(config.get_hosts_data())
        middle_layout.addWidget(self.hosts_edit)
        
        save_layout = QHBoxLayout()
        save_layout.addStretch(1)
        
        self.save_btn = QPushButton("保存配置")
        self.save_btn.clicked.connect(self.save_config)
        save_layout.addWidget(self.save_btn)
        
        middle_layout.addLayout(save_layout)
        
        main_layout.addLayout(middle_layout)
        
        # 下栏 - 日志
        bottom_layout = QVBoxLayout()
        
        bottom_layout.addWidget(QLabel("日志:"))
        
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Courier New", 10))
        self.log_view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        bottom_layout.addWidget(self.log_view)
        
        main_layout.addLayout(bottom_layout)
        
        # 分配布局比例
        main_layout.setStretch(0, 0)  # 上栏固定高度
        main_layout.setStretch(1, 2)  # 中栏
        main_layout.setStretch(2, 1)  # 下栏
    
    def connect_signals(self) -> None:
        """连接信号"""
        # 日志更新信号
        self.log_updated.connect(self.update_log_view)
        
        # 管理员权限状态变更信号
        self.admin_status_changed.connect(self.update_admin_button)
        
        # 配置保存信号
        self.config_saved.connect(self.on_config_saved)
        
        # 监控状态变更信号
        self.monitor_status_changed.connect(self.update_monitor_button)
    
    def check_admin_privileges(self) -> None:
        """检查管理员权限"""
        is_admin = self.is_admin()
        self.admin_status_changed.emit(is_admin)
    
    def is_admin(self) -> bool:
        """检查是否具有管理员权限"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False
    def update_admin_button(self, is_admin: bool) -> None:
        """更新管理员按钮状态"""
        if is_admin:
            self.admin_btn.setText("已具备管理员权限")
            self.admin_btn.setEnabled(False)
            logger.info("当前程序已具备管理员权限")
        else:
            self.admin_btn.setText("以管理员权限运行")
            self.admin_btn.setEnabled(True)
            logger.info("当前程序没有管理员权限")
            
    def run_as_admin(self) -> None:
        """以管理员权限运行程序"""
        if self.is_admin():
            return
        
        try:
            # 保存当前配置
            self.save_config()
            
            # 设置下次以管理员权限运行
            config.set("general", "run_as_admin", True)
            config.save_config()
            
            # 获取当前程序路径
            if getattr(sys, 'frozen', False):
                app_path = sys.executable
            else:
                # 对于脚本，确保使用Python解释器启动
                python_exe = sys.executable
                app_path = python_exe
                app_args = f'"{os.path.abspath(sys.argv[0])}" --already-trying-uac'
            
            # 对于打包版本，直接使用参数
            if getattr(sys, 'frozen', False):
                # 创建命令行参数，添加一个标记防止死循环
                if "--already-trying-uac" not in sys.argv:
                    app_args = "--already-trying-uac"
                else:
                    app_args = ""
            
            # 关闭系统托盘图标
            self.tray_icon.hide()
            
            logger.info(f"尝试以管理员权限运行: {app_path} {app_args}")
            
            # 以管理员权限重启
            # 确保工作目录正确设置
            work_dir = os.path.dirname(os.path.abspath(app_path))
            
            # 使用ShellExecuteW启动
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", app_path, app_args, work_dir, 1
            )
            
            # 如果ShellExecuteW返回值大于32表示成功启动
            if ret > 32:
                logger.info("管理员权限的新实例已启动，当前实例即将退出")
                # 使用延时确保新进程有时间启动
                QMessageBox.information(self, "提示", "程序正在以管理员权限重新启动...")
                QTimer.singleShot(1000, QApplication.quit)
            else:
                error_msg = "未知错误"
                if ret == 0:
                    error_msg = "系统内存或资源不足"
                elif ret == 2:
                    error_msg = "指定的文件未找到"
                elif ret == 3:
                    error_msg = "指定的路径未找到"
                elif ret == 5:
                    error_msg = "拒绝访问"
                elif ret == 8:
                    error_msg = "内存不足"
                elif ret == 11:
                    error_msg = "无效的格式"
                elif ret == 26:
                    error_msg = "共享冲突"
                elif ret == 27:
                    error_msg = "文件名不完整或无效"
                elif ret == 28:
                    error_msg = "打印机脱机"
                elif ret == 29:
                    error_msg = "已超时"
                elif ret == 30:
                    error_msg = "文件已在使用中"
                elif ret == 31:
                    error_msg = "没有关联的应用程序可执行此文件"
                elif ret == 32:
                    error_msg = "操作已取消"
                
                logger.error(f"以管理员权限运行失败，返回值: {ret}，错误: {error_msg}")
                logger.error(f"程序路径: {app_path}")
                logger.error(f"参数: {app_args}")
                logger.error(f"工作目录: {work_dir}")
                
                QMessageBox.critical(self, "错误", f"以管理员权限运行失败: {error_msg} (代码: {ret})")
        except Exception as e:
            logger.error(f"以管理员权限运行失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"以管理员权限运行失败: {str(e)}")
    
    def toggle_autostart(self, state: int) -> None:
        """切换开机自启状态"""
        try:
            is_checked = state == Qt.CheckState.Checked.value
            
            # 获取程序路径
            if getattr(sys, 'frozen', False):
                app_path = f'"{sys.executable}"'
            else:
                app_path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
            
            # 注册表路径
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
            
            # 导入winreg模块
            import winreg
            
            # 打开注册表项
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0, 
                winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
            )
            
            if is_checked:
                # 设置开机自启
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, app_path)
                logger.info("已设置开机自启")
            else:
                # 删除开机自启
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
                logger.info("已取消开机自启")
            
            # 更新配置
            config.set("general", "auto_start", is_checked)
            config.save_config()
            
        except Exception as e:
            logger.error(f"设置开机自启失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"设置开机自启失败: {str(e)}")
            
            # 回滚复选框状态
            self.autostart_cb.setChecked(not is_checked)
    
    def open_hosts_file(self) -> None:
        """打开hosts文件"""
        try:
            # 获取hosts文件路径
            hosts_path = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 
                                    'System32', 'drivers', 'etc', 'hosts')
            
            # 使用记事本打开
            if os.path.exists(hosts_path):
                os.startfile(hosts_path)
                logger.info(f"已打开hosts文件: {hosts_path}")
            else:
                logger.error(f"hosts文件不存在: {hosts_path}")
                QMessageBox.critical(self, "错误", f"hosts文件不存在: {hosts_path}")
        except Exception as e:
            logger.error(f"打开hosts文件失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"打开hosts文件失败: {str(e)}")
    
    def save_config(self) -> None:
        """保存配置"""
        try:
            # 获取延迟时间
            try:
                delay_text = self.delay_edit.text().strip()
                if not delay_text:
                    delay_time = 5  # 默认值
                    logger.warning("延迟时间为空，使用默认值5毫秒")
                else:
                    delay_time = int(delay_text)
                    if delay_time < 1:
                        delay_time = 1
                        logger.warning("延迟时间小于1毫秒，已调整为1毫秒")
                    elif delay_time > 10000:
                        delay_time = 10000
                        logger.warning("延迟时间大于10000毫秒，已调整为10000毫秒")
            except ValueError as e:
                logger.error(f"延迟时间格式错误: {str(e)}，使用默认值5毫秒")
                delay_time = 5
                QMessageBox.warning(self, "警告", f"延迟时间格式错误，已使用默认值5毫秒")
            
            # 更新配置
            config.set("general", "delay_time", delay_time)
            
            # 更新hosts数据
            hosts_data = self.hosts_edit.toPlainText()
            config.set_hosts_data(hosts_data)
            
            # 更新监控模块的去抖动时间（毫秒转秒）
            debounce_time = delay_time / 1000.0
            monitor.set_debounce_time(debounce_time)
            
            # 保存配置
            if config.save_config():
                logger.info("配置已保存")
                self.config_saved.emit()
            else:
                logger.error("保存配置失败")
                QMessageBox.critical(self, "错误", "保存配置失败，请查看日志")
        except Exception as e:
            logger.error(f"保存配置失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"保存配置失败: {str(e)}")
    
    def on_config_saved(self) -> None:
        """配置保存后的处理"""
        # 配置更改后直接触发对比检查
        logger.info("配置已更改，立即触发对比检查")
        contrast_module.start()
    
    def check_monitor_status(self) -> None:
        """检查监控状态"""
        # 通过检查线程是否活跃来判断监控状态
        if hasattr(monitor, 'monitor_thread') and monitor.monitor_thread and monitor.monitor_thread.is_alive():
            if not self.is_monitoring:  # 状态变化时才记录
                logger.info("监控状态检查: 监控正在运行")
            self.is_monitoring = True
        else:
            if self.is_monitoring:  # 状态变化时才记录
                logger.info("监控状态检查: 监控已停止")
            self.is_monitoring = False
        
        # 更新UI显示
        self.monitor_status_changed.emit(self.is_monitoring)
        
        # 每5秒检查一次监控状态
        QTimer.singleShot(5000, self.check_monitor_status)
    
    def update_monitor_button(self, is_monitoring: bool) -> None:
        """更新监控状态显示"""
        if is_monitoring:
            self.monitor_status_label.setText("监控状态: 运行中")
            self.monitor_status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.monitor_status_label.setText("监控状态: 已停止")
            self.monitor_status_label.setStyleSheet("color: red;")
    
    def manual_contrast(self) -> None:
        """手动执行对比"""
        logger.info("手动触发对比检查")
        contrast_module.start()
    
    def apply_delay_time(self) -> None:
        """应用延迟时间设置"""
        try:
            # 获取延迟时间
            delay_time = int(self.delay_edit.text())
            if delay_time < 1 or delay_time > 10000:
                raise ValueError("延迟时间必须在1-10000毫秒范围内")
                
            # 更新配置
            config.set("general", "delay_time", delay_time)
            
            # 保存配置
            if config.save_config():
                logger.info(f"延迟时间已更新为 {delay_time} 毫秒")
                
                # 更新监控模块的去抖动时间（毫秒转秒）
                debounce_time = delay_time / 1000.0
                monitor.set_debounce_time(debounce_time)
                
                # 触发一次对比检查
                contrast_module.start()
            else:
                logger.error("保存延迟时间设置失败")
                
        except ValueError as e:
            logger.error(f"应用延迟时间失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"应用延迟时间失败: {str(e)}")
        except Exception as e:
            logger.error(f"应用延迟时间时发生错误: {str(e)}")
            QMessageBox.critical(self, "错误", f"应用延迟时间时发生错误: {str(e)}")
    
    def update_log_view(self, message: str) -> None:
        """更新日志视图"""
        self.log_view.append(message)
        # 滚动到底部
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def closeEvent(self, event: QCloseEvent) -> None:
        """关闭事件处理"""
        if config.get("general", "minimize_to_tray", True):
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                APP_NAME,
                "程序已最小化到系统托盘",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
        else:
            self.quit_application()
    
    def quit_application(self) -> None:
        """退出应用程序"""
        reply = QMessageBox.question(
            self, 
            "退出确认", 
            "确定要退出 Hosts Monitor 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 控制器负责停止监控，这里只隐藏托盘图标
            self.tray_icon.hide()
            QApplication.quit()


# 移除自定义验证器类，使用QIntValidator替代
