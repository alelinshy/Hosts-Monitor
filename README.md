# Hosts Monitor

Hosts Monitor 是一个用于监控和自动修复 Windows hosts 文件的工具。当检测到 hosts 文件内容发生变化或丢失时，会自动将指定的内容写入 hosts 文件。

## 功能特点

- 实时监控 hosts 文件变化
- 自动修复缺失的 hosts 记录
- 支持开机自启动
- 支持最小化到系统托盘
- 支持以管理员权限运行
- 用户友好的界面

## 系统要求

- Windows 10/11
- Python 3.8 或更高版本（如果使用源码运行）

## 安装方式

### 方式1：使用预编译的可执行文件

1. 从 Releases 页面下载最新的 `Hosts Monitor.exe`
2. 双击运行即可，首次运行时建议使用管理员权限

### 方式2：从源码运行

1. 克隆代码仓库
2. 安装依赖：`pip install -r requirements.txt`
3. 运行程序：`python run.py`

## 使用说明

1. 在主界面中，点击"以管理员权限运行"按钮获取管理员权限
2. 在中间的文本框中编辑需要保持的 hosts 内容
3. 点击"保存配置"按钮保存设置
4. 程序会自动监控 hosts 文件，并在需要时进行修复

## 配置说明

配置文件 `hosts_monitor.toml` 会自动创建在程序所在目录，包含以下设置：

- `auto_start`：是否开机自启动
- `run_as_admin`：是否以管理员权限运行
- `delay_time`：检测到变化后延迟修复的时间（毫秒）
- `minimize_to_tray`：是否最小化到系统托盘
- `hosts.data`：需要保持的 hosts 内容

## 开发者信息

使用了以下主要技术:

- Python 3.8+
- PyQt6 
- watchfiles
- pywin32
- toml
- PyInstaller
