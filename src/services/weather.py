"""天气数据获取模块。

使用 Open-Meteo 免费 API 获取厦门天气预报。

无需 API Key，直接通过 HTTP 请求获取 JSON 数据。

"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

import requests

from config import (
    WEATHER_CITY,
    WEATHER_LATITUDE,
    WEATHER_LONGITUDE,
    WEATHER_TEMP_CHANGE_THRESHOLD,

    WEATHER_TEMP_HIGH_THRESHOLD,

    WEATHER_TEMP_LOW_THRESHOLD,

    WEATHER_RAIN_PROB_THRESHOLD,

    WEATHER_WIND_SPEED_THRESHOLD,

)

logger = logging.getLogger(__name__)

# 城市坐标查询缓存（减少重复 API 请求）
_GEO_CACHE: dict[str, Optional[dict[str, object]]] = {}

# 国内常见城市本地兜底（Open-Meteo 不可达时仍可查询）
_CHINA_CITY_FALLBACK: dict[str, dict[str, Any]] = {
    "厦门": {"city": "厦门市", "lat": 24.4798, "lon": 118.0894, "nmc_id": "gDCDS"},
    "厦门市": {"city": "厦门市", "lat": 24.4798, "lon": 118.0894, "nmc_id": "gDCDS"},
}

_NMC_WEATHER_TO_CODE: dict[str, int] = {
    "晴": 0, "多云": 2, "阴": 3, "小雨": 61, "中雨": 63, "大雨": 65,
    "暴雨": 65, "雷阵雨": 95, "阵雨": 80, "小雪": 71, "中雪": 73, "大雪": 75,
    "雾": 45, "霾": 45,
}

_nmc_session: requests.Session | None = None
_nmc_city_index: dict[str, dict[str, Any]] | None = None

def _normalize_city_key(name: str) -> str:
    return name.strip().replace("省", "").replace("市", "")

def _local_city_lookup(city_name: str) -> Optional[dict[str, Any]]:
    """本地城市表 + config 配置兜底。"""
    key = city_name.strip()
    candidates = [key]
    if key.endswith("市"):
        candidates.append(key[:-1])
    else:
        candidates.append(key + "市")
    for cand in candidates:
        if cand in _CHINA_CITY_FALLBACK:
            return dict(_CHINA_CITY_FALLBACK[cand])
    try:
        from config import WEATHER_CITY, WEATHER_LATITUDE, WEATHER_LONGITUDE
        for cand in candidates:
            if _normalize_city_key(cand) == _normalize_city_key(WEATHER_CITY):
                local = _CHINA_CITY_FALLBACK.get(WEATHER_CITY) or _CHINA_CITY_FALLBACK.get(
                    _normalize_city_key(WEATHER_CITY), {}
                )
                return {
                    "city": WEATHER_CITY,
                    "lat": WEATHER_LATITUDE,
                    "lon": WEATHER_LONGITUDE,
                    "nmc_id": local.get("nmc_id"),
                }
    except Exception:
        pass
    return None

def _http_get_json(
    url: str,
    params: dict | None = None,
    *,
    timeout: int = 12,
    retries: int = 2,
    headers: dict | None = None,
) -> Optional[dict]:
    hdrs = {"User-Agent": "HorseSmallNine/1.0"}
    if headers:
        hdrs.update(headers)
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=hdrs, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            last_err = exc
            time.sleep(0.4 * (attempt + 1))
    if last_err:
        logger.debug("HTTP 请求失败 %s: %s", url, last_err)
    return None

def _nmc_session_get() -> requests.Session:
    global _nmc_session
    if _nmc_session is None:
        _nmc_session = requests.Session()
        _nmc_session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "http://www.nmc.cn/",
            "Accept": "application/json",
        })
        try:
            _nmc_session.get("http://www.nmc.cn/", timeout=10)
        except Exception:
            pass
    return _nmc_session

def _nmc_build_city_index() -> dict[str, dict[str, Any]]:
    global _nmc_city_index
    if _nmc_city_index is not None:
        return _nmc_city_index
    index: dict[str, dict[str, Any]] = {}
    session = _nmc_session_get()
    try:
        provinces = session.get("http://www.nmc.cn/rest/province/all", timeout=15).json()
        for prov in provinces:
            pcode = prov.get("code")
            if not pcode:
                continue
            try:
                cities = session.get(f"http://www.nmc.cn/rest/province/{pcode}", timeout=15).json()
            except Exception:
                continue
            if not isinstance(cities, list):
                continue
            for item in cities:
                cname = str(item.get("city", "")).strip()
                sid = item.get("code")
                if not cname or not sid:
                    continue
                entry = {
                    "city": cname if cname.endswith("市") else cname,
                    "nmc_id": sid,
                    "province": item.get("province", ""),
                }
                index[cname] = entry
                index[_normalize_city_key(cname)] = entry
                if not cname.endswith("市"):
                    index[cname + "市"] = entry
    except Exception as exc:
        logger.warning("构建 NMC 城市索引失败: %s", exc)
    _nmc_city_index = index
    return index

def _nmc_find_station(city_name: str) -> Optional[str]:
    local = _local_city_lookup(city_name)
    if local and local.get("nmc_id"):
        return local["nmc_id"]
    index = _nmc_build_city_index()
    for key in (city_name.strip(), _normalize_city_key(city_name), city_name.strip() + "市"):
        hit = index.get(key)
        if hit:
            return hit.get("nmc_id")
    return None

def _nmc_fetch_raw(station_id: str) -> Optional[dict]:
    session = _nmc_session_get()
    try:
        resp = session.get(
            "http://www.nmc.cn/rest/weather",
            params={"stationid": station_id, "_": int(time.time() * 1000)},
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        data = payload.get("data")
        if not data:
            return None
        if isinstance(data, str):
            data = json.loads(data) if data else None
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.warning("NMC 天气请求失败: %s", exc)
        return None

def _nmc_temp_value(block: dict) -> Optional[float]:
    raw = block.get("weather", {}).get("temperature", "9999")
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    return val if val < 9000 else None

def _nmc_detail_to_day(entry: dict) -> DayWeather:
    day = entry.get("day", {})
    night = entry.get("night", {})
    t_day = _nmc_temp_value(day)
    t_night = _nmc_temp_value(night)
    temps = [t for t in (t_day, t_night) if t is not None]
    temp_max = max(temps) if temps else 0.0
    temp_min = min(temps) if temps else 0.0
    desc_day = str(day.get("weather", {}).get("info", ""))
    desc_night = str(night.get("weather", {}).get("info", ""))
    desc = desc_day if desc_day and desc_day != "9999" else desc_night
    if not desc or desc == "9999":
        desc = "阴"
    precip = float(entry.get("precipitation") or 0)
    rain_prob = 70.0 if "雨" in desc or "雪" in desc else (40.0 if precip > 0 else 10.0)
    return DayWeather(
        date=entry.get("date", ""),
        temp_max=temp_max,
        temp_min=temp_min,
        rain_prob_max=rain_prob,
        wind_speed_max=0.0,
        weather_code=_NMC_WEATHER_TO_CODE.get(desc, 3),
        weather_desc=desc,
    )

def fetch_day_weather_by_nmc(station_id: str, day_offset: int = 0) -> Optional[DayWeather]:
    raw = _nmc_fetch_raw(station_id)
    if raw is None:
        return None
    details = raw.get("predict", {}).get("detail", [])
    if not details or len(details) <= day_offset:
        return None
    return _nmc_detail_to_day(details[day_offset])

def fetch_weather_dialog_detail_nmc(station_id: str, day_offset: int = 0) -> Optional[dict]:
    dw = fetch_day_weather_by_nmc(station_id, day_offset)
    if dw is None:
        return None
    return {
        "date": dw.date,
        "temp_min": dw.temp_min,
        "temp_max": dw.temp_max,
        "wind_speed_max": dw.wind_speed_max,
        "weather_code": dw.weather_code,
        "weather_desc": dw.weather_desc,
        "uv_index_max": 0,
        "rain_periods": [],
        "commute_morning": False,
        "commute_evening": False,
    }

def _fetch_open_meteo_day(lat: float, lon: float, day_offset: int) -> Optional[DayWeather]:
    data = _http_get_json(
        "https://api.open-meteo.com/v1/forecast",
        {
            "latitude": lat,
            "longitude": lon,
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_probability_max",
                "wind_speed_10m_max",
                "weather_code",
            ],
            "timezone": "Asia/Shanghai",
            "forecast_days": day_offset + 1,
        },
    )
    if data is None:
        return None
    daily = data.get("daily", {})
    dates = daily.get("time", [])
    if len(dates) <= day_offset:
        return None
    i = day_offset
    return DayWeather(
        date=dates[i],
        temp_max=daily["temperature_2m_max"][i],
        temp_min=daily["temperature_2m_min"][i],
        rain_prob_max=daily["precipitation_probability_max"][i] or 0,
        wind_speed_max=daily["wind_speed_10m_max"][i] or 0,
        weather_code=daily["weather_code"][i],
        weather_desc=_weather_desc(daily["weather_code"][i]),
    )

def fetch_day_weather(
    lat: float,
    lon: float,
    day_offset: int = 0,
    nmc_id: str | None = None,
) -> Optional[DayWeather]:
    """按坐标获取天气，Open-Meteo 失败时回退中央气象台。"""
    got = _fetch_open_meteo_day(lat, lon, day_offset)
    if got is not None:
        return got
    sid = nmc_id or _nmc_find_station(WEATHER_CITY)
    if sid:
        return fetch_day_weather_by_nmc(sid, day_offset)
    return None

def geo_lookup(city_name: str) -> Optional[dict[str, object]]:
    """查询城市坐标。优先本地/config，其次 Open-Meteo，最后中央气象台索引。"""
    key = city_name.strip()
    if key in _GEO_CACHE:
        return _GEO_CACHE[key]

    local = _local_city_lookup(key)
    if local is not None:
        _GEO_CACHE[key] = local
        return local

    search_names = [key]
    if key.endswith("市"):
        search_names.append(key[:-1])
    else:
        search_names.append(key + "市")

    for name in search_names:
        data = _http_get_json(
            "https://geocoding-api.open-meteo.com/v1/search",
            {"name": name, "count": 1, "language": "zh", "format": "json", "country_code": "CN"},
        )
        if data is None:
            data = _http_get_json(
                "https://geocoding-api.open-meteo.com/v1/search",
                {"name": name, "count": 1, "language": "zh", "format": "json"},
            )
        results = (data or {}).get("results", [])
        if results:
            r = results[0]
            result: dict[str, object] = {
                "city": r.get("name", key),
                "lat": r["latitude"],
                "lon": r["longitude"],
            }
            nmc_id = _nmc_find_station(str(result["city"]))
            if nmc_id:
                result["nmc_id"] = nmc_id
            _GEO_CACHE[key] = result
            return result

    nmc_id = _nmc_find_station(key)
    if nmc_id:
        index = _nmc_build_city_index()
        hit = index.get(key) or index.get(_normalize_city_key(key)) or index.get(key + "市")
        result = {
            "city": hit["city"] if hit else key,
            "lat": WEATHER_LATITUDE,
            "lon": WEATHER_LONGITUDE,
            "nmc_id": nmc_id,
        }
        if local := _local_city_lookup(key):
            result["lat"] = local["lat"]
            result["lon"] = local["lon"]
        _GEO_CACHE[key] = result
        return result

    logger.warning("未找到城市: %s", key)
    return None

def geo_search(city_name: str, count: int = 5) -> list[dict[str, object]]:

    """搜索城市，返回多个匹配结果供下拉列表使用。

    Args:

        city_name: 城市名称，如"南京"

        count: 最大返回结果数

    Returns:

        列表，每项 {"city": str, "lat": float, "lon": float, "admin1": str, "country": str}

    """

    try:

        url = "https://geocoding-api.open-meteo.com/v1/search"

        params = {"name": city_name, "count": count, "language": "zh", "format": "json", "country_code": "CN"}

        resp = requests.get(url, params=params, timeout=10)

        resp.raise_for_status()

        data = resp.json()

        results = data.get("results", [])

        # Open-Meteo API 对部分中文城市名（如"厦门"）不返回结果，

        # 但会返回"厦门市"的结果。尝试添加"市"后缀兜底。

        if not results and not city_name.endswith("市"):

            params["name"] = city_name + "市"

            resp = requests.get(url, params=params, timeout=10)

            resp.raise_for_status()

            data = resp.json()

            results = data.get("results", [])

        elif not results and city_name.endswith("市"):

            params["name"] = city_name[:-1]

            resp = requests.get(url, params=params, timeout=10)

            resp.raise_for_status()

            data = resp.json()

            results = data.get("results", [])

        return [

            {

                "city": r.get("name", ""),

                "lat": r["latitude"],

                "lon": r["longitude"],

                "admin1": r.get("admin1", ""),

                "country": r.get("country", ""),

            }

            for r in results

        ]

    except Exception as e:

        logger.warning("城市搜索失败: %s", e)

        return []

@dataclass

class DayWeather:

    """单日天气数据。"""

    date: str                   # 日期 (YYYY-MM-DD)

    temp_max: float             # 最高温 (°C)

    temp_min: float             # 最低温 (°C)

    rain_prob_max: float        # 最大降雨概率 (%)

    wind_speed_max: float       # 最大风速 (km/h)

    weather_code: int           # 天气代码

    weather_desc: str           # 天气描述

    @property

    def temp_range_str(self) -> str:

        return f"{self.temp_min:.0f}~{self.temp_max:.0f}°C"

# WMO 天气代码映射

_WMO_CODES: dict[int, str] = {

    0: "晴",

    1: "晴间多云",

    2: "多云",

    3: "阴天",

    45: "雾",

    48: "雾凇",

    51: "小毛毛雨",

    53: "毛毛雨",

    55: "大毛毛雨",

    61: "小雨",

    63: "中雨",

    65: "大雨",

    66: "冻雨(小)",

    67: "冻雨(大)",

    71: "小雪",

    73: "中雪",

    75: "大雪",

    77: "雪粒",

    80: "小阵雨",

    81: "阵雨",

    82: "大阵雨",

    85: "小阵雪",

    86: "大阵雪",

    95: "雷暴",

    96: "雷暴+小冰雹",

    99: "雷暴+大冰雹",

}

def _weather_desc(code: int) -> str:

    return _WMO_CODES.get(code, f"未知({code})")

def fetch_tomorrow_weather() -> Optional[DayWeather]:
    """获取明天的天气预报。"""
    local = _local_city_lookup(WEATHER_CITY) or {}
    nmc_id = local.get("nmc_id")
    got = fetch_day_weather(WEATHER_LATITUDE, WEATHER_LONGITUDE, day_offset=1, nmc_id=nmc_id)
    if got is None:
        logger.warning("获取明天天气失败: %s", WEATHER_CITY)
    return got

def fetch_today_weather() -> Optional[DayWeather]:
    """获取今天的天气预报（用于对比温差）。"""
    local = _local_city_lookup(WEATHER_CITY) or {}
    nmc_id = local.get("nmc_id")
    got = fetch_day_weather(WEATHER_LATITUDE, WEATHER_LONGITUDE, day_offset=0, nmc_id=nmc_id)
    if got is None:
        logger.warning("获取今天天气失败: %s", WEATHER_CITY)
    return got

@dataclass

class WeatherAlert:

    """天气预警信息。"""

    alerts: list[str]       # 预警原因列表

    summary: str            # 摘要消息

    full_message: str       # 完整消息（用于微信发送）

    @property

    def has_alert(self) -> bool:

        return len(self.alerts) > 0

def check_weather_alert(
    tomorrow: DayWeather,
    today: Optional[DayWeather] = None,
) -> WeatherAlert:
    """根据天气数据判断是否需要预警。

    Args:
        tomorrow: 明日天气数据
        today: 今日天气数据，可选，用于温差对比

    Returns:
        WeatherAlert 对象
    """
    alerts: list[str] = []

    # 高温预警
    if tomorrow.temp_max >= WEATHER_TEMP_HIGH_THRESHOLD:
        alerts.append(f"高温 {tomorrow.temp_max:.0f}℃")

    # 低温预警
    if tomorrow.temp_min <= WEATHER_TEMP_LOW_THRESHOLD:
        alerts.append(f"低温 {tomorrow.temp_min:.0f}℃")

    # 温差变化预警
    if today is not None:
        temp_diff_high = tomorrow.temp_max - today.temp_max
        temp_diff_low = tomorrow.temp_min - today.temp_min
        if abs(temp_diff_high) >= WEATHER_TEMP_CHANGE_THRESHOLD:
            direction = "升温" if temp_diff_high > 0 else "降温"
            alerts.append(f"{direction} {abs(temp_diff_high):.0f}℃（最高温）")
        if abs(temp_diff_low) >= WEATHER_TEMP_CHANGE_THRESHOLD:
            direction = "升温" if temp_diff_low > 0 else "降温"
            alerts.append(f"{direction} {abs(temp_diff_low):.0f}℃（最低温）")

    # 降雨预警
    if tomorrow.rain_prob_max >= WEATHER_RAIN_PROB_THRESHOLD:
        alerts.append(f"降雨概率 {tomorrow.rain_prob_max:.0f}%")

    # 大风预警
    if tomorrow.wind_speed_max >= WEATHER_WIND_SPEED_THRESHOLD:
        alerts.append(f"大风 {tomorrow.wind_speed_max:.0f}km/h")

    # 恶劣天气预警
    bad_weather_codes = {61, 63, 65, 66, 67, 71, 73, 75, 77, 95, 96, 99}
    if tomorrow.weather_code in bad_weather_codes:
        alerts.append(f"{tomorrow.weather_desc}")

    # 构建消息
    date_str = tomorrow.date
    weather_info = f"{tomorrow.weather_desc} {tomorrow.temp_range_str}"

    if alerts:
        summary = f"明天有天气异常：{'；'.join(alerts)}"
        alert_items = '；'.join(alerts)
        full_message = (
            f"明日厦门天气预警\n"
            f"日期: {date_str}\n"
            f"天气: {weather_info}\n"
            f"风速: {tomorrow.wind_speed_max:.0f}km/h\n"
            f"预警: {alert_items}\n"
            f"注意做好防护哦~"
        )
    else:
        summary = f"明天天气正常：{weather_info}"
        full_message = f"明日厦门天气正常：{weather_info}，无需特别防护。"

    return WeatherAlert(
        alerts=alerts,
        summary=summary,
        full_message=full_message,
    )
