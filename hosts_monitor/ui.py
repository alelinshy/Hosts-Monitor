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
                            QMenu, QFileDialog, QGroupBox, QFrame, QScrollBar)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QAction, QCloseEvent, QFont, QIntValidator, QPalette, QColor

# 相对导入将在条件判断后处理
# 初始化日志和版本信息
# 支持直接运行UI时的导入方式
try:
    # 尝试相对导入（作为包的一部分导入时）
    from . import logger
    from .version import VERSION, APP_NAME
    from .config import config
    from .monitor import monitor
    from .contrast import contrast_module
    from .repair import repair_module
    from .controller import controller
except ImportError:
    # 当直接运行UI模块时的导入方式
    import sys
    import importlib.util
    import os
    
    # 确定模块路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    
    # 将父目录添加到sys.path
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    # 确保hosts_monitor包可以被识别
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    # 先尝试从包中导入
    try:
        from hosts_monitor import logger, config, monitor, contrast_module, repair_module
        from hosts_monitor.version import VERSION, APP_NAME
        try:
            from hosts_monitor.controller import controller
        except ImportError:
            # 创建一个控制器模拟实现
            print("警告: 控制器模块未找到，将使用模拟实现")
            class DummyController:
                def __init__(self):
                    pass
                def start(self):
                    print("使用模拟控制器启动应用程序")
                def stop(self):
                    print("使用模拟控制器停止应用程序")
            controller = DummyController()
    except ImportError:
        # 如果无法从包导入，尝试直接导入
        print("尝试直接导入模块...")
        sys.path.insert(0, os.path.join(parent_dir, "hosts_monitor"))
        try:
            import logger
            import config
            import monitor
            import version
            import contrast
            import repair
            
            # 获取需要的模块和变量
            VERSION = version.VERSION
            APP_NAME = version.APP_NAME
            contrast_module = contrast.contrast_module
            repair_module = repair.repair_module
            
            try:
                import controller
                controller = controller.controller
            except ImportError:
                print("警告: 控制器模块未找到，将使用模拟实现")
                # 提供一个模拟实现
                class DummyController:
                    def __init__(self):
                        pass
                    def start(self):
                        print("使用模拟控制器启动应用程序")
                    def stop(self):
                        print("使用模拟控制器停止应用程序")
                controller = DummyController()
        except Exception as e:
            print(f"导入模块时发生错误: {str(e)}")
            raise


class HostsMonitorUI(QMainWindow):
    """Hosts Monitor UI类"""
    
    # 布局常量
    TOP_GROUP_HEIGHT = 130  # 顶部控制面板固定高度
    
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
        
        # 窗口大小和样式
        self.setMinimumSize(200, 450)
        self.setup_window_style()
        
        # 从配置恢复窗口大小和位置
        self.restore_window_geometry()

        # 监控状态
        self.is_monitoring = False
        
        # 初始化监控模块的去抖动时间（毫秒转秒）
        delay_time_ms = config.get("general", "delay_time", 3000)
        debounce_time_sec = delay_time_ms / 1000.0
        monitor.set_debounce_time(debounce_time_sec)
        
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
    
    def setup_window_style(self) -> None:
        """设置窗口样式"""
        # 设置应用程序全局字体
        app_font = QFont("Microsoft YaHei UI", 9)  # 使用微软雅黑UI字体
        QApplication.setFont(app_font)
        
        # 设置窗口背景色为浅色
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(245, 245, 248))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(30, 30, 30))
        self.setPalette(palette)
        
        # 设置全局滚动条样式
        self.setStyleSheet("""
            QScrollBar:vertical {
                background-color: #f0f0f0;
                width: 12px;
                margin: 0px 0px 0px 0px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #c0c0c0;
                min-height: 30px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background-color: #f0f0f0;
                border-radius: 6px;
            }
            
            QScrollBar:horizontal {
                background-color: #f0f0f0;
                height: 12px;
                margin: 0px 0px 0px 0px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background-color: #c0c0c0;
                min-width: 30px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #a0a0a0;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background-color: #f0f0f0;
                border-radius: 6px;
            }
        """)
    
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
        tray_menu.setStyleSheet("QMenu { background-color: #ffffff; border: 1px solid #cccccc; }"
                               "QMenu::item { padding: 5px 25px 5px 30px; }"
                               "QMenu::item:selected { background-color: #e6f2ff; }")
        
        show_action = QAction(QIcon(self.icon_path), "显示主窗口", self)
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
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)
        
        # 上栏 - 控制面板
        top_group = QGroupBox("控制面板")
        top_group.setObjectName("topGroup")
        top_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #cccccc; border-radius: 6px; margin-top: 10px; } "
                               "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        top_layout = QVBoxLayout(top_group)
        top_layout.setContentsMargins(10, 20, 10, 10)
        
        # 上栏第一行
        top_row1 = QHBoxLayout()
        
        # 权限控制
        admin_layout = QVBoxLayout()
        admin_layout.setSpacing(5)
        admin_title = QLabel("权限控制")
        admin_title.setStyleSheet("font-weight: bold; color: #444444;")
        admin_layout.addWidget(admin_title)
        
        self.admin_btn = QPushButton("以管理员权限运行")
        self.admin_btn.setMinimumWidth(150)
        self.admin_btn.setStyleSheet("QPushButton { background-color: #0078d7; color: white; border-radius: 4px; padding: 5px; } "
                                    "QPushButton:hover { background-color: #1084e0; } "
                                    "QPushButton:pressed { background-color: #005fa1; } "
                                    "QPushButton:disabled { background-color: #88b7df; }")
        self.admin_btn.clicked.connect(self.run_as_admin)
        admin_layout.addWidget(self.admin_btn)
        
        self.autostart_cb = QCheckBox("开机自启")
        self.autostart_cb.setChecked(config.get("general", "auto_start", False))
        self.autostart_cb.stateChanged.connect(self.toggle_autostart)
        admin_layout.addWidget(self.autostart_cb)
        top_row1.addLayout(admin_layout)
        
        # 分隔线
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.Shape.VLine)
        separator1.setFrameShadow(QFrame.Shadow.Sunken)
        separator1.setStyleSheet("background-color: #cccccc;")
        top_row1.addWidget(separator1)
        
        # 文件操作
        file_layout = QVBoxLayout()
        file_layout.setSpacing(5)
        file_title = QLabel("文件操作")
        file_title.setStyleSheet("font-weight: bold; color: #444444;")
        file_layout.addWidget(file_title)
        
        self.open_hosts_btn = QPushButton("打开hosts文件")
        self.open_hosts_btn.setStyleSheet("QPushButton { background-color: #f0f0f0; border: 1px solid #cccccc; border-radius: 4px; padding: 5px; } "
                                         "QPushButton:hover { background-color: #e6e6e6; } "
                                         "QPushButton:pressed { background-color: #d9d9d9; }")
        self.open_hosts_btn.clicked.connect(self.open_hosts_file)
        file_layout.addWidget(self.open_hosts_btn)
        
        # 监控状态指示
        self.monitor_status_label = QLabel("监控状态: 未知")
        self.monitor_status_label.setStyleSheet("padding: 5px; border: 1px solid #cccccc; border-radius: 4px; background-color: #f9f9f9;")
        file_layout.addWidget(self.monitor_status_label)
        
        top_row1.addLayout(file_layout)
        
        # 分隔线
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.VLine)
        separator2.setFrameShadow(QFrame.Shadow.Sunken)
        separator2.setStyleSheet("background-color: #cccccc;")
        top_row1.addWidget(separator2)
        
        # 操作和设置
        operation_layout = QVBoxLayout()
        operation_layout.setSpacing(5)
        operation_title = QLabel("操作与设置")
        operation_title.setStyleSheet("font-weight: bold; color: #444444;")
        operation_layout.addWidget(operation_title)
        
        # 手动对比按钮
        self.manual_check_btn = QPushButton("手动对比")
        self.manual_check_btn.setStyleSheet("QPushButton { background-color: #5cb85c; color: white; border-radius: 4px; padding: 5px; } "
                                           "QPushButton:hover { background-color: #4cae4c; } "
                                           "QPushButton:pressed { background-color: #3d8b3d; }")
        self.manual_check_btn.clicked.connect(self.manual_contrast)
        operation_layout.addWidget(self.manual_check_btn)
        
        # 延迟设置
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("延迟时间(毫秒):"))
        
        self.delay_edit = QLineEdit()
        self.delay_edit.setFixedWidth(80)
        self.delay_edit.setStyleSheet("border: 1px solid #cccccc; border-radius: 4px; padding: 3px;")
        self.delay_edit.setText(str(config.get("general", "delay_time", 3000)))
        self.delay_edit.setValidator(QIntValidator(1, 10000))
        delay_layout.addWidget(self.delay_edit)
        
        self.apply_delay_btn = QPushButton("应用")
        self.apply_delay_btn.setToolTip("应用延迟时间设置")
        self.apply_delay_btn.setStyleSheet("QPushButton { background-color: #f0f0f0; border: 1px solid #cccccc; border-radius: 4px; padding: 3px; } "
                                          "QPushButton:hover { background-color: #e6e6e6; } "
                                          "QPushButton:pressed { background-color: #d9d9d9; }")
        self.apply_delay_btn.clicked.connect(self.apply_delay_time)
        delay_layout.addWidget(self.apply_delay_btn)
        
        operation_layout.addLayout(delay_layout)
        top_row1.addLayout(operation_layout)
        
        top_row1.addStretch(1)
        top_layout.addLayout(top_row1)
        
        main_layout.addWidget(top_group)
        
        # 上栏设置固定高度
        top_group.setFixedHeight(100)
        
        # 中栏 - hosts数据
        middle_group = QGroupBox("Hosts数据配置")
        middle_group.setObjectName("middleGroup")
        middle_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #cccccc; border-radius: 6px; margin-top: 10px; } "
                                  "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        middle_layout = QVBoxLayout(middle_group)
        middle_layout.setContentsMargins(10, 20, 10, 10)
        
        self.hosts_edit = QTextEdit()
        self.hosts_edit.setPlaceholderText("在这里输入需要监控的hosts数据...")
        self.hosts_edit.setFont(QFont("Consolas", 10))
        self.hosts_edit.setStyleSheet("border: 1px solid #cccccc; border-radius: 4px; background-color: #ffffff;")
        self.hosts_edit.setText(config.get_hosts_data())
        middle_layout.addWidget(self.hosts_edit)
        
        save_layout = QHBoxLayout()
        save_layout.addStretch(1)
        
        self.save_btn = QPushButton("保存配置")
        self.save_btn.setMinimumWidth(120)
        self.save_btn.setStyleSheet("QPushButton { background-color: #0078d7; color: white; border-radius: 4px; padding: 6px; font-weight: bold; } "
                                   "QPushButton:hover { background-color: #1084e0; } "
                                   "QPushButton:pressed { background-color: #005fa1; }")
        self.save_btn.clicked.connect(self.save_config)
        save_layout.addWidget(self.save_btn)
        
        middle_layout.addLayout(save_layout)
        
        main_layout.addWidget(middle_group)
        
        # 下栏 - 日志
        bottom_group = QGroupBox("运行日志")
        bottom_group.setObjectName("bottomGroup")
        bottom_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #cccccc; border-radius: 6px; margin-top: 10px; } "
                                  "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        bottom_layout = QVBoxLayout(bottom_group)
        bottom_layout.setContentsMargins(10, 20, 10, 10)
        
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Consolas", 9))
        self.log_view.setStyleSheet("border: 1px solid #cccccc; border-radius: 4px; background-color: #f5f5f5;")
        # 启用自动换行
        self.log_view.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        bottom_layout.addWidget(self.log_view)
        
        main_layout.addWidget(bottom_group)
        
        # 不使用setStretch，而是通过调整窗口大小事件处理来设置高度
        self.resized_flag = False  # 标记是否已调整过尺寸
    
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
            
    def create_admin_task(self) -> bool:
        """创建管理员权限的任务计划"""
        try:
            # 获取程序完整路径
            if getattr(sys, 'frozen', False):
                app_path = sys.executable
            else:
                # 对于脚本，使用Python解释器启动
                app_path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
            
            # 任务计划名称
            task_name = f"{APP_NAME.replace(' ', '_')}_AdminTask"
            
            # 工作目录
            work_dir = os.path.dirname(os.path.abspath(app_path if getattr(sys, 'frozen', False) else sys.argv[0]))
            
            # 创建XML文件内容
            xml_content = f"""<?xml version="1.0" encoding="UTF-16"?>
    <Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
      <RegistrationInfo>
    <Description>{APP_NAME} 管理员权限启动任务</Description>
      </RegistrationInfo>
      <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
      </Principals>
      <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>false</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
      </Settings>
      <Actions Context="Author">
    <Exec>
      <Command>{app_path}</Command>
      <WorkingDirectory>{work_dir}</WorkingDirectory>
    </Exec>
      </Actions>
    </Task>
    """
            
            # 创建临时XML文件
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.xml', delete=False, mode='w', encoding='utf-16') as temp:
                temp_xml_path = temp.name
                temp.write(xml_content)
            
            # 使用schtasks创建任务
            logger.info(f"正在创建管理员权限任务计划: {task_name}")
            result = subprocess.run(
                ['schtasks', '/create', '/tn', task_name, '/xml', temp_xml_path, '/f'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # 删除临时XML文件
            try:
                os.unlink(temp_xml_path)
            except:
                pass
            
            # 检查是否成功
            if result.returncode == 0:
                logger.info("管理员权限任务计划创建成功")
                return True
            else:
                logger.error(f"创建任务计划失败: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"创建管理员权限任务计划失败: {str(e)}")
            return False
    
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
            
            # 首先尝试创建管理员权限的任务计划
            # 此操作需要UAC确认，但只需要一次
            if self.create_admin_task():
                # 创建成功后，使用任务计划启动程序
                task_name = f"{APP_NAME.replace(' ', '_')}_AdminTask"
                logger.info(f"正在通过任务计划启动: {task_name}")
                
                # 启动任务
                subprocess.Popen(
                    ['schtasks', '/run', '/tn', task_name],
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                # 关闭系统托盘图标
                self.tray_icon.hide()
                
                # 等待一会儿后退出当前实例
                logger.info("管理员权限的新实例通过任务计划启动，当前实例即将退出")
                QTimer.singleShot(1000, QApplication.quit)
                return
            
            # 如果任务计划创建失败，回退到传统的UAC方式
            logger.warning("创建任务计划失败，将使用传统UAC方式请求管理员权限")
            
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
                # 直接退出当前实例，不显示提示弹窗
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
            # 获取延迟时间（毫秒）
            try:
                delay_text = self.delay_edit.text().strip()
                if not delay_text:
                    delay_time = 3000  # 默认值（毫秒）
                    logger.warning("延迟时间为空，使用默认值3000毫秒")
                else:
                    delay_time = int(delay_text)
                    if delay_time < 1:
                        delay_time = 1
                        logger.warning("延迟时间小于1毫秒，已调整为1毫秒")
                    elif delay_time > 10000:
                        delay_time = 10000
                        logger.warning("延迟时间大于10000毫秒，已调整为10000毫秒")
            except ValueError as e:
                logger.error(f"延迟时间格式错误: {str(e)}，使用默认值3000毫秒")
                delay_time = 3000
                QMessageBox.warning(self, "警告", f"延迟时间格式错误，已使用默认值3000毫秒")
            
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
            self.monitor_status_label.setStyleSheet("padding: 5px; border: 1px solid #c3e6cb; "
                                                   "border-radius: 4px; background-color: #d4edda; "
                                                   "color: #155724; font-weight: bold;")
        else:
            self.monitor_status_label.setText("监控状态: 已停止")
            self.monitor_status_label.setStyleSheet("padding: 5px; border: 1px solid #f5c6cb; "
                                                   "border-radius: 4px; background-color: #f8d7da; "
                                                   "color: #721c24; font-weight: bold;")
    
    def manual_contrast(self) -> None:
        """手动执行对比"""
        logger.info("手动触发对比检查")
        contrast_module.start()
    
    def apply_delay_time(self) -> None:
        """应用延迟时间设置"""
        try:
            # 获取延迟时间（毫秒）
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
        """更新日志视图，根据消息类型使用不同颜色"""
        # 根据消息类型设置不同颜色
        if "错误" in message or "失败" in message:
            # 错误消息使用红色
            formatted_message = f'<span style="color:#e74c3c;">{message}</span>'
        elif "警告" in message:
            # 警告消息使用橙色
            formatted_message = f'<span style="color:#e67e22;">{message}</span>'
        elif "成功" in message or "已保存" in message:
            # 成功消息使用绿色
            formatted_message = f'<span style="color:#27ae60;">{message}</span>'
        elif "信息" in message or "提示" in message:
            # 信息消息使用蓝色
            formatted_message = f'<span style="color:#2980b9;">{message}</span>'
        else:
            # 默认消息颜色
            formatted_message = message
            
        # 追加消息到日志视图
        self.log_view.append(formatted_message)
        
        # 滚动到底部
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def resizeEvent(self, event) -> None:
        """窗口大小变更事件处理"""
        super().resizeEvent(event)
        # 调用调整高度方法
        self.adjust_layout_heights()

        # 不在每次调整大小时保存，避免频繁写入配置文件
        # 而是在窗口关闭时保存

    def moveEvent(self, event) -> None:
        """窗口移动事件处理"""
        super().moveEvent(event)

        # 不在每次移动时保存，避免频繁写入配置文件
        # 而是在窗口关闭时保存

    def showEvent(self, event) -> None:
        """窗口显示事件，用于初始化高度设置"""
        super().showEvent(event)
        # 显示后立即触发一次尺寸调整
        QTimer.singleShot(100, self.adjust_layout_heights)
    
    def adjust_layout_heights(self) -> None:
        """调整布局高度"""
        central_height = self.centralWidget().height()
        
        # 设置上栏固定高度
        top_group = self.findChild(QGroupBox, "topGroup")
        if top_group:
            top_group.setFixedHeight(self.TOP_GROUP_HEIGHT)
        
        # 设置中栏高度
        middle_height = int((central_height - self.TOP_GROUP_HEIGHT) * 0.4)
        if middle_height > 0:
            middle_group = self.findChild(QGroupBox, "middleGroup")
            if middle_group:
                middle_group.setFixedHeight(middle_height)
    
    def restore_window_geometry(self) -> None:
        """从配置中恢复窗口大小和位置"""
        width = config.get("window", "width", 550)
        height = config.get("window", "height", 750)
        pos_x = config.get("window", "pos_x", -1)
        pos_y = config.get("window", "pos_y", -1)
        
        # 设置窗口大小
        self.resize(width, height)
        
        # 设置窗口位置（如果有保存）
        if pos_x >= 0 and pos_y >= 0:
            self.move(pos_x, pos_y)
        else:
            # 居中显示
            self.setGeometry(
                QApplication.primaryScreen().geometry().width() // 2 - width // 2,
                QApplication.primaryScreen().geometry().height() // 2 - height // 2,
                width,
                height
            )
        
        logger.info(f"已从配置恢复窗口大小: {width}x{height}")
    
    def save_window_geometry(self) -> None:
        """保存窗口大小和位置到配置"""
        # 保存窗口大小
        config.set("window", "width", self.width())
        config.set("window", "height", self.height())
        
        # 保存窗口位置
        config.set("window", "pos_x", self.x())
        config.set("window", "pos_y", self.y())
        
        # 保存配置
        config.save_config()
        logger.info(f"已保存窗口大小: {self.width()}x{self.height()}, 位置: ({self.x()}, {self.y()})")
    
    def closeEvent(self, event: QCloseEvent) -> None:
        """关闭事件处理"""
        # 保存窗口大小和位置
        self.save_window_geometry()
        
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
            # 保存窗口大小和位置
            self.save_window_geometry()
            
            # 控制器负责停止监控，这里只隐藏托盘图标
            self.tray_icon.hide()
            QApplication.quit()


# 移除自定义验证器类，使用QIntValidator替代


def main():
    """UI模块的主函数入口点，支持单独运行"""
    import sys
    
    try:
        # 记录启动信息
        if hasattr(logger, "info"):
            logger.info(f"正在启动 {APP_NAME} v{VERSION} (UI独立运行模式)")
        else:
            print(f"正在启动 {APP_NAME} v{VERSION} (UI独立运行模式)")
        
        # 检查是否已有实例在运行
        # 此处可以添加单实例检查逻辑
        
        # 初始化配置
        if hasattr(config, "init_config") and callable(config.init_config):
            config.init_config()
        
        # 创建QApplication实例
        app = QApplication(sys.argv)
        app.setApplicationName(APP_NAME)
        app.setApplicationVersion(VERSION)
        
        # 设置样式表
        app.setStyle("Fusion")
        
        # 创建主窗口
        main_window = HostsMonitorUI()
        main_window.show()
        
        # 启动监控线程
        try:
            if hasattr(monitor, "start_monitoring") and callable(monitor.start_monitoring):
                monitor.start_monitoring()
                if hasattr(logger, "info"):
                    logger.info("监控线程已启动")
                else:
                    print("监控线程已启动")
        except Exception as e:
            error_msg = f"启动监控线程失败: {str(e)}"
            if hasattr(logger, "error"):
                logger.error(error_msg)
            else:
                print(f"错误: {error_msg}")
            # 显示错误消息对话框，但不终止程序
            QMessageBox.warning(main_window, "警告", f"启动监控功能失败: {str(e)}\n程序仍将继续运行，但某些功能可能不可用。")
        
        # 运行应用程序主循环
        sys.exit(app.exec())
    except Exception as e:
        error_msg = f"启动UI失败: {str(e)}"
        if hasattr(logger, "critical"):
            logger.critical(error_msg)
        else:
            print(f"严重错误: {error_msg}")
        
        # 显示错误对话框
        app = QApplication(sys.argv) if 'app' not in locals() else app
        QMessageBox.critical(None, "严重错误", f"启动程序失败: {str(e)}\n请检查日志获取更多信息。")
        sys.exit(1)


# 当直接运行ui.py时执行主函数
if __name__ == "__main__":
    main()
