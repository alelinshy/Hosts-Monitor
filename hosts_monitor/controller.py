#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
控制器模块

本模块充当 MVC 模式中的控制器，负责处理用户界面与后台逻辑模块之间的交互。
主要职责包括:
1. 初始化 UI 并将数据填充到界面元素
2. 连接 UI 控件的事件到相应的处理函数
3. 处理用户操作，更新配置并触发相应的后台处理
4. 将后台模块的日志和状态更新反映到 UI 上

使用示例:
    from hosts_monitor.controller import MainController
    
    # 创建控制器并启动应用
    controller = MainController()
    controller.start()
"""

import os
import sys
import time
import threading
import logging
import ctypes
import winreg
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from functools import partial

# PyQt6 导入
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, Qt, QEvent
from PyQt6.QtWidgets import QApplication, QMessageBox, QTableWidgetItem, QCheckBox, QFileDialog, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction

# 导入项目模块
from hosts_monitor.ui import HostsMonitorUI, RuleEditDialog
from hosts_monitor.config import (
    get_all_rules, get_enabled_rules, get_rule, 
    add_rule, update_rule, remove_rule,
    get_setting, update_setting, get_default_settings,
    CONFIG_LOCK, CONFIG_DATA, save_config
)
from hosts_monitor.monitor import (
    start_monitoring, stop_monitoring, trigger_check, 
    is_monitoring_active
)
from hosts_monitor.contrast import HOSTS_PATH
from hosts_monitor.logger import logger
from hosts_monitor.version import VERSION


class LogHandler(logging.Handler):
    """
    日志处理器，用于将后台日志信息同步到 UI
    """
    
    def __init__(self, log_signal):
        super().__init__()
        self.log_signal = log_signal
        self.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    
    def emit(self, record):
        """
        处理日志记录，发送信号到 UI
        """
        try:
            msg = self.format(record)
            level = record.levelname.lower()
            # 根据日志级别设置不同的颜色
            color = {
                'debug': '#888888',
                'info': '#00FF00',
                'warning': '#FFA500',
                'error': '#FF0000',
                'critical': '#FF00FF'
            }.get(level, '#FFFFFF')
            
            # 发送带格式的消息到 UI
            formatted_msg = f'<span style="color:{color}">{msg}</span>'
            self.log_signal.emit(level, formatted_msg)
        except Exception:
            self.handleError(record)


class MainController(QObject):
    """
    主控制器类，负责 UI 与后台逻辑的交互
    """
    # 定义信号，用于线程安全地更新 UI
    log_signal = pyqtSignal(str, str)  # 参数: 日志级别, 日志消息
    status_signal = pyqtSignal(str)    # 参数: 状态消息
    
    def __init__(self, app=None):
        """
        初始化控制器
        
        参数:
            app: QApplication 实例，如果为 None 则创建一个新的
        """
        super().__init__()
        self.app = app or QApplication(sys.argv)
        self.ui = HostsMonitorUI()
        self.setup_logging()
        self.init_ui()
        self.connect_signals()
        # 初始化但不启动计时器 - 已不再需要
        self._last_status = None
        
    def setup_logging(self):
        """
        设置日志处理，将后台日志同步到 UI
        """
        # 连接日志信号到 UI 更新函数
        self.log_signal.connect(self.update_log_ui)
        
        # 创建并添加自定义日志处理器
        log_handler = LogHandler(self.log_signal)
        log_handler.setLevel(logging.INFO)
        logger.addHandler(log_handler)
        
        logger.info("日志系统初始化完成")
    def init_ui(self):
        """
        初始化 UI，加载配置数据到界面
        """
        # 设置应用图标
        self.set_application_icon()
        
        # 设置版本信息
        self.ui.version_label.setText(f"版本: {VERSION}")
        
        # 加载规则数据
        self.load_rules_to_ui()
        
        # 加载设置项
        self.load_settings_to_ui()
        
        # 清除测试数据
        self.ui.log_text.clear()
        self.ui.mappings_table.setRowCount(0)
          # 检查管理员权限，如果已经具备则禁用提权按钮
        if is_admin():
            self.ui.admin_button.setEnabled(False)
            self.ui.admin_button.setText("已获管理员权限")
            self.ui.admin_button.setToolTip("程序已经以管理员权限运行")
            logger.info("检测到管理员权限，提权按钮已禁用")
        
        logger.info("UI 初始化完成")
    
    def connect_signals(self):
        """
        连接 UI 信号到相应的处理函数
        """
        # 规则管理信号
        self.ui.add_rule_button.clicked.connect(self.on_add_rule)
        
        # 控制按钮信号
        self.ui.admin_button.clicked.connect(self.on_request_admin)
        self.ui.open_hosts_button.clicked.connect(self.on_open_hosts_file)
        
        # 设置项信号
        self.ui.auto_start_checkbox.stateChanged.connect(self.on_toggle_auto_start)
        self.ui.apply_delay_button.clicked.connect(self.on_apply_delay)
        
        logger.info("事件处理绑定完成")
    
    def start(self):
        """
        启动应用程序
        """
        # 启动文件监控
        self.start_monitoring()
        
        # 显示主窗口
        self.ui.show()
        
        # 记录应用启动信息
        logger.info(f"Hosts Monitor {VERSION} 已启动")
        
        # 运行应用程序主循环
        sys.exit(self.app.exec())
    
    def start_monitoring(self):
        """
        启动 Hosts 文件监控
        """
        if get_setting('monitor_enabled', True):
            try:
                if start_monitoring():
                    # 启动成功后直接设置状态并记录日志
                    logger.info("Hosts 监控已启动")
                    logger.info("Hosts 文件状态: 监控中")
                    self._last_status = "监控中"
                else:
                    logger.warning("Hosts 监控启动失败")
                    logger.info("Hosts 文件状态: 未监控")
                    self._last_status = "未监控"
            except Exception as e:
                logger.error(f"启动监控时出错: {str(e)}")
                logger.info("Hosts 文件状态: 未监控")
                self._last_status = "未监控"
        else:
            logger.info("Hosts 监控未启用")
            logger.info("Hosts 文件状态: 未监控")
            self._last_status = "未监控"
    
    def load_rules_to_ui(self):
        """
        加载规则数据到 UI
        """
        # 清空现有规则
        for i in reversed(range(self.ui.rules_content_layout.count())):
            item = self.ui.rules_content_layout.itemAt(i)
            if item:
                widget = item.widget()
                if widget:
                    widget.setParent(None)
        
        # 清空映射表格
        self.ui.mappings_table.setRowCount(0)
        
        # 加载所有规则
        rules = get_all_rules()
        if not rules:
            logger.info("未找到任何规则")
            return
        
        logger.info(f"加载 {len(rules)} 条规则")
        
        # 添加规则到 UI
        for rule in rules:
            rule_name = rule.get('name', '')
            if rule_name:
                # 创建规则项
                rule_widget = self.ui._create_rule_item_widget(rule_name)
                # 设置启用状态
                checkbox = rule_widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(rule.get('enabled', False))
                    # 连接信号到处理函数，使用 lambda 传递规则名和状态
                    checkbox.stateChanged.connect(
                        lambda state, rn=rule_name: self.on_toggle_rule(state, rn)
                    )
                
                # 添加到布局
                self.ui.rules_content_layout.addWidget(rule_widget)
                
                # 添加映射到表格
                self.add_rule_mappings_to_table(rule)
    
    def add_rule_mappings_to_table(self, rule):
        """
        将规则的映射添加到映射表格
        
        参数:
            rule: 规则数据字典
        """
        rule_name = rule.get('name', '')
        entries = rule.get('entries', [])
        
        for entry in entries:
            ip = entry.get('ip', '')
            domain = entry.get('domain', '')
            
            if ip and domain:
                row = self.ui.mappings_table.rowCount()
                self.ui.mappings_table.insertRow(row)
                self.ui.mappings_table.setItem(row, 0, QTableWidgetItem(ip))
                self.ui.mappings_table.setItem(row, 1, QTableWidgetItem(domain))
                self.ui.mappings_table.setItem(row, 2, QTableWidgetItem(rule_name))
    
    def load_settings_to_ui(self):
        """
        加载设置项到 UI
        """
        # 设置延迟时间
        delay_ms = get_setting('delay_ms', 2000)
        self.ui.delay_input.setText(str(delay_ms))
        
        # 设置开机自启状态
        auto_start = get_setting('auto_start', False)
        self.ui.auto_start_checkbox.setChecked(auto_start)
    
    def update_log_ui(self, level, message):
        """
        更新 UI 日志窗口
        
        参数:
            level: 日志级别
            message: 格式化的日志消息
        """
        # 追加日志消息到日志窗口
        self.ui.log_text.append(message)
        
        # 滚动到底部
        scrollbar = self.ui.log_text.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())
    
    # update_status 方法已移除，不再需要定期检查监控状态
    
    # -------------------- 事件处理函数 -------------------- #
    def on_add_rule(self):
        """
        添加新规则按钮点击处理
        """
        rule_name = self.ui.new_rule_input.text().strip()
        if not rule_name:
            logger.warning("规则名称不能为空")
            self.show_message("提示", "请输入规则名称", QMessageBox.Icon.Warning)
            return
        
        # 打开编辑对话框，获取映射数据
        dlg = RuleEditDialog(rule_name, [], self.ui)
        if dlg.exec():
            mappings = dlg.get_mappings()
            
            # 检查是否有映射
            if not mappings:
                logger.warning("规则至少需要一个映射")
                self.show_message("提示", "规则至少需要一个映射", QMessageBox.Icon.Warning)
                return
            
            # 格式化为配置模块所需的格式
            entries = [{'ip': ip, 'domain': domain} for ip, domain in mappings]
            
            # 添加规则
            if add_rule(rule_name, entries):
                logger.info(f"已添加规则: {rule_name}")
                
                # 清空输入框，并避免触发UI模块的add_rule_item
                self.ui.new_rule_input.clear()
                
                # 重新加载规则到 UI，确保所有规则项的复选框都正确连接信号
                self.load_rules_to_ui()
                  # 在后台线程中触发检查，避免UI卡顿
                thread = threading.Thread(target=self._background_check, daemon=True)
                thread.start()
            else:                
                logger.error(f"添加规则 {rule_name} 失败")
                self.show_message("错误", f"无法添加规则: {rule_name}", QMessageBox.Icon.Critical)
                
    def on_toggle_rule(self, state, rule_name):
        """
        规则启用/禁用切换处理
        
        参数:
            state: 复选框状态
            rule_name: 规则名称
        """
        enabled = state == Qt.CheckState.Checked.value
        status = "启用" if enabled else "禁用"
        
        # 修改规则状态但禁止触发检查和修复，只更新配置
        # 绕过 update_rule 直接更新规则状态，避免触发修复流程
        rule = get_rule(rule_name)
        if rule:
            rule['enabled'] = enabled
            # 直接调用 save_config 保存配置
            from hosts_monitor.config import save_config
            if save_config():
                logger.info(f"已{status}规则: {rule_name}")
            else:
                logger.error(f"{status}规则 {rule_name} 失败")
                
                # 恢复复选框状态
                sender = self.sender()
                if sender and isinstance(sender, QCheckBox):
                    sender.setChecked(not enabled)
        else:
            logger.error(f"找不到规则: {rule_name}")
            
            # 恢复复选框状态
            sender = self.sender()
            if sender and isinstance(sender, QCheckBox):
                sender.setChecked(not enabled)
    def _background_check(self):
        """
        后台线程触发 hosts 检查，避免阻塞 UI。
        完全在后台执行，无论监控线程是否活跃
        """
        try:
            from hosts_monitor.monitor import is_monitoring_active, _event_queue, check_hosts

            # 如果监控线程活跃，使用队列
            if is_monitoring_active():
                logger.info("将检查请求加入监控队列")
                _event_queue.put("check")
            else:
                # 即使监控未运行，也在后台线程直接执行检查
                logger.info("监控未运行，在后台线程直接执行检查")
                # 导入必要模块
                from hosts_monitor.contrast import check_hosts as run_check
                run_check()
        except Exception as e:
            logger.error(f"后台检查时出错: {str(e)}")

    def on_open_hosts_file(self):
        """
        打开 Hosts 文件按钮点击处理
        """
        try:
            os.startfile(HOSTS_PATH)
            logger.info(f"已打开 Hosts 文件: {HOSTS_PATH}")
        except Exception as e:
            logger.error(f"打开 Hosts 文件失败: {str(e)}")
            self.show_message("错误", f"无法打开 Hosts 文件: {str(e)}", QMessageBox.Icon.Critical)
    
    def on_apply_delay(self):
        """
        应用延迟设置按钮点击处理
        """
        try:
            delay_text = self.ui.delay_input.text().strip()
            delay_ms = int(delay_text)
            
            if delay_ms < 0:
                raise ValueError("延迟时间不能为负数")
            
            # 更新配置
            if update_setting('delay_ms', delay_ms):
                logger.info(f"已设置延迟时间为 {delay_ms} 毫秒")
            else:
                logger.error("更新延迟设置失败")
                self.show_message("错误", "更新延迟设置失败", QMessageBox.Icon.Critical)
        except ValueError:
            logger.error("延迟时间必须为有效的整数")
            self.show_message("错误", "延迟时间必须为有效的整数", QMessageBox.Icon.Critical)
    
    def on_toggle_auto_start(self, state):
        """
        开机自启切换处理
        
        参数:
            state: 复选框状态
        """
        enabled = state == Qt.CheckState.Checked.value
        status = "启用" if enabled else "禁用"
        
        # 更新配置
        if update_setting('auto_start', enabled):
            logger.info(f"已{status}开机自启")
            # 执行系统操作
            result = self.set_auto_start(enabled)
            if not result:
                # 恢复设置和复选框状态
                update_setting('auto_start', not enabled)
                self.ui.auto_start_checkbox.setChecked(not enabled)
        else:
            logger.error(f"{status}开机自启失败")
            
            # 恢复复选框状态
            self.ui.auto_start_checkbox.setChecked(not enabled)
    
    def set_auto_start(self, enable):
        """
        设置开机自启
        
        参数:
            enable: 是否启用开机自启
            
        返回:
            bool: 成功返回 True，失败返回 False
        """
        try:
            # 获取程序路径
            if getattr(sys, 'frozen', False):
                # PyInstaller 打包的可执行文件
                app_path = f'"{sys.executable}"'
            else:
                # 脚本运行
                script_path = os.path.abspath(sys.argv[0])
                app_path = f'"{sys.executable}" "{script_path}"'
            
            # 注册表路径
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_name = "HostsMonitor"
            
            # 打开注册表
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                key_path,
                0,
                winreg.KEY_SET_VALUE
            ) as key:
                if enable:
                    # 添加启动项
                    winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, app_path)
                    logger.info(f"已添加开机自启项: {app_path}")
                else:
                    # 移除启动项
                    try:
                        winreg.DeleteValue(key, app_name)
                        logger.info("已移除开机自启项")
                    except FileNotFoundError:
                        # 如果项不存在，忽略错误
                        logger.info("开机自启项不存在，无需移除")
            
            return True
        except Exception as e:
            logger.error(f"设置开机自启失败: {str(e)}")
            self.show_message("错误", f"设置开机自启失败: {str(e)}", QMessageBox.Icon.Critical)
            return False
    def on_request_admin(self):
        """
        请求管理员权限按钮点击处理
        """
        # 检查当前是否已是管理员权限
        if is_admin():
            logger.info("程序已经以管理员权限运行")
            # 禁用按钮并更新提示
            self.ui.admin_button.setEnabled(False)
            self.ui.admin_button.setToolTip("程序已经以管理员权限运行")
            self.ui.admin_button.setText("已获管理员权限")
            self.show_message("提示", "程序已经以管理员权限运行", QMessageBox.Icon.Information)
            return
        
        # 确认是否提升权限
        reply = self.show_message(
            "提升权限",
            "程序需要以管理员权限重新启动才能获得完全的 Hosts 文件访问权限。\n\n是否以管理员权限重新启动?",
            QMessageBox.Icon.Question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            logger.info("正在以管理员权限重新启动程序")
            
            # 停止监控并准备退出
            stop_monitoring()
            
            # 尝试以管理员权限重新启动
            if self.restart_as_admin():
                logger.info("已请求以管理员权限重新启动")
                # 退出当前实例
                self.app.exit(0)
            else:
                logger.error("以管理员权限重新启动失败")
                self.show_message("错误", "无法以管理员权限重新启动程序", QMessageBox.Icon.Critical)
    
    def restart_as_admin(self):
        """
        以管理员权限重新启动程序
        
        返回:
            bool: 成功返回 True，失败返回 False
        """
        try:
            # 获取程序路径
            if getattr(sys, 'frozen', False):
                # PyInstaller 打包的可执行文件
                app_path = sys.executable
                work_dir = os.path.dirname(app_path)
                # 拼接完整的命令行参数，包括可能的命令行参数
                args = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
                
                # 以管理员权限启动可执行文件，不需要提供额外的命令行参数
                result = ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "runas",
                    app_path,
                    args,  # 传递原始命令行参数
                    work_dir,  # 工作目录设为可执行文件所在目录
                    1  # SW_SHOWNORMAL
                )
                logger.info(f"启动可执行文件，返回值: {result}，应用路径: {app_path}，工作目录: {work_dir}")
            else:
                # 脚本运行，需要使用Python解释器启动脚本
                script_path = os.path.abspath(sys.argv[0])
                work_dir = os.path.dirname(script_path)
                
                # 获取真正的启动脚本
                # 如果是从run.py启动的，确保使用run.py而不是内部模块路径
                if script_path.endswith("main.py") or script_path.endswith("controller.py"):
                    run_py_path = os.path.join(work_dir, "..", "run.py")
                    if os.path.exists(run_py_path):
                        script_path = os.path.abspath(run_py_path)
                        work_dir = os.path.dirname(script_path)
                        logger.info(f"使用启动脚本: {script_path}")
                
                # 构建不带引号的参数，ShellExecute内部会处理空格问题
                # 将参数用双引号包裹，确保路径中的空格被正确处理
                params = f'"{script_path}"'
                
                # 传递脚本路径作为参数给Python解释器
                result = ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "runas",
                    sys.executable,
                    params,  # 使用引号包裹路径
                    work_dir,
                    1  # SW_SHOWNORMAL
                )
                logger.info(f"启动脚本，返回值: {result}，脚本路径: {script_path}，工作目录: {work_dir}")
                
            # ShellExecuteW返回值大于32表示成功
            if result <= 32:
                error_messages = {
                    0: "内存不足",
                    2: "文件未找到",
                    3: "路径未找到", 
                    5: "访问被拒绝",
                    8: "内存不足",
                    11: "无效的格式", 
                    26: "共享冲突", 
                    27: "文件名不完整",
                    28: "缺少安装程序",
                    29: "Windows无法访问",
                    30: "Windows无法访问",
                    31: "没有关联的应用程序",
                    32: "没有DDE事务可用"
                }
                error_msg = error_messages.get(result, f"未知错误代码 {result}")
                logger.error(f"ShellExecuteW失败: {error_msg}")
                return False
                
            return True
        except Exception as e:
            logger.error(f"以管理员权限重新启动失败: {str(e)}")
            return False
    
    def show_message(self, title, message, icon=QMessageBox.Icon.Information, buttons=QMessageBox.StandardButton.Ok):
        """
        显示消息对话框
        
        参数:
            title: 对话框标题
            message: 对话框消息
            icon: 对话框图标
            buttons: 对话框按钮
            
        返回:
            用户点击的按钮
        """
        msg_box = QMessageBox(self.ui)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(icon)
        msg_box.setStandardButtons(buttons)
        return msg_box.exec()
    
    def set_application_icon(self):
        """
        设置应用程序图标
        确保图标在开发环境和打包后环境都能正确显示
        """
        try:
            # 确定图标路径：打包环境和开发环境下路径不同
            if getattr(sys, 'frozen', False):
                # PyInstaller 打包环境: 资源位于临时解包路径 _MEIPASS
                base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
                icon_path = os.path.join(base_path, 'resources', 'icon.ico')
            else:
                # 开发环境
                base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                icon_path = os.path.join(base_path, 'resources', 'icon.ico')
            
            # 检查图标文件是否存在
            if os.path.isfile(icon_path):
                from PyQt6.QtGui import QIcon
                app_icon = QIcon(icon_path)
                
                # 设置应用图标
                self.app.setWindowIcon(app_icon)
                # 设置主窗口图标
                self.ui.setWindowIcon(app_icon)
                
                logger.info(f"应用程序图标已设置: {icon_path}")
            else:
                logger.warning(f"图标文件不存在: {icon_path}")
        except Exception as e:
            logger.error(f"设置应用图标时出错: {str(e)}")


# 辅助函数

def is_admin():
    """
    检查当前进程是否以管理员权限运行
    
    返回:
        bool: 是管理员返回 True，否则返回 False
    """
    try:
        # Windows 系统检查管理员权限
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        # 若失败，保守地返回 False
        return False


# 主入口点

def main():
    """
    程序主入口点
    """
    app = QApplication(sys.argv)
    controller = MainController(app)
    controller.start()


if __name__ == "__main__":
    main()
