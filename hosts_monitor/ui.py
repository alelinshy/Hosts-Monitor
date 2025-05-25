import sys
import os
from PyQt6.QtCore import Qt, QEvent, QTimer, QCoreApplication
from PyQt6.QtGui import QIcon, QFont, QColor, QFontDatabase, QAction
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QGroupBox,
    QLabel,
    QPushButton,
    QCheckBox,
    QLineEdit,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QDialog,
    QHeaderView,
    QSizePolicy,
    QGraphicsDropShadowEffect,
    QAbstractItemView,
    QSystemTrayIcon,
    QMenu
)

class StyleManager:
    """样式表管理类，负责加载和应用UI样式以及相关UI增强功能"""
    
    @staticmethod
    def apply_dpi_scaling():
        """
        检测屏幕DPI并应用相应的缩放设置
        使Qt应用程序在高DPI显示器上呈现清晰
        """
        try:
            screen = QApplication.primaryScreen()
            if screen:
                # 设置高DPI缩放策略
                QApplication.setHighDpiScaleFactorRoundingPolicy(
                    Qt.HighDpiScaleFactorRoundingPolicy.RoundPreferFloor)
                
                # 启用高DPI像素图缩放（PyQt6推荐做法）
                # PyQt6 可能不再支持 AA_UseHighDpiPixmaps，若出错可注释掉此行
                # QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
                
                # 尝试设置其他高DPI相关属性
                # PyQt6 已不再支持 AA_DisableHighDpiScaling，直接跳过此设置
        except:
            # 如果不支持，忽略错误
            pass
            
    @staticmethod
    def create_group_box(title):
        """
        创建一个标准样式的分组框
        
        参数:
        - title: 分组框标题
        
        返回: QGroupBox 实例
        """
        group_box = QGroupBox(title)
        # 分组框样式已在QSS中定义
        return group_box
    
    @staticmethod
    def create_standard_table(columns, headers=None, editable=False):
        """
        创建一个标准配置的表格
        
        参数:
        - columns: 表格列数
        - headers: 列标题列表
        - editable: 是否可编辑
        
        返回: QTableWidget 实例
        """
        table = QTableWidget(0, columns)
        
        # 设置列标题
        if headers and len(headers) == columns:
            table.setHorizontalHeaderLabels(headers)
        
        # 设置表格属性
        header = table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        vheader = table.verticalHeader()
        if vheader is not None:
            vheader.setVisible(False)
        
        # 设置编辑触发器
        if not editable:
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        # 设置选择行为
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        return table
    
    @staticmethod
    def create_scroll_area(align_top=True):
        """
        创建标准配置的滚动区域
        
        参数:
        - align_top: 内容是否顶部对齐
        
        返回:
        - scroll: QScrollArea 实例
        - content_layout: 内容区域的布局
        """
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)  # 无边框
        
        # 创建内容部件和布局
        content = QWidget()
        content_layout = QVBoxLayout(content)
        
        # 设置对齐方式
        if align_top:
            content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # 设置滚动区域内容
        scroll.setWidget(content)
        
        return scroll, content_layout
    
    @staticmethod
    def optimize_text_editor_font(text_edit):
        """
        优化文本编辑器的字体渲染
        
        参数:
        - text_edit: QTextEdit实例
        """
        try:
            # 优化QTextEdit字体渲染 - 替代CSS中的-webkit-font-smoothing
            log_font = text_edit.font()
            log_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
            text_edit.setFont(log_font)
        except:
            # 如果不支持，忽略错误
            pass
    
    @staticmethod
    def optimize_text_editor_layout(text_edit):
        """
        优化文本编辑器的文本布局，特别针对中文显示优化
        
        参数:
        - text_edit: QTextEdit实例
        """
        try:
            # 获取文档选项对象
            doc_options = text_edit.document().defaultTextOption()
            
            # 设置基本文本对齐和方向
            doc_options.setAlignment(Qt.AlignmentFlag.AlignLeft)
            doc_options.setTextDirection(Qt.LayoutDirection.LeftToRight)
            
            # 使用设计指标而非屏幕指标，提高文本布局质量
            doc_options.setUseDesignMetrics(True)
            
            # 设置自动换行模式，适合中文显示
            doc_options.setWrapMode(doc_options.WrapMode.WrapAtWordBoundaryOrAnywhere)
            
            # 设置文本选项标识，针对中文优化
            doc_options.setFlags(
                doc_options.flags() | 
                doc_options.Flag.AddSpaceForLineAndParagraphSeparators | 
                doc_options.Flag.SuppressColors
            )
            
            # 将优化后的选项应用到文档
            text_edit.document().setDefaultTextOption(doc_options)
        except:
            # 如果不支持，忽略错误
            pass
    
    @staticmethod
    def create_rule_item_widget(rule_name, edit_callback, delete_callback):
        """
        创建单个规则项的部件
        
        参数:
        - rule_name: 规则名称
        - edit_callback: 编辑按钮回调函数
        - delete_callback: 删除按钮回调函数
        
        返回: QWidget 实例
        """
        item_widget = QWidget()
        layout = QHBoxLayout(item_widget)
        layout.setContentsMargins(0, 0, 0, 0)
    
        # 创建规则启用/禁用复选框
        checkbox = QCheckBox()
        checkbox.setObjectName("rule_checkbox")
    
        # 创建规则名称标签
        label = QLabel(rule_name)
    
        # 创建编辑按钮
        edit_btn = QPushButton("编辑")
        edit_btn.setObjectName("rule_edit_btn")
        edit_btn.clicked.connect(edit_callback)
    
        # 创建删除按钮
        delete_btn = QPushButton("删除")
        delete_btn.setObjectName("rule_delete_btn")
        delete_btn.clicked.connect(delete_callback)
    
        # 添加到布局
        layout.addWidget(checkbox)
        layout.addWidget(label, stretch=1)
        layout.addWidget(edit_btn)
        layout.addWidget(delete_btn)
        
        return item_widget
            
    @staticmethod
    def apply_font_settings(app):
        """应用字体相关设置到整个应用程序"""
        try:
            # 启用字体抗锯齿设置 - 替代样式表中的font-smooth
            app_font = app.font()
            app_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
            app.setFont(app_font)
            
            # 添加字体替代方案
            for base_font in ["Microsoft YaHei", "Microsoft YaHei UI", "SimHei"]:
                for substitute in ["思源黑体 CN", "Source Han Sans CN", "HarmonyOS Sans SC", "Noto Sans CJK SC"]:
                    QFont.insertSubstitution(base_font, substitute)
            
            # 宋体替代为思源宋体
            QFont.insertSubstitution("SimSun", "思源宋体 CN")
            QFont.insertSubstitution("SimSun", "Source Han Serif CN")
            QFont.insertSubstitution("SimSun", "Noto Serif CJK SC")
            
            # 设置等宽字体替代方案 - 优化中文等宽显示
            for mono_font in ["Consolas", "Courier New", "Microsoft YaHei UI Mono"]:
                for substitute in ["思源等宽 SC", "Source Han Mono SC", "JetBrains Mono", "Sarasa Term SC"]:
                    QFont.insertSubstitution(mono_font, substitute)
        except:
            # 如果不支持此方法，则忽略
            pass
    
    @staticmethod
    def load_custom_fonts():
        """加载自定义字体资源"""
        try:
            # 添加本地字体目录
            app_dir = os.path.dirname(os.path.abspath(__file__))
            font_dir = os.path.join(app_dir, "fonts")
            if os.path.exists(font_dir):
                QFontDatabase.addApplicationFont(os.path.join(font_dir, "SourceHanSansCN-Regular.otf"))
                QFontDatabase.addApplicationFont(os.path.join(font_dir, "SourceHanSansCN-Medium.otf"))
                QFontDatabase.addApplicationFont(os.path.join(font_dir, "SourceHanSansCN-Bold.otf"))
        except:
            # 如果找不到字体资源，忽略错误
            pass
    
    @staticmethod
    def apply_shadow_effect(widget, blur_radius=18, opacity=60, offset_x=0, offset_y=0):
        """
        为部件添加阴影效果
        
        参数:
        - widget: 需要添加阴影的部件
        - blur_radius: 阴影的模糊半径
        - opacity: 阴影透明度(0-255)
        - offset_x: 阴影的水平偏移
        - offset_y: 阴影的垂直偏移
        """
        try:
            shadow = QGraphicsDropShadowEffect(widget)
            shadow.setBlurRadius(blur_radius)  # 设置模糊半径
            shadow.setColor(QColor(0, 0, 0, opacity))  # 设置颜色和透明度
            shadow.setOffset(offset_x, offset_y)  # 设置偏移
            widget.setGraphicsEffect(shadow)
        except:
            # 如果不支持，忽略错误
            pass
    
    @staticmethod
    def get_style_sheet():
        """返回应用的全局样式表"""
        # 样式表直接内嵌在代码中，不再从外部文件加载
        return """/* 全局样式表 - Hosts Monitor 应用程序
   用于统一管理界面字体和文字样式
*/

/* 应用全局默认字体设置 */
* {
    font-family: "HarmonyOS Sans SC", "Microsoft YaHei", "Microsoft YaHei UI", "PingFang SC",
                "Noto Sans CJK SC", "Hiragino Sans GB", "WenQuanYi Micro Hei",
                "Segoe UI";
    font-size: 10.5pt;
    font-weight: 450;           /* 稍微加粗增强清晰度 */
    letter-spacing: 0.3px;      /* 增加字间距 */
    color: #101010;             /* 稍深色文字增强对比度 */
}

/* 主窗口设置 */
QMainWindow { 
    background: #F0F2F5;
    font-family: "思源黑体 CN", "Source Han Sans CN", "HarmonyOS Sans SC", 
                "Microsoft YaHei", "Microsoft YaHei UI", "PingFang SC", 
                "Noto Sans CJK SC", "Hiragino Sans GB", "WenQuanYi Micro Hei", 
                "Segoe UI";
    font-size: 10pt;
}

/* 标签默认字体设置 */
QLabel {
    font-family: "思源黑体 CN", "Source Han Sans CN", "HarmonyOS Sans SC", 
                "Microsoft YaHei", "Microsoft YaHei UI", "PingFang SC", 
                "Noto Sans CJK SC", "Hiragino Sans GB", "WenQuanYi Micro Hei", 
                "Segoe UI";
    font-size: 10pt;
    letter-spacing: 0.4px;      /* 增加字间距 */
    color: #000000;             /* 纯黑色增强对比度 */    /* 移除text-shadow，因为当前版本的PyQt6不支持它 */
    /* text-shadow: 0 0 1px rgba(0, 0, 0, 0.15); */  /* 微弱阴影增强文字边缘 */
}

/* 标题字体 */
QLabel#title {
    font-size: 13pt;
    letter-spacing: 0.5px;
    color: #000000;    /* Qt不支持text-shadow属性，已移除 */
    /* text-shadow: 0 1px 1px rgba(0, 0, 0, 0.2); */
}

/* 版本标签 */
QLabel#version_label {
    font-size: 18pt;
}

/* 分组框设置 */
QGroupBox {
    background: #FFFFFF;
    border: none;
    border-radius: 10px;
    /* 分组框标题与窗口间距 */
    margin-top: 40px;

    font-family: "思源黑体 CN", "Source Han Sans CN", "HarmonyOS Sans SC",
                "Microsoft YaHei", "Microsoft YaHei UI", "PingFang SC", 
                "Noto Sans CJK SC", "Hiragino Sans GB", "WenQuanYi Micro Hei", 
                "Segoe UI";
    font-size: 13pt;
    letter-spacing: 0.5px;      /* 标题字间距更大 */
    color: #000000;             /* 纯黑色标题 */    /* Qt不支持text-shadow属性，已移除 */
    /* text-shadow: 0 1px 0 rgba(0, 0, 0, 0.2); */
}

QGroupBox::title {
    subcontrol-origin: margin;  /* 从 margin 区域开始布局标题 */
    left: 15px;                 /* 标题距离左侧 */
    padding: 0 8px;             /* 水平内边距 */
    color: #000000;           /* 字体颜色 */
}

/* 按钮样式设置 */
QPushButton {
    background: #005A9E;      /* 主色：微软经典蓝 */
    color: #FFFFFF;             /* 纯白色字体 */
    border: none;               /* 无边框 */
    border-radius: 6px;         /* 圆角 6px */
    padding: 6px 14px;          /* 上下内边距6px，左右14px */
    font-family: "思源黑体 CN", "Source Han Sans CN", "HarmonyOS Sans SC", 
                "Microsoft YaHei", "Microsoft YaHei UI", "PingFang SC", 
                "Noto Sans CJK SC", "Hiragino Sans GB", "WenQuanYi Micro Hei", 
                "Segoe UI";
    font-size: 10.5pt;   /* 使用按钮专用字号 */
    letter-spacing: 0.5px;      /* 增加字间距 */    /* Qt不支持text-shadow属性，已移除 */
    /* text-shadow: 0 1px 0 rgba(0, 0, 0, 0.5); */
    text-align: center;         /* 水平居中 */
    /* QPushButton不支持qproperty-alignment属性，已移除 */
    /* qproperty-alignment: AlignCenter; */
}

/* 规则管理区域的编辑按钮 */
QPushButton#rule_edit_btn {
    background: #4CAF50;  /* 使用绿色背景 */
    color: #FFFFFF;
}

QPushButton#rule_edit_btn:pressed {
    background: #388E3C;  /* 按下时更深的绿色 */
}

/* 规则管理区域的删除按钮 */
QPushButton#rule_delete_btn {
    background: #F44336;  /* 使用红色背景 */
    color: #FFFFFF;
}

QPushButton#rule_delete_btn:pressed {
    background: #D32F2F;  /* 按下时更深的红色 */
}

/* 按下时更深的按压效果 */
QPushButton:pressed {
    background: #004C87;
}

/* 输入框和表格设置 */
QLineEdit, QTableWidget {
    background: #FFFFFF;      /* 背景白 */
    border: 1px solid #DDD;   /* 1px 浅灰边框 */
    border-radius: 6px;         /* 圆角 6px */
    padding: 4px;               /* 内边距 4px */
    font-family: "思源黑体 CN", "Source Han Sans CN", "HarmonyOS Sans SC", 
                "Microsoft YaHei", "Microsoft YaHei UI", "PingFang SC", 
                "Noto Sans CJK SC", "Hiragino Sans GB", "WenQuanYi Micro Hei", 
                "Segoe UI";
    font-size: 10.5pt;    /* 使用输入框专用字号 */
}

/* 表头设置 */
QHeaderView::section {
    background: #E8E8E8;      /* 表头背景 */
    padding: 8px;               /* 内边距 8px */
    border: 1px solid #DDDDDD;               /* 去掉分割线 */
    font-family: "思源黑体 CN", "Source Han Sans CN", "HarmonyOS Sans SC", 
                "Microsoft YaHei", "Microsoft YaHei UI", "PingFang SC", 
                "Noto Sans CJK SC", "Hiragino Sans GB", "WenQuanYi Micro Hei", 
                "Segoe UI";
    font-size: 10.5pt;
    font-weight: bold;          /* 加粗 */
}

/* 复选框设置 */
QCheckBox {
    font-family: "思源黑体 CN", "Source Han Sans CN", "HarmonyOS Sans SC", 
                "Microsoft YaHei", "Microsoft YaHei UI", "PingFang SC", 
                "Noto Sans CJK SC", "Hiragino Sans GB", "WenQuanYi Micro Hei", 
                "Segoe UI";
    font-size: 10.5pt;
    spacing: 6px;               /* 增加复选框与文本之间的距离 */
    color: #101010;             /* 确保文字颜色统一 */
    min-height: 20px;           /* 设置最小高度，确保点击区域足够大 */
}

/* 复选框指示器样式 */
QCheckBox::indicator {
    width: 18px;                /* 增加复选框大小 */
    height: 18px;               /* 增加复选框大小 */
    border: 1px solid #AAA;     /* 浅灰色边框 */
    border-radius: 3px;         /* 稍微圆角 */
    background-color: #FFFFFF;  /* 白色背景 */
}

/* 悬停时的样式 */
QCheckBox::indicator:hover {
    border-color: #005A9E;      /* 使用主题蓝色边框 */
    background-color: #F5F5F5;  /* 轻微灰色背景 */
}

/* 复选框指示器样式，不使用图像 */
QCheckBox::indicator:checked {
    background-color: #005A9E;  /* 使用主题蓝色背景 */
    border-color: #005A9E;      /* 边框与背景同色 */
    /* 下面创建一个简单的对勾效果，使用内部渐变 */
    background: qradialgradient(
        cx: 0.5, cy: 0.5,
        fx: 0.5, fy: 0.5,
        radius: 0.4,
        stop: 0 #005A9E,
        stop: 0.6 #005A9E,
        stop: 0.8 white,
        stop: 0.9 #005A9E,
        stop: 1 #005A9E
    );
}

/* 选中并悬停状态 */
QCheckBox::indicator:checked:hover {
    background-color: #0066B3;  /* 略深蓝色背景 */
    border-color: #0066B3;      /* 边框与背景同色 */
}

/* 特定样式：规则管理面板内的复选框 */
#rule_checkbox {
    padding-left: 4px;          /* 为规则管理面板中的复选框增加左侧内边距 */
}

/* 特定样式：在hover上突出显示整行规则项 */
#rule_checkbox:hover {
    background-color: #F5F5F5;  /* 轻微灰色背景 */
}

/* 表格项（单元格）悬停高亮和选中样式，使交互更细腻 */
QTableWidget::item:hover {
    background: #F5F5F5;      /* 悬停时淡灰色背景 */
}
QTableWidget::item:selected {
    background: #CCE4FF;      /* 选中时浅蓝背景 */
    color: #000;              /* 选中时字体黑色 */
}

/* 滚动区域去掉边框，保持内容区干净简洁 */
QScrollArea {
    border: none;
}

/* 日志文本框特殊字体设置 */
QTextEdit#log_text {
    background: #1E1E1E;      /* 深灰近黑背景 */
    color: #F0F0F0;           /* 更亮的灰色字体增强对比度，提高中文可读性 */
    border: none;               /* 无边框 */
    border-radius: 6px;         /* 圆角 6px */
    padding: 10px;              /* 增加内边距 */
    font-family: "JetBrains Maple Mono", "Consolas";  /* 中文优化等宽字体 */
    font-size: 10pt;          /* 使用日志专用字号 */
    line-height: 1.4;           /* 增加行高，适合中文显示 */
    selection-background-color: #3A546D;  /* 选中文本背景色 */
    selection-color: #FFFFFF;   /* 选中文本颜色 */
}

/* 日志垂直滚动条样式 - 优化触摸操作 */
QTextEdit#log_text QScrollBar:vertical {
    background: transparent;          /* 背景透明 */
    width: 12px;                      /* 增加滚动条宽度，便于触摸操作 */
    margin: 2px 2px 2px 2px;          /* 四边留出2px空隙 */
    border: none;                     /* 无边框 */
    border-radius: 6px;               /* 整体圆角增大 */
}

/* 日志垂直滚动条滑块样式 */
QTextEdit#log_text QScrollBar::handle:vertical {
    background: rgba(110, 110, 110, 0.55);  /* 调整透明度与颜色 */
    min-height: 35px;                 /* 增加最小高度 */
    border-radius: 6px;               /* 滑块圆角增大 */
}

/* 日志垂直滚动条滑块悬停样式 */
QTextEdit#log_text QScrollBar::handle:vertical:hover {
    background: rgba(130, 130, 130, 0.75);  /* 悬停时更明显 */
}

/* 日志垂直滚动条滑块按下样式 */
QTextEdit#log_text QScrollBar::handle:vertical:pressed {
    background: rgba(160, 160, 160, 0.95);  /* 按下时更明显 */
}

/* 去掉日志滚动条上下箭头和按钮，保持简洁 */
QTextEdit#log_text QScrollBar::add-line:vertical,
QTextEdit#log_text QScrollBar::sub-line:vertical,
QTextEdit#log_text QScrollBar::add-page:vertical,
QTextEdit#log_text QScrollBar::sub-page:vertical {
    background: transparent;
    border: none;
    height: 0px;
}

/* 日志水平滚动条样式（与垂直滚动条保持一致）- 优化触摸操作 */
QTextEdit#log_text QScrollBar:horizontal {
    background: transparent;
    height: 12px;               /* 增加高度，与垂直滚动条一致 */
    margin: 2px 2px 2px 2px;
    border: none;
    border-radius: 6px;         /* 增大圆角，与垂直滚动条一致 */
}

/* 日志水平滚动条滑块样式 */
QTextEdit#log_text QScrollBar::handle:horizontal {
    background: rgba(110, 110, 110, 0.55);  /* 与垂直滚动条一致 */
    min-width: 35px;            /* 增加最小宽度 */
    border-radius: 6px;         /* 增大圆角 */
}

/* 日志水平滚动条滑块悬停样式 */
QTextEdit#log_text QScrollBar::handle:horizontal:hover {
    background: rgba(130, 130, 130, 0.75);  /* 与垂直滚动条一致 */
}

/* 去掉日志水平滚动条左右箭头和按钮 */
QTextEdit#log_text QScrollBar::add-line:horizontal,
QTextEdit#log_text QScrollBar::sub-line:horizontal,
QTextEdit#log_text QScrollBar::add-page:horizontal,
QTextEdit#log_text QScrollBar::sub-page:horizontal {
    background: transparent;
    border: none;
    width: 0px;
}

/* 对话框样式优化，提高文字清晰度 */
QDialog {
    background: #F5F7FA;
    font-family: "思源黑体 CN", "Source Han Sans CN", "HarmonyOS Sans SC", 
                "Microsoft YaHei", "Microsoft YaHei UI", "PingFang SC", 
                "Noto Sans CJK SC", "Hiragino Sans GB", "WenQuanYi Micro Hei", 
                "Segoe UI";
    font-size: 10.5pt;
}

/* 提高表格内中文文字的清晰度 */
QTableWidget::item {
    padding: 6px;
    border-color: transparent;
    font-kerning: true;  /* 启用字距调整 */
}

/* 提高滚动区域内部文字的可读性 */
QScrollArea QWidget {
    background: transparent;
    font-family: "思源黑体 CN", "Source Han Sans CN", "HarmonyOS Sans SC", 
                "Microsoft YaHei", "Microsoft YaHei UI", "PingFang SC", 
                "Noto Sans CJK SC", "Hiragino Sans GB", "WenQuanYi Micro Hei", 
                "Segoe UI";
}

/* 对话框容器特别优化 */
QWidget#container {
    background-color: white;
    border-radius: 12px;
}

/* 规则管理面板和规则映射面板分隔条样式 */
QSplitter::handle:vertical {
    background-color: #EEEEEE;
    width: 1px;
}
QSplitter::handle:horizontal {
    background-color: transparent;
    height: 1px;
}
"""


class RuleEditDialog(QDialog):
    """
    规则编辑对话框（二级界面）
    - 显示已添加的映射列表
    - 支持新增/删除映射
    """

    def __init__(self, rule_name, mappings=None, parent=None):
        super().__init__(parent)
        self.rule_name = rule_name
        self.mappings = mappings or []
        self._init_ui()
        self._load_mappings()
        
    def _init_ui(self):
        """初始化对话框UI"""
        # 基本窗口设置
        self.setWindowTitle(f"编辑规则 : {self.rule_name}")
        self.setMinimumSize(600, 500)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # 设置窗口背景透明
        
        # 创建主布局
        self._create_main_layout()
    
    def _create_main_layout(self):
        """创建主布局和容器"""
        # 设置主对话框的布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)  # 为阴影预留边距
        
        # 创建内容容器
        self.container = QWidget(self)
        self.container.setObjectName("container")
        
        # 为容器添加阴影效果
        self._add_shadow_to_container()
        
        # 添加容器到主布局
        main_layout.addWidget(self.container)
        
        # 创建容器内的布局
        container_layout = QVBoxLayout(self.container)
        container_layout.setSpacing(12)
        container_layout.setContentsMargins(16, 16, 16, 16)
        
        # 添加各区域组件
        self._create_title_area(container_layout)
        self._create_mappings_table(container_layout)
        self._create_add_mapping_area(container_layout)
        self._create_action_buttons(container_layout)
    
    def _add_shadow_to_container(self):
        """为容器添加阴影效果"""
        # 使用StyleManager中的统一方法
        StyleManager.apply_shadow_effect(self.container, blur_radius=20, opacity=80, offset_x=0, offset_y=0)
    
    def _create_title_area(self, parent_layout):
        """创建标题区域"""
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 10)
        
        # 创建标题标签
        title_label = QLabel(f"编辑规则 : {self.rule_name}")
        title_label.setObjectName("title")  # 使用CSS中定义的标题样式
        
        # 添加到布局
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        parent_layout.addLayout(title_layout)
    
    def _create_mappings_table(self, parent_layout):
        """创建映射表格"""
        # 创建表格 - 使用StyleManager中的通用方法
        self.table = StyleManager.create_standard_table(
            columns=2,
            headers=["IP 地址", "域名"],
            editable=True
        )
        
        # 添加到布局
        parent_layout.addWidget(self.table)
    
    def _create_add_mapping_area(self, parent_layout):
        """创建添加映射区域"""
        add_layout = QHBoxLayout()
        
        # 创建IP输入框
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("输入 IP 地址，例如：127.0.0.1")
        
        # 创建域名输入框
        self.domain_input = QLineEdit()
        self.domain_input.setPlaceholderText("输入域名，例如：www.example.com")
        
        # 创建添加按钮
        self.add_button = QPushButton("添加映射")
        self.add_button.clicked.connect(self.add_mapping)
        
        # 添加到布局
        add_layout.addWidget(self.ip_input)
        add_layout.addWidget(self.domain_input)
        add_layout.addWidget(self.add_button)
        parent_layout.addLayout(add_layout)
    
    def _create_action_buttons(self, parent_layout):
        """创建底部操作按钮区域"""
        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建删除按钮
        self.remove_button = QPushButton("删除选中")
        self.remove_button.clicked.connect(self.remove_selected)
        
        # 创建取消按钮
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        
        # 创建保存按钮
        self.save_button = QPushButton("确认")
        self.save_button.clicked.connect(self.accept)
        
        # 添加到布局
        action_layout.addWidget(self.remove_button)
        action_layout.addStretch()
        action_layout.addWidget(self.cancel_button)
        action_layout.addWidget(self.save_button)
        parent_layout.addLayout(action_layout)
    
    def _load_mappings(self):
        """加载初始映射数据到表格"""
        if self.mappings:
            for ip, domain in self.mappings:
                self._add_mapping_to_table(ip, domain)
    
    def _add_mapping_to_table(self, ip, domain):
        """添加一条映射到表格"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(ip))
        self.table.setItem(row, 1, QTableWidgetItem(domain))
        
    def mousePressEvent(self, a0):
        """鼠标按下事件处理 - 用于实现窗口拖动"""
        if a0 is not None:
            self.oldPos = a0.globalPosition().toPoint()
    
    def mouseMoveEvent(self, a0):
        """鼠标移动事件处理 - 用于实现窗口拖动"""
        if a0 is not None and hasattr(self, 'oldPos'):
            delta = a0.globalPosition().toPoint() - self.oldPos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = a0.globalPosition().toPoint()

    def add_mapping(self):
        """添加一条新的IP-域名映射"""
        ip = self.ip_input.text().strip()
        domain = self.domain_input.text().strip()
        if ip and domain:
            self._add_mapping_to_table(ip, domain)
            self.ip_input.clear()
            self.domain_input.clear()

    def remove_selected(self):
        """删除选中的映射"""
        selected_items = self.table.selectedItems()
        if selected_items:
            self.table.removeRow(selected_items[0].row())
            
    def get_mappings(self):
        """获取所有映射数据"""
        mappings = []
        for row in range(self.table.rowCount()):
            ip_item = self.table.item(row, 0)
            domain_item = self.table.item(row, 1)
            if ip_item is not None and domain_item is not None:
                ip = ip_item.text()
                domain = domain_item.text()
                mappings.append((ip, domain))
        return mappings


class HostsMonitorUI(QMainWindow):
    """主窗口类，负责整个应用的UI显示和交互逻辑"""
    
    def __init__(self):
        super().__init__()
        self._init_window()
        self._create_ui_structure()
        self._init_ui_state()
        # 初始化并显示系统托盘图标
        self._init_tray_icon()
    
    def _init_window(self):
        """初始化窗口基本属性和样式"""
        self.setWindowTitle("Hosts Monitor")
        self.setMinimumSize(1250, 950)
        
        # 应用全局样式表
        self.setStyleSheet(StyleManager.get_style_sheet())
        
    def set_window_icon(self, icon_path):
        """
        设置窗口图标
        
        参数:
        - icon_path: 图标文件路径
        
        返回:
        - bool: 设置成功返回True，失败返回False
        """
        try:
            if os.path.isfile(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                return True
            return False
        except Exception:
            return False
    
    def _create_ui_structure(self):
        """创建UI主结构和布局"""
        # 创建中央部件并设置阴影效果
        central = QWidget()
        self.setCentralWidget(central)
        self._apply_shadow_effect(central)

        # 创建主布局
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # 创建顶部区域
        self._setup_top_area(main_layout)

        # 创建中部分割区域
        splitter = self._create_middle_splitter()
        main_layout.addWidget(splitter, stretch=1)

        # 创建底部日志区域
        self._setup_log_area(main_layout)
    
    def _apply_shadow_effect(self, widget):
        """为部件添加阴影效果"""
        # 使用StyleManager中的统一方法
        StyleManager.apply_shadow_effect(widget, blur_radius=18, opacity=60, offset_x=0, offset_y=0)
    
    def _create_middle_splitter(self):
        """创建中部的分割器区域"""
        splitter = QSplitter(Qt.Orientation.Horizontal)
        # 分隔条样式已在QSS文件中定义
        # 设置分隔条宽度
        splitter.setHandleWidth(10)  # 规则管理面板和规则映射面板之间的宽度

        self._setup_rules_area(splitter)
        self._setup_mappings_area(splitter)
        splitter.setSizes([300, 400])
        
        return splitter
    def _init_ui_state(self):
        """初始化UI状态"""
        # 当直接运行UI模块时才加载测试数据
        if __name__ == "__main__":
            self.load_test_data()

    def load_test_data(self):
        """加载测试数据用于UI预览"""
        # 加载测试规则
        test_rules = ["test_rule1", "test_rule2", "test_rule3"]
        for rule in test_rules:
            self.new_rule_input.setText(rule)
            self.add_rule_item()
            
        # 加载测试映射
        test_mappings = [
            ("127.0.0.1", "localhost", "test_rule1"),
            ("192.168.0.1", "mydomain.com", "test_rule2"),
            ("10.0.0.1", "example.org", "test_rule3")
        ]
        for ip, domain, rule in test_mappings:
            row = self.mappings_table.rowCount()
            self.mappings_table.insertRow(row)
            self.mappings_table.setItem(row, 0, QTableWidgetItem(ip))
            self.mappings_table.setItem(row, 1, QTableWidgetItem(domain))
            self.mappings_table.setItem(row, 2, QTableWidgetItem(rule))
            
        # 添加预设的模拟日志信息
        self.log_text.clear()  # 清空之前的日志
        # 日志界面测试信息，增强文字渲染效果
        test_logs = [
            "观察对话框上部两个圆角是否有黑边问题",
            "测试对话框的拖动功能是否正常工作",
            "检查日志区域的自动滚动功能是否正常",
            "验证高DPI下文本是否清晰且无模糊",
            "测试不同字号(9pt、12pt、16pt)下日志字体渲染效果",
            "验证中文与English混排时对齐是否正常",
            "观察滚动条样式与拖动手柄的圆角效果",
            "验证右键菜单功能是否正常弹出",
            "测试复制粘贴日志内容到外部程序",
            "测试日志内容搜索功能是否高亮匹配关键词",
            "验证切换窗口焦点后自动滚动是否暂停",
            "测试日志区域对鼠标拖选文本的支持",
            "验证日志行折叠与展开的表现（如有）",
            "测试日志字体大小动态调整功能",
            "验证日志包含长文本时的自动换行效果",
            "测试日志内容导出到文件功能"
        ]
        
        import datetime
        base_time = datetime.datetime.now()
        
        for i, msg in enumerate(test_logs):
            log_time = (base_time + datetime.timedelta(seconds=i)).strftime('%Y-%m-%d %H:%M:%S')
            formatted_msg = f'<span style="color:#00FF00">[{log_time}] [测试] {msg}</span>'
            self.log_text.append(formatted_msg)

        # 滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        if scrollbar is not None:
            scrollbar.setValue(scrollbar.maximum())

    def _setup_top_area(self, parent_layout):
        """设置顶部功能区域"""
        # 创建容器
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        # 创建布局
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
    
        # 添加版本标签
        self._add_version_label(layout)
        
        # 添加控制按钮
        self._add_control_buttons(layout)
        
        # 添加启动选项
        self._add_startup_option(layout)
        
        # 添加延迟设置
        self._add_delay_settings(layout)
        
        # 将容器添加到父布局
        parent_layout.addWidget(container)
    
    def _add_version_label(self, parent_layout):
        """添加版本标签到布局"""
        self.version_label = QLabel("版本: 1.0.0")
        self.version_label.setObjectName("version_label")  # 使用QSS中定义的版本标签样式
        parent_layout.addWidget(self.version_label)
        parent_layout.addStretch(1)
    
    def _add_control_buttons(self, parent_layout):
        """添加控制按钮到布局"""
        # 创建管理员权限按钮
        self.admin_button = QPushButton(QIcon(), "管理员权限")
        self.admin_button.setToolTip("重新提权以管理员运行")
        parent_layout.addWidget(self.admin_button)
        
        # 创建打开Hosts文件按钮
        self.open_hosts_button = QPushButton(QIcon(), "打开 Hosts 文件")
        self.open_hosts_button.setToolTip("在系统文件管理器中打开 Hosts 文件")
        parent_layout.addWidget(self.open_hosts_button)
    
    def _add_startup_option(self, parent_layout):
        """添加开机自启选项到布局"""
        self.auto_start_checkbox = QCheckBox("开机自启")
        parent_layout.addWidget(self.auto_start_checkbox)
    
    def _add_delay_settings(self, parent_layout):
        """添加延迟设置到布局"""
        # 创建延迟标签
        delay_label = QLabel("延迟时间 (ms):")
        parent_layout.addWidget(delay_label)
        
        # 创建延迟输入框
        self.delay_input = QLineEdit()
        self.delay_input.setFixedWidth(120)
        parent_layout.addWidget(self.delay_input)
        
        # 创建应用按钮
        self.apply_delay_button = QPushButton("应用")
        self.apply_delay_button.setToolTip("应用延迟设置并保存到配置文件")
        parent_layout.addWidget(self.apply_delay_button)

    def _setup_rules_area(self, parent_widget):
        """设置规则管理区域，包括规则列表和添加规则功能"""
        # 创建规则管理分组框
        rules_group = self._create_group_box("规则管理")
        
        # 创建分组框内布局
        box_layout = QVBoxLayout(rules_group)
        box_layout.setContentsMargins(12, 12, 12, 12)
        box_layout.setSpacing(12)
    
        # 创建规则列表滚动区域
        self.rules_content_layout = self._create_rules_scroll_area(box_layout)
    
        # 创建添加规则区域
        self._create_add_rule_area(box_layout)
    
        # 将分组框添加到父部件
        parent_widget.addWidget(rules_group)
    
    def _create_group_box(self, title):
        """创建一个标准样式的分组框"""
        return StyleManager.create_group_box(title)
    
    def _create_rules_scroll_area(self, parent_layout):
        """创建规则列表的滚动区域"""
        # 使用StyleManager中的通用方法创建滚动区域
        scroll, content_layout = StyleManager.create_scroll_area(align_top=True)
        parent_layout.addWidget(scroll)
        
        return content_layout
    def _create_add_rule_area(self, parent_layout):
        """创建添加规则的区域"""
        add_rule_layout = QHBoxLayout()
        
        # 创建规则名称输入框
        self.new_rule_input = QLineEdit()
        self.new_rule_input.setPlaceholderText("新规则名称，例如：rule1")
        
        # 创建添加规则按钮
        self.add_rule_button = QPushButton("+ 添加规则")
        # 注意：不在这里连接信号，让控制器来连接
        # self.add_rule_button.clicked.connect(self.add_rule_item)
        
        # 添加到布局
        add_rule_layout.addWidget(self.new_rule_input)
        add_rule_layout.addWidget(self.add_rule_button)
        parent_layout.addLayout(add_rule_layout)

    def add_rule_item(self):
        """
        添加一个新的规则项到规则列表（仅在UI模块内初始化界面时使用）
        注意：这个方法在实际使用时已由控制器的 on_add_rule 方法替代，
        因为复选框状态变更事件需要在控制器中连接和处理
        """
        from hosts_monitor.config import add_rule, get_rule
        from hosts_monitor.monitor import trigger_check
        from PyQt6.QtWidgets import QMessageBox
        
        name = self.new_rule_input.text().strip()
        if not name:
            return
            
        # 检查规则名是否已存在
        if get_rule(name):
            QMessageBox.warning(self, "规则已存在", f"规则 '{name}' 已存在，请使用其他名称。")
            return
        # 添加到配置文件，默认创建一个空的规则（无映射项）
        if add_rule(name, [], enabled=True):
            # 注意：此处添加的规则项没有为复选框连接状态变更事件
            # 在实际应用中，应使用控制器的 on_add_rule 方法，它会调用 load_rules_to_ui
            # 确保所有规则项的复选框都连接到控制器的 on_toggle_rule 方法
            
            # 创建规则项部件
            rule_item = self._create_rule_item_widget(name)
            
            # 添加到规则内容布局
            self.rules_content_layout.addWidget(rule_item)
            self.new_rule_input.clear()
            
            # 触发检查
            trigger_check()
        else:
            QMessageBox.critical(self, "添加失败", f"无法添加规则 '{name}'，请重试。")
    
    def _create_rule_item_widget(self, rule_name):
        """创建单个规则项的部件"""
        # 使用StyleManager的通用方法创建规则项部件
        item_widget = StyleManager.create_rule_item_widget(
            rule_name, 
            lambda: self.open_edit_dialog(rule_name),
            lambda: self.delete_rule(rule_name, item_widget)  # 删除规则项
        )
        
        # 注意：复选框的状态变更事件连接应该由控制器处理
        # 这里不连接事件，返回的 widget 让控制器访问复选框并连接事件
        
        return item_widget
        
    def delete_rule(self, rule_name, item_widget):
        """删除规则并更新UI"""
        from hosts_monitor.config import remove_rule
        from PyQt6.QtWidgets import QMessageBox
        
        # 确认删除对话框
        reply = QMessageBox.question(
            self, 
            "确认删除",
            f"确定要删除规则 '{rule_name}' 吗?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 从配置文件中删除规则
            if remove_rule(rule_name):
                # 从UI中移除规则项
                item_widget.setParent(None)
                
                # 更新映射表格，移除被删除规则的映射
                self._refresh_mappings_table()
    
    def open_edit_dialog(self, rule_name):
        """打开编辑规则的对话框"""
        # 获取当前规则的映射（实际应用中应从数据存储中获取）
        mappings = self._get_rule_mappings(rule_name)
        
        # 创建并显示对话框
        dlg = RuleEditDialog(rule_name, mappings, self)
        if dlg.exec():
            # 处理对话框返回的结果（实际应用中应保存到数据存储）
            self._save_rule_mappings(rule_name, dlg)
    def _get_rule_mappings(self, rule_name):
        """获取指定规则的映射数据"""
        # 从配置模块获取规则数据
        from hosts_monitor.config import get_rule
        
        rule = get_rule(rule_name)
        if rule and 'entries' in rule:
            # 转换配置模块的格式为对话框所需的格式
            return [(entry['ip'], entry['domain']) for entry in rule['entries']]
        return []
    def _save_rule_mappings(self, rule_name, dialog):
        """保存规则映射数据到配置文件"""
        from hosts_monitor.config import update_rule
        from hosts_monitor.monitor import trigger_check
        
        # 获取对话框中的映射数据
        mappings = dialog.get_mappings()
        
        # 转换为配置模块所需的格式
        entries = [{'ip': ip, 'domain': domain} for ip, domain in mappings]
        
        # 更新规则
        if update_rule(rule_name, {'entries': entries}):
            # 刷新映射表格
            self._refresh_mappings_table()
            # 触发检查
            trigger_check()
    
    def _setup_mappings_area(self, parent_widget):
        """设置规则映射区域，显示所有规则的映射关系"""
        # 创建规则映射分组框
        mappings_group = self._create_group_box("规则映射")
        
        # 创建分组框内布局
        box_layout = QVBoxLayout(mappings_group)
        box_layout.setContentsMargins(12, 12, 12, 12)
    
        # 创建映射表格
        self.mappings_table = self._create_mappings_table()
        box_layout.addWidget(self.mappings_table)
    
        # 将分组框添加到父部件
        parent_widget.addWidget(mappings_group)
    
    def _create_mappings_table(self):
        """创建映射表格"""
        return StyleManager.create_standard_table(
            columns=3, 
            headers=["IP", "域名", "所属规则"],
            editable=False
        )

    def _setup_log_area(self, parent_layout):
        """设置日志记录区域"""
        # 创建日志记录分组框
        log_box = self._create_group_box("日志记录")
        
        # 创建分组框内布局
        box_layout = QVBoxLayout(log_box)
        box_layout.setContentsMargins(12, 12, 12, 12)
    
        # 创建日志文本编辑器
        self.log_text = self._create_log_text_editor()
        box_layout.addWidget(self.log_text)
        
        # 添加到父布局
        parent_layout.addWidget(log_box, stretch=1)
    
    def _create_log_text_editor(self):
        """创建优化的日志文本编辑器"""
        log_text = QTextEdit()
        log_text.setObjectName("log_text")  # 日志文本框的样式在QSS中通过ID定义
        log_text.setReadOnly(True)
        log_text.setAcceptRichText(True)  # 确保富文本渲染
        
        # 使用StyleManager中的方法应用字体和布局优化
        StyleManager.optimize_text_editor_font(log_text)
        StyleManager.optimize_text_editor_layout(log_text)
        
        return log_text
    
    def _init_tray_icon(self):
        """初始化系统托盘图标和菜单"""
        # 创建托盘图标
        self.tray_icon = QSystemTrayIcon(self)
        # 加载图标资源
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_file = os.path.join(base_path, 'resources', 'icon.ico')
        if os.path.exists(icon_file):
            self.tray_icon.setIcon(QIcon(icon_file))
        else:
            self.tray_icon.setIcon(self.windowIcon())
        self.tray_icon.setToolTip('Hosts Monitor')
        # 创建托盘菜单
        menu = QMenu()
        restore_action = QAction('显示主界面', self)
        restore_action.triggered.connect(self.showNormal)
        exit_action = QAction('退出', self)
        # 退出应用
        # 退出应用
        exit_action.triggered.connect(QApplication.quit)
        menu.addAction(restore_action)
        menu.addAction(exit_action)
        self.tray_icon.setContextMenu(menu)
        # 托盘图标激活事件
        self.tray_icon.activated.connect(self._on_tray_activated)

    def _on_tray_activated(self, reason):
        """托盘图标点击处理"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger or reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.showNormal()
            self.activateWindow()

    def changeEvent(self, a0):
        """窗口状态变化时处理最小化到托盘"""
        # 当窗口状态改变时，检查是否最小化
        if a0 is not None and a0.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized():
                # 延迟隐藏窗口，确保托盘消息正常显示
                QTimer.singleShot(0, self.hide)
                self.tray_icon.show()
                self.tray_icon.showMessage(
                    'Hosts Monitor', '已最小化到托盘',
                    QSystemTrayIcon.MessageIcon.Information, 2000
                )
        super().changeEvent(a0)

    def _refresh_mappings_table(self):
        """刷新映射表格，显示所有规则的映射"""
        from hosts_monitor.config import get_all_rules
        
        # 清空表格
        self.mappings_table.setRowCount(0)
        
        # 加载所有规则的映射
        rules = get_all_rules()
        for rule in rules:
            rule_name = rule.get('name', '')
            entries = rule.get('entries', [])
            
            for entry in entries:
                ip = entry.get('ip', '')
                domain = entry.get('domain', '')
                
                if ip and domain:
                    row = self.mappings_table.rowCount()
                    self.mappings_table.insertRow(row)
                    self.mappings_table.setItem(row, 0, QTableWidgetItem(ip))
                    self.mappings_table.setItem(row, 1, QTableWidgetItem(domain))
                    self.mappings_table.setItem(row, 2, QTableWidgetItem(rule_name))


def setup_application():
    """设置应用程序全局配置"""
    app = QApplication(sys.argv)
    
    # 应用高DPI缩放设置 - 全局只需执行一次
    StyleManager.apply_dpi_scaling()
    
    # 设置应用级文本渲染设置 - 增强针对中文的优化
    app.setDesktopSettingsAware(True)  # 使用系统字体设置
    
    # 加载自定义字体
    StyleManager.load_custom_fonts()
    
    # 应用字体设置
    StyleManager.apply_font_settings(app)
    
    return app

if __name__ == "__main__":
    """
    UI模块直接运行时的测试入口
    用于设计和预览界面，加载测试数据
    """
    app = QApplication(sys.argv)
    
    # 应用DPI缩放和StyleManager相关设置
    StyleManager.apply_dpi_scaling()
    
    # 创建并显示主窗口
    main_window = HostsMonitorUI()
    main_window.show()
    
    # 启动应用程序
    sys.exit(app.exec())