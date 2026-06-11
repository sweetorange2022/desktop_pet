# 🐱 桌面宠物 — HorseSmallNine

一个基于 **PySide6 (Qt for Python)** 的 Windows 桌面宠物应用。可爱的宠物形象常驻桌面，同时提供系统监控、健康提醒、课程表、天气预警等实用功能。

## ✨ 功能特性

### 🎮 桌面宠物
- 透明无边框窗口，可自由拖拽到桌面任意位置
- 支持 **GIF 动图**、**MP4 视频**、**静态图片** 多种资源格式
- 右键菜单快速操作，交互丰富

### 📊 系统监控
- 实时采集 **CPU 使用率**、**内存占用**、**网络速度**、**CPU 温度**
- 信息气泡自动刷新，状态阈值可配置
- 数据异常时自动变色提醒（绿 → 橙 → 红）

### 💧 健康提醒
- 工作时间定时提醒喝水、活动
- 支持 **2026 年法定节假日** 和调休日自动识别
- 下班提醒、休息日温馨提示
- 提醒内容随机轮换，避免枯燥

### 📅 课程表
- 通过 `schedule.json` 配置每周课程
- 气泡中显示当天课程安排

### 🌤 天气预警
- 基于 **Open-Meteo API** 获取天气预报（免费，无需 API Key）
- 自动检测极端高温/低温、大风、降雨等异常天气
- 支持通过城市名搜索自动配置经纬度
- 每天定时推送明日天气到微信

### 💬 微信通知
- 天气卡片自动生成并发送到指定微信联系人
- 通过 `pyautogui` 模拟操作，无需额外 API

### ⚙️ 其他
- **开机自启**：首次启动自动注册，可通过托盘菜单开关
- **系统托盘**：完整托盘菜单，支持切换信息源、退出等
- **纯配置化**：所有参数通过 `config/` 目录下的 JSON 文件管理

## 📁 项目结构

```
desktop_pet/
├── main.py                  # 应用入口，组装模块并启动事件循环
├── config.py                # 配置加载模块，从 config/*.json 读取参数
├── build.py                 # PyInstaller 打包脚本
├── requirements.txt         # Python 依赖
├── schedule.json            # 课程表配置
├── HorseSmallNine.spec      # PyInstaller spec 文件
│
├── assets/                  # 资源文件
│   ├── animated/            # GIF/APNG/WebP 动图
│   ├── generated/           # 生成的静态图片
│   ├── ico/                 # 图标文件
│   ├── images/              # 其他图片
│   └── videos/              # 视频文件
│
├── config/                  # 配置文件目录
│   ├── health.json          # 健康提醒配置
│   ├── monitor.json         # 系统监控配置
│   ├── ui.json              # UI 尺寸与样式配置
│   ├── weather.json         # 天气预警配置
│   └── wechat.json          # 微信通知配置
│
├── scripts/                 # 辅助脚本
│   ├── _autostart.py        # 开机自启管理
│   ├── _health_reminder.py  # 健康提醒逻辑
│   └── generate_assets.py   # 资源生成脚本
│
└── src/                     # 核心源码
    ├── core/                # 核心模块
    │   ├── monitor.py       # 系统资源监控
    │   └── state.py         # 状态管理
    ├── providers/           # 信息提供者（Strategy 模式）
    │   ├── base.py          # 抽象基类 InfoProvider
    │   ├── system_provider.py    # 系统监控数据
    │   ├── schedule_provider.py  # 课程表数据
    │   ├── health_provider.py    # 健康提醒数据
    │   └── weather_provider.py   # 天气数据
    ├── services/            # 外部服务
    │   ├── weather.py       # 天气 API 接口
    │   ├── weather_image.py # 天气卡片渲染
    │   ├── wechat_sender.py # 微信消息发送
    │   └── screen_recorder.py # 屏幕录制
    └── ui/                  # 界面组件
        ├── pet_window.py    # 宠物主窗口
        ├── info_bubble.py   # 信息气泡
        ├── tray_manager.py  # 系统托盘管理
        ├── weather_dialog.py # 天气详情对话框
        └── weather_image.py # 天气卡片图片生成
```

## 🚀 快速开始

### 环境要求

- **Python** 3.10+
- **Windows** 10/11

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行

```bash
python main.py
```

### 打包为 EXE

```bash
python build.py
```

打包产物输出到 `dist/HorseSmallNine.exe`，打包前会自动运行截图和录屏自检。

## ⚙️ 配置说明

所有配置文件位于 `config/` 目录，采用 JSON 格式，修改后重启生效。

### `config/monitor.json` — 系统监控

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `monitor_interval_ms` | 1000 | 采集间隔（毫秒） |
| `cpu_high_threshold` | 80.0 | CPU 告警阈值（%） |
| `memory_high_threshold` | 85.0 | 内存告警阈值（%） |
| `temp_high_threshold` | 75.0 | 温度告警阈值（°C） |

### `config/ui.json` — 界面

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `pet_size` | 120 | 宠物尺寸（像素） |
| `bubble_width` | 200 | 气泡宽度 |
| `bubble_height` | 120 | 气泡高度 |
| `color_idle` | `#4CAF50` | 正常状态颜色 |
| `color_warning` | `#FF9800` | 警告状态颜色 |
| `color_danger` | `#F44336` | 危险状态颜色 |

### `config/health.json` — 健康提醒

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `health_reminder_interval_s` | 3600 | 提醒间隔（秒） |
| `health_work_hours` | `[[9,0,12,10],[13,30,24,0]]` | 工作时间段 |
| `health_off_work_times` | `[[12,10],[18,0]]` | 下班时间点 |
| `holidays_2026` | 2026 年法定节假日 | 法定假日列表 |

### `config/weather.json` — 天气预警

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `weather_city` | 厦门 | 城市名称 |
| `weather_latitude` | 24.4798 | 纬度 |
| `weather_longitude` | 118.0894 | 经度 |
| `weather_check_hour` | 20 | 每日检查时间（小时） |
| `weather_temp_high_threshold` | 35.0 | 高温预警阈值（°C） |
| `weather_rain_prob_threshold` | 60.0 | 降雨预警阈值（%） |

### `config/wechat.json` — 微信通知

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `wechat_target_name` | Teemo | 微信联系人备注名 |
| `wechat_send_delay_s` | 0.5 | 发送延迟（秒） |

## 🏗 技术架构

```
┌─────────────────────────────────────────────────┐
│                    main.py (入口)                 │
│         组装模块 · 连接信号槽 · 启动事件循环         │
├─────────────┬───────────────┬───────────────────┤
│   UI 层     │   Core 层     │   Services 层      │
│             │               │                    │
│ PetWindow   │ SystemMonitor │ Weather API        │
│ InfoBubble  │ StateManager  │ WeChat Sender      │
│ TrayManager │               │ Screen Recorder    │
│ WeatherDlg  │               │ Weather Image      │
├─────────────┴───────────────┴───────────────────┤
│              Providers (Strategy 模式)            │
│  SystemProvider · ScheduleProvider               │
│  HealthProvider · WeatherProvider                 │
├─────────────────────────────────────────────────┤
│              config.py (JSON 配置加载)             │
└─────────────────────────────────────────────────┘
```

- **信号槽机制**：通过 Qt Signal 解耦数据采集与 UI 渲染
- **Strategy 模式**：`InfoProvider` 抽象接口，各信息源独立实现
- **配置驱动**：所有可调参数外部化为 JSON 文件

## 📦 依赖说明

| 库 | 用途 |
|----|------|
| `PySide6` | Qt 6 GUI 框架 |
| `psutil` | 系统资源监控 |
| `requests` | HTTP 请求（天气 API） |
| `pyautogui` | 自动化操作（微信发送） |
| `pyperclip` | 剪贴板操作 |
| `mss` | 屏幕截图 |
| `Pillow` | 图像处理 |

## 📝 License

本项目仅供学习和个人使用。

## 🙏 致谢

- [Open-Meteo](https://open-meteo.com/) — 免费天气 API
- [PySide6](https://wiki.qt.io/Qt_for_Python) — Qt for Python
- [psutil](https://github.com/giampaolo/psutil) — 跨平台系统监控库