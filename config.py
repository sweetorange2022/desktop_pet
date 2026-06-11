"""应用常量配置。

从 config/ 目录下的 JSON 文件加载配置。
如外部文件缺失或无法读取，自动使用内置默认值。
Phase 2 扩展时新增常量即可，无需修改业务逻辑。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 配置文件目录
# ---------------------------------------------------------------------------
_CONFIG_DIR = Path(__file__).parent / "config"

def _load_json(filename: str, default: dict | None = None) -> dict:
    """从 config/ 目录加载 JSON 配置文件，失败时返回默认值。"""
    path = _CONFIG_DIR / filename
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        if path.exists():
            print(f"[config] 读取 {path} 失败: {e}，使用默认值", file=sys.stderr)
        return default or {}

# ===========================================================================
# 监控采集  (config/monitor.json)
# ===========================================================================
_monitor = _load_json("monitor.json")

MONITOR_INTERVAL_MS: int = _monitor.get("monitor_interval_ms", 1000)
NETWORK_SAMPLE_INTERVAL_S: float = _monitor.get("network_sample_interval_s", 1.0)

# 状态阈值
CPU_HIGH_THRESHOLD: float = _monitor.get("cpu_high_threshold", 80.0)
MEMORY_HIGH_THRESHOLD: float = _monitor.get("memory_high_threshold", 85.0)
TEMP_HIGH_THRESHOLD: float = _monitor.get("temp_high_threshold", 75.0)
NET_HIGH_THRESHOLD_KB: float = _monitor.get("net_high_threshold_kb", 1024.0)

# 显示标签
CPU_LABEL: str = _monitor.get("cpu_label", "CPU")
MEMORY_LABEL: str = _monitor.get("memory_label", "内存")
NETWORK_DOWN_LABEL: str = _monitor.get("network_down_label", "网络")
NETWORK_UP_LABEL: str = _monitor.get("network_up_label", "")
NETWORK_UNIT_KB: str = _monitor.get("network_unit_kb", "KB/s")
NETWORK_UNIT_MB: str = _monitor.get("network_unit_mb", "MB/s")
MEMORY_UNIT: str = _monitor.get("memory_unit", "GB")
DEFAULT_VALUE: str = _monitor.get("default_value", "--")

# ===========================================================================
# UI 尺寸 & 样式  (config/ui.json)
# ===========================================================================
_ui = _load_json("ui.json")

PET_SIZE: int = _ui.get("pet_size", 120)
BUBBLE_WIDTH: int = _ui.get("bubble_width", 200)
BUBBLE_HEIGHT: int = _ui.get("bubble_height", 120)
BUBBLE_MARGIN: int = _ui.get("bubble_margin", 0)
BUBBLE_AUTO_HIDE_MS: int = _ui.get("bubble_auto_hide_ms", 5000)

# 状态颜色（十六进制）
COLOR_IDLE: str = _ui.get("color_idle", "#4CAF50")
COLOR_WARNING: str = _ui.get("color_warning", "#FF9800")
COLOR_DANGER: str = _ui.get("color_danger", "#F44336")

# 屏幕边距
SCREEN_MARGIN_RIGHT: int = _ui.get("screen_margin_right", 30)
SCREEN_MARGIN_BOTTOM: int = _ui.get("screen_margin_bottom", 30)

# 应用名称
APP_NAME: str = _ui.get("app_name", "桌面宠物")

# 信息源
DEFAULT_SOURCE: str = _ui.get("default_source", "纯净模式")
SOURCE_NAMES: list[str] = _ui.get("source_names", ["纯净模式", "系统监控", "课程表", "健康提醒", "天气预警"])

# 气泡 QSS 样式
_BUBBLE_STYLE_DEFAULT = """
    QWidget#info_bubble {
        background-color: rgba(20, 20, 20, 230);
        border: 1px solid rgba(255, 255, 255, 80);
        border-radius: 12px;
    }
    QLabel {
        color: #F0F0F0;
        font-family: "Microsoft YaHei", "Consolas", "Segoe UI", sans-serif;
        font-size: 13px;
        font-weight: bold;
        letter-spacing: 1px;
    }
"""
BUBBLE_STYLE: str = _ui.get("bubble_style", _BUBBLE_STYLE_DEFAULT)

# ===========================================================================
# 健康提醒  (config/health.json)
# ===========================================================================
_health = _load_json("health.json")

HEALTH_REMINDER_INTERVAL_S: int = _health.get("health_reminder_interval_s", 3600)
HEALTH_WORK_HOURS: list[tuple[int, int, int, int]] = [
    tuple(item) for item in _health.get("health_work_hours", [
        [9, 0, 12, 10],
        [13, 30, 24, 0],
    ])
]
HEALTH_REMINDER_TITLE: str = _health.get("health_reminder_title", "健康提醒")
HEALTH_REMINDER_MSG: str = _health.get("health_reminder_msg", "辛苦了，喝点水动一下吧~")

HEALTH_OFF_WORK_TIMES: list[tuple[int, int]] = [
    tuple(item) for item in _health.get("health_off_work_times", [
        [12, 10],
        [18, 0],
    ])
]

HEALTH_ENCOURAGEMENTS: list[str] = _health.get("health_encouragements", [
    "加油，坚持就是胜利！",
    "专注工作，也要照顾好自己~",
    "今天也是元气满满的一天！",
    "忙里偷闲，喝杯水休息下~",
    "努力的你最棒！",
    "保持节奏，别太累了~",
    "工作再忙也要动一动哦！",
    "距离下班又近了一步！",
])

# 非工作时间温馨提示
REST_DAY_TIPS: list[str] = _health.get("rest_day_tips", [
    "今天是休息日，好好放松~",
    "休息是为了更好地出发！",
    "享受悠闲时光吧~",
    "记得出去走走哦~",
])

NON_WORK_HOURS_TIPS: list[str] = _health.get("non_work_hours_tips", [
    "夜深了，好好休息~",
    "辛苦了一天，早点休息吧~",
    "明天也要元气满满哦~",
    "晚安，好梦~",
])

BEFORE_WORK_TIPS: list[str] = _health.get("before_work_tips", [
    "新的一天，加油！",
    "今天也要开心工作~",
    "早安，准备好迎接新的一天了吗？",
])

OFF_WORK_TIPS: list[str] = _health.get("off_work_tips", [
    "今天辛苦了~",
    "下班啦，好好享受自由时光！",
    "辛苦了一天，犒劳一下自己吧~",
])

HOLIDAYS_2026: set[tuple[int, int]] = {
    tuple(item) for item in _health.get("holidays_2026", [
        [1, 1], [1, 2], [1, 3],
        [2, 17], [2, 18], [2, 19], [2, 20], [2, 21], [2, 22], [2, 23],
        [4, 4], [4, 5], [4, 6],
        [5, 1], [5, 2], [5, 3], [5, 4], [5, 5],
        [6, 19], [6, 20], [6, 21],
        [10, 1], [10, 2], [10, 3], [10, 4], [10, 5], [10, 6], [10, 7],
        [10, 8],
    ])
}

WORKDAYS_EXTRA_2026: set[tuple[int, int]] = {
    tuple(item) for item in _health.get("workdays_extra_2026", [
        [1, 4],
        [2, 15],
        [2, 28],
        [4, 26],
        [5, 9],
        [10, 10],
    ])
}

# ===========================================================================
# 天气预警  (config/weather.json)
# ===========================================================================
_weather = _load_json("weather.json")

WEATHER_CITY: str = _weather.get("weather_city", "厦门")
WEATHER_LATITUDE: float = _weather.get("weather_latitude", 24.4798)
WEATHER_LONGITUDE: float = _weather.get("weather_longitude", 118.0894)
WEATHER_CHECK_HOUR: int = _weather.get("weather_check_hour", 20)
WEATHER_TEMP_HIGH_THRESHOLD: float = _weather.get("weather_temp_high_threshold", 35.0)
WEATHER_TEMP_LOW_THRESHOLD: float = _weather.get("weather_temp_low_threshold", 5.0)
WEATHER_TEMP_CHANGE_THRESHOLD: float = _weather.get("weather_temp_change_threshold", 10.0)
WEATHER_RAIN_PROB_THRESHOLD: float = _weather.get("weather_rain_prob_threshold", 60.0)
WEATHER_WIND_SPEED_THRESHOLD: float = _weather.get("weather_wind_speed_threshold", 50.0)
WEATHER_CHECK_INTERVAL_MS: int = _weather.get("weather_check_interval_ms", 60000)
WEATHER_ALERT_TITLE: str = _weather.get("weather_alert_title", "天气预警")
WEATHER_ALERT_FORMAT: str = _weather.get("weather_alert_format", "🌤 明日{city}天气预警\n📅 {date}\n🌡 {weather_info}\n🌧 降雨概率: {rain_prob}%\n💨 风速: {wind_speed}km/h\n⚠️ {alerts}\n注意做好防护哦~")
WEATHER_NORMAL_FORMAT: str = _weather.get("weather_normal_format", "明天{city}天气正常：{weather_info}，无需特别防护。")
WEATHER_NORMAL_SUMMARY: str = _weather.get("weather_normal_summary", "明天天气正常：{weather_info}")
WEATHER_ALERT_SUMMARY: str = _weather.get("weather_alert_summary", "明天有天气异常：{alerts}")
WEATHER_NORMAL_STATUS: str = _weather.get("weather_normal_status", "天气获取失败")
WEATHER_CHECKING_STATUS: str = _weather.get("weather_checking_status", "正在检查天气...")
WEATHER_WAIT_STATUS: str = _weather.get("weather_wait_status", "等待检查...")
BAD_WEATHER_CODES: set[int] = set(_weather.get("bad_weather_codes", [61, 63, 65, 66, 67, 71, 73, 75, 77, 95, 96, 99]))

# ===========================================================================
# 微信通知  (config/wechat.json)
# ===========================================================================
_wechat = _load_json("wechat.json")

WECHAT_TARGET_NAME: str = _wechat.get("wechat_target_name", "Teemo")
WECHAT_WINDOW_CLASSES: list[str] = _wechat.get("wechat_window_classes", [
    "WeChatMainWndForPC", "WeixinMainWndForPC", "Qt51514QWindowIcon",
])
WECHAT_SEARCH_TITLE: str = _wechat.get("wechat_search_title", "微信")
WECHAT_SEND_DELAY_S: float = _wechat.get("wechat_send_delay_s", 0.5)
WECHAT_SEARCH_DELAY_S: float = _wechat.get("wechat_search_delay_s", 1.0)
WECHAT_SELECT_DELAY_S: float = _wechat.get("wechat_select_delay_s", 1.5)
WECHAT_TYPE_DELAY_S: float = _wechat.get("wechat_type_delay_s", 0.3)
WECHAT_ACTIVATE_DELAY_S: float = _wechat.get("wechat_activate_delay_s", 0.3)
WECHAT_LOG_FILE: str = _wechat.get("wechat_log_file", "_wechat_debug.log")
WECHAT_MINIMIZE_AFTER_SEND: bool = _wechat.get("wechat_minimize_after_send", True)
WECHAT_RESTORE_FOREGROUND: bool = _wechat.get("wechat_restore_foreground", True)
