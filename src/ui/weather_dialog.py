"""天气查询与发送对话框。

点击"天气预报"菜单项弹出，可设置城市和微信好友，

自动查询天气并生成可编辑的卡片，确认后发送微信。

"""

from __future__ import annotations

import logging

import os

from datetime import datetime

from typing import Optional

from PySide6.QtCore import Qt, QTimer

from PySide6.QtGui import QTextCursor

from PySide6.QtWidgets import (

    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,

    QPushButton, QTextEdit, QMessageBox, QApplication,

)

from config import WEATHER_CITY, WEATHER_LATITUDE, WEATHER_LONGITUDE

from src.services.weather import fetch_today_weather, fetch_tomorrow_weather, geo_lookup, geo_search

from src.services.wechat_sender import send_wechat_message, send_wechat_image

class WeatherDialog(QDialog):

    """天气卡片对话框。"""

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setWindowTitle("天气预报")

        self.setMinimumSize(420, 500)

        self.setup_ui()

        self._city = WEATHER_CITY

        self._target = "楚楚大魔王(懒羊羊版)"

        # 智能搜索防抖定时器

        self._search_timer = QTimer(self)

        self._search_timer.setSingleShot(True)

        self._search_timer.timeout.connect(self._on_search_timeout)

        # 打开对话框后自动查询默认城市

        QTimer.singleShot(0, self.on_query)

    def setup_ui(self):

        layout = QVBoxLayout(self)

        layout.setSpacing(10)

        # 城市

        city_row = QHBoxLayout()

        city_row.addWidget(QLabel("城市："))

        self.city_input = QLineEdit(WEATHER_CITY)

        self.city_input.textChanged.connect(self._on_city_changed)

        city_row.addWidget(self.city_input)

        # 搜索防抖

        # 用户从下拉列表选择

        layout.addLayout(city_row)

        # 微信好友

        friend_row = QHBoxLayout()

        friend_row.addWidget(QLabel("发送给："))

        self.friend_input = QLineEdit("Teemo")

        friend_row.addWidget(self.friend_input)

        layout.addLayout(friend_row)

        # 查询按钮

        self.query_btn = QPushButton("查询天气")

        self.query_btn.clicked.connect(self.on_query)

        layout.addWidget(self.query_btn)

        # 结果卡片（可编辑）

        self.result_edit = QTextEdit()

        self.result_edit.setPlaceholderText('点击[查询天气]获取结果...')

        self.result_edit.setStyleSheet(

            "QTextEdit { background: #1e1e2e; color: #cdd6f4; "

            "border: 1px solid #45475a; border-radius: 6px; "

            "padding: 10px; font-size: 14px; }"

        )

        layout.addWidget(self.result_edit)

        # 发送按钮

        btn_row = QHBoxLayout()

        self.send_btn = QPushButton("发送微信")

        self.send_btn.clicked.connect(self.on_send)

        self.send_btn.setEnabled(False)

        btn_row.addWidget(self.send_btn)

        cancel_btn = QPushButton("取消")

        cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

    def _do_query(self, city: str):
        """核心查询逻辑（查坐标->查天气->显示结果），不涉及按钮状态。"""

        result = geo_lookup(city)

        if result is None:

            return None

        lat, lon = result["lat"], result["lon"]
        nmc_id = result.get("nmc_id")
        city_name = result["city"]
        self._city = city_name

        now = datetime.now()
        hour = now.hour
        if hour < 8:
            weather = self._fetch_weather(lat, lon, day_offset=0, nmc_id=nmc_id)
            label = "今天"
        elif hour < 16:
            weather = self._fetch_weather(lat, lon, day_offset=0, nmc_id=nmc_id)
            label = "今天"
        else:
            weather = self._fetch_weather(lat, lon, day_offset=1, nmc_id=nmc_id)
            label = "明天"

        if weather is None:

            return None

        card = self._build_card(city_name, label, weather)

        self.result_edit.setText(card)

        # 页脚右对齐
        _c = self.result_edit.textCursor()
        _c.movePosition(QTextCursor.End)
        _c.select(QTextCursor.BlockUnderCursor)
        _fmt = _c.blockFormat()
        _fmt.setAlignment(Qt.AlignRight)
        _c.setBlockFormat(_fmt)
        self.result_edit.setTextCursor(_c)

        self.send_btn.setEnabled(True)

        return city_name, label, weather

    def on_query(self):
        """点击「查询天气」按钮触发。"""

        city = self.city_input.text().strip()

        if not city:

            QMessageBox.warning(self, "提示", "请输入城市名称")

            return

        self.query_btn.setEnabled(False)

        self.query_btn.setText("查询中...")

        QApplication.processEvents()

        result_triple = self._do_query(city)

        self.query_btn.setEnabled(True)

        if result_triple is None:

            QMessageBox.warning(self, "查询失败", f"未找到城市「{city}」或天气数据获取失败")

            self.query_btn.setText("查询天气")

            return

        self.query_btn.setText("重新查询")

    def _on_city_changed(self, text: str):
        """用户修改城市输入时，启动防抖定时器。"""

        if text.strip():

            self._search_timer.start(400)

        else:

            # 清空输入时停掉定时器

            self._search_timer.stop()

    def _on_search_timeout(self):
        """防抖超时后，检查城市名称是否唯一，唯一则自动查询。"""

        text = self.city_input.text().strip()

        if len(text) < 2:
            # 太短不查（排除"南"这种可能匹配多个城市的单字）
            return

        from src.services.weather import geo_search

        results = geo_search(text, count=3)

        if len(results) == 1:
            # 唯一匹配，自动查询
            r = results[0]
            self._do_query(r["city"])
            return

        if len(results) == 0 and not text.endswith("市"):
            # 无匹配，尝试加"市"再搜一次
            results = geo_search(text + "市", count=3)
            if len(results) == 1:
                r = results[0]
                self._do_query(r["city"])
                return

        # 多个结果或无结果——什么都不做，等待用户继续输入

    def _fetch_weather(
        self,
        lat: float,
        lon: float,
        day_offset: int = 0,
        nmc_id: str | None = None,
    ):
        """获取指定偏移的天气数据（只关注 7:00-22:00）。"""

        import requests

        from src.services.weather import DayWeather, _weather_desc, fetch_weather_dialog_detail_nmc

        url = "https://api.open-meteo.com/v1/forecast"

        params = {

            "latitude": lat,

            "longitude": lon,

            "daily": [

                "temperature_2m_max", "temperature_2m_min",

                "precipitation_probability_max",

                "wind_speed_10m_max", "weather_code",

                "uv_index_max",

            ],

            "hourly": [

                "temperature_2m",

                "precipitation_probability",

                "weather_code",

            ],

            "timezone": "Asia/Shanghai",

            "forecast_days": day_offset + 1,

        }

        try:

            resp = requests.get(url, params=params, timeout=10)

            resp.raise_for_status()

            data = resp.json()

            daily = data.get("daily", {})

            dates = daily.get("time", [])

            if not dates or len(dates) <= day_offset:
                raise ValueError("Open-Meteo 返回数据为空")

            i = day_offset

            offset_h = day_offset * 24

            hourly = data.get("hourly", {})

            hourly_times = hourly.get("time", [])

            probs = hourly.get("precipitation_probability", [])

            codes = hourly.get("weather_code", [])

            temps = hourly.get("temperature_2m", [])

            # 只关注 7:00-22:00
            h_start, h_end = 7, 22

            # 温度范围（7-22 点的小时温度）
            day_temps = []

            for h in range(h_start, h_end + 1):
                ti = offset_h + h
                if ti < len(temps) and temps[ti] is not None:
                    day_temps.append(temps[ti])

            temp_min = min(day_temps) if day_temps else daily["temperature_2m_min"][i]

            temp_max = max(day_temps) if day_temps else daily["temperature_2m_max"][i]

            # 主要天气描述（7-22 点出现最多的天气码）
            day_codes = []

            for h in range(h_start, h_end + 1):
                ti = offset_h + h
                if ti < len(codes) and codes[ti] is not None:
                    day_codes.append(codes[ti])

            if day_codes:
                main_code = max(set(day_codes), key=day_codes.count)
            else:
                main_code = daily["weather_code"][i]

            weather_desc = _weather_desc(main_code)

            # 风速
            wind_speed = daily["wind_speed_10m_max"][i] or 0

            # 紫外线
            uv = daily.get("uv_index_max", [0])[i] or 0

            # 逐小时分析降水时段
            rain_periods = []

            in_rain = False

            rain_start = None

            rain_probs = []

            for h in range(h_start, h_end + 1):
                ti = offset_h + h
                if ti < len(probs) and ti < len(codes):
                    prob = probs[ti] or 0
                    code = codes[ti] or 0
                    is_rainy = code in {61, 63, 65, 66, 67, 80, 81, 82} or prob >= 50

                    if is_rainy and not in_rain:
                        in_rain = True
                        rain_start = h
                        rain_probs = [prob]
                    elif is_rainy and in_rain:
                        rain_probs.append(prob)
                    elif not is_rainy and in_rain:
                        rain_periods.append({
                            "start": rain_start,
                            "end": h - 1,
                            "prob": max(rain_probs),
                        })
                        in_rain = False
                        rain_probs = []

            if in_rain:
                rain_periods.append({
                    "start": rain_start,
                    "end": h_end,
                    "prob": max(rain_probs),
                })

            # 出行时间检查
            commute_morning = False

            commute_evening = False

            for rp in rain_periods:
                if rp["start"] <= 8 and rp["end"] >= 7:
                    commute_morning = True
                if rp["start"] <= 18 and rp["end"] >= 17:
                    commute_evening = True

            return {

                "date": dates[i],

                "temp_min": temp_min,

                "temp_max": temp_max,

                "wind_speed_max": wind_speed,

                "weather_code": main_code,

                "weather_desc": weather_desc,

                "uv_index_max": uv,

                "rain_periods": rain_periods,

                "commute_morning": commute_morning,

                "commute_evening": commute_evening,

            }

        except Exception as e:
            import logging
            logging.warning("Open-Meteo 天气查询失败: %s", e)

        if nmc_id:
            return fetch_weather_dialog_detail_nmc(nmc_id, day_offset)
        return None

    def _build_card(self, city: str, label: str, weather: dict) -> str:
        """生成天气卡片文本。"""

        lines = []

        # 定位图标 + 城市名
        lines.append("\U0001f4cd " + city)

        # 日期
        lines.append("📅 " + weather["date"])

        lines.append("")

        lines.append("")

        # 温度 + 天气描述
        lines.append(
            "\U0001f321 " + str(weather['temp_min'])[:4] + "~" +
            str(weather['temp_max'])[:4] + "\u2103  \u2601 " +
            weather['weather_desc']
        )

        # 风速
        if weather["wind_speed_max"] >= 29:
            lines.append("\U0001f4a8 风速：" + str(weather['wind_speed_max'])[:4] + "km/h")

        # 紫外线（含防晒提示在同一行）
        uv = weather["uv_index_max"]

        if uv >= 8:
            uv_lvl = "紫外线极高"
            uv_suffix = "注意防晒"
        elif uv >= 6:
            uv_lvl = "紫外线较高"
            uv_suffix = "注意防晒"
        elif uv >= 3:
            uv_lvl = "紫外线中等"
            uv_suffix = ""
        else:
            uv_lvl = "紫外线较弱"
            uv_suffix = ""

        uv_text = "\u2600\ufe0f 紫外线：" + uv_lvl + "（指数" + str(uv)[:4] + "）"
        if uv_suffix:
            uv_text += " " + uv_suffix

        lines.append(uv_text)

        # 降水时段（多段各自显示概率）
        rain_periods = weather.get("rain_periods", [])

        if rain_periods:
            parts = []
            for rp in rain_periods:
                start_str = str(rp['start']).zfill(2) + ":00"
                end_str = str(rp['end']).zfill(2) + ":00"
                parts.append(start_str + "-" + end_str + "（" + str(rp['prob'])[:4] + "%）")
            lines.append("🌧 降水：" + "、".join(parts))

            # 大雨/高概率提示
            _tips = []
            for rp in rain_periods:
                _high = rp.get("high_ranges", [])
                _heavy = rp.get("has_heavy", False)
                if _heavy and _high:
                    _rh_parts = []
                    for _rs, _re in _high:
                        _rh_parts.append(str(_rs).zfill(2) + ":00-" + str(_re).zfill(2) + ":00")
                    _tips.append("、".join(_rh_parts) + "雨势较大")
                elif _heavy:
                    _ss = str(rp['start']).zfill(2) + ":00"
                    _es = str(rp['end']).zfill(2) + ":00"
                    _tips.append(_ss + "-" + _es + "雨势较大")
                elif _high:
                    _rh_parts = []
                    for _rs, _re in _high:
                        _rh_parts.append(str(_rs).zfill(2) + ":00-" + str(_re).zfill(2) + ":00")
                    _tips.append("、".join(_rh_parts) + "降雨概率较高")

            if _tips:
                lines.append("⚠️ " + "；".join(_tips) + "，注意")

        # 通勤提醒
        if weather.get("commute_morning") or weather.get("commute_evening"):
            tips = []
            if weather.get("commute_morning"):
                tips.append("7:00-9:00")
            if weather.get("commute_evening"):
                tips.append("17:20-18:30")
            lines.append("\u26a0\ufe0f " + "、".join(tips) + "有雨，记得带伞")

        lines.append("")

        lines.append("--- 马小九温馨提示")

        from builtins import chr as _chr
        _nl = _chr(10)
        return _nl.join(lines)

    def _format_hours(hours: list[int]) -> str:

        """格式化降水时段。"""

        if not hours:

            return "无"

        ranges = []

        start = hours[0]

        end = hours[0]

        for h in hours[1:]:

            if h == end + 1:

                end = h

            else:

                ranges.append((start, end))

                start = h

                end = h

        ranges.append((start, end))

        parts = []

        for s, e in ranges:

            if s == e:

                parts.append(f"{s}时")

            else:

                parts.append(f"{s}-{e}时")

        return "、".join(parts)

    def on_send(self):

        """发送天气卡片为图片到微信。"""

        friend = self.friend_input.text().strip()

        if not friend:

            QMessageBox.warning(self, "提示", "请输入微信好友名称")

            return

        msg = self.result_edit.toPlainText().strip()

        if not msg:

            QMessageBox.warning(self, "提示", "没有可发送的内容")

            return

        self.send_btn.setEnabled(False)

        self.send_btn.setText("发送中...")

        QApplication.processEvents()

        # 将天气文字渲染为图片，然后发送图片

        from src.ui.weather_image import render_weather_card

        img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_weather_card_send.png")

        try:

            render_weather_card(msg, img_path)

            success = send_wechat_image(friend, img_path)

        except Exception as e:

            logging.warning(f"天气图片发送失败: {e}")

            success = False

        if success:

            QMessageBox.information(self, "成功", f"已发送给「{friend}」")

            self.accept()

        else:

            QMessageBox.warning(self, "失败", "微信发送失败，请确认微信窗口已打开")

            self.send_btn.setEnabled(True)

            self.send_btn.setText("发送微信")

