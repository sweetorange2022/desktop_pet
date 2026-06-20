# -*- coding: utf-8 -*-
"""AI 账户余额查询服务。

支持通过 HTTP API 查询多个 AI 平台的账户余额，
结果缓存并在指定间隔后自动刷新。
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

@dataclass
class AccountConfig:
    """单个 AI 账户配置。"""
    name: str
    api_url: str
    api_key: str = ""
    method: str = "GET"
    headers: dict = field(default_factory=dict)
    balance_json_path: str = "balance"
    currency: str = "CNY"
    enabled: bool = True
    web_url: str = ""


@dataclass
class BalanceResult:
    """单个账户的余额查询结果。"""
    name: str
    balance: Optional[float] = None
    currency: str = "CNY"
    error: str = ""
    is_loading: bool = False


def _resolve_json_path(data: Any, path: str) -> Any:
    """按点号分隔路径从嵌套 dict/list 中取值。

    支持数组索引，如 balance_infos.0.total_balance
    例如 _resolve_json_path({"data": {"total": 100}}, "data.total") -> 100
    """
    keys = path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        elif isinstance(current, list):
            # 支持数组索引访问
            try:
                idx = int(key)
                if 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None
            except (ValueError, TypeError):
                return None
        else:
            return None
    return current


class AIBalanceService:
    """AI 账户余额查询服务。

    - 从 config/ai_accounts.json 加载账户配置
    - 在后台线程中并发查询各平台余额
    - 结果缓存，定时刷新
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        if config_path is None:
            config_path = str(Path(__file__).parent.parent.parent / "config" / "ai_accounts.json")
        self._config_path = config_path
        self._accounts: list[AccountConfig] = []
        self._enabled: bool = True
        self._refresh_interval_s: int = 300
        self._results: dict[str, BalanceResult] = {}
        self._lock = threading.Lock()
        self._on_update: Optional[callable] = None
        self._timer: Optional[threading.Timer] = None
        self._running = False
        self._load_config()

    def _load_config(self) -> None:
        """从 JSON 文件加载账户配置。"""
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
            logger.warning("加载 AI 账户配置失败: %s", e)
            return

        self._enabled = data.get("enabled", True)
        self._refresh_interval_s = data.get("refresh_interval_s", 300)
        self._accounts.clear()

        for acc in data.get("accounts", []):
            cfg = AccountConfig(
                name=acc.get("name", "未命名"),
                api_url=acc.get("api_url", ""),
                api_key=acc.get("api_key", ""),
                method=acc.get("method", "GET").upper(),
                headers=acc.get("headers", {}),
                balance_json_path=acc.get("balance_json_path", "balance"),
                currency=acc.get("currency", "CNY"),
                enabled=acc.get("enabled", True),
                web_url=acc.get("web_url", ""),
            )
            self._accounts.append(cfg)
            # 初始化结果占位
            if cfg.name not in self._results:
                self._results[cfg.name] = BalanceResult(name=cfg.name, currency=cfg.currency)

    def set_on_update(self, callback: callable) -> None:
        """设置余额更新回调（在主线程中触发）。"""
        self._on_update = callback

    def get_results(self) -> dict[str, BalanceResult]:
        """获取当前缓存的余额结果。"""
        with self._lock:
            return dict(self._results)

    def get_display_data(self) -> dict[str, str]:
        """获取用于气泡显示的数据（{标签: 值}）。"""
        with self._lock:
            results = dict(self._results)

        data = {}
        if not self._enabled:
            return data

        for cfg in self._accounts:
            if not cfg.enabled:
                continue
            result = results.get(cfg.name)
            if result is None:
                continue
            if result.is_loading:
                data[cfg.name] = "查询中..."
            elif result.error:
                data[cfg.name] = f"❌ {result.error}"
            elif result.balance is not None:
                symbol = "¥" if cfg.currency == "CNY" else "$"
                data[cfg.name] = f"{symbol}{result.balance:.2f}"
            else:
                data[cfg.name] = "N/A"

        return data

    def get_overlay_items(self) -> list[dict]:
        """获取悬浮叠加显示数据列表。

        返回格式：[{"name": "DeepSeek", "text": "¥49.95", "ok": True},
                   {"name": "MiMo", "text": "查询", "ok": False, "web_url": "..."}]
        """
        with self._lock:
            results = dict(self._results)

        items = []
        if not self._enabled:
            return items

        for cfg in self._accounts:
            if not cfg.enabled:
                continue
            result = results.get(cfg.name)
            if result is None:
                continue

            if result.is_loading:
                items.append({"name": cfg.name, "text": "...", "ok": True})
            elif result.balance is not None:
                symbol = "¥" if cfg.currency == "CNY" else "$"
                items.append({
                    "name": cfg.name,
                    "text": f"{symbol}{result.balance:.2f}",
                    "ok": True,
                })
            elif cfg.web_url:
                # 无余额 API，但有网页链接
                items.append({
                    "name": cfg.name,
                    "text": "查询",
                    "ok": False,
                    "web_url": cfg.web_url,
                })
            elif not result.error:
                items.append({"name": cfg.name, "text": "N/A", "ok": True})
            # 有错误但无 web_url 的账户不显示

        return items

    def start(self) -> None:
        """启动定时刷新。"""
        if self._running:
            return
        self._running = True
        self.refresh()

    def stop(self) -> None:
        """停止定时刷新。"""
        self._running = False
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def refresh(self) -> None:
        """在后台线程中并发查询所有启用的账户余额。"""
        if not self._enabled:
            self._schedule_next()
            return

        enabled_accounts = [acc for acc in self._accounts if acc.enabled and acc.api_url and acc.api_key]

        if not enabled_accounts:
            self._schedule_next()
            return

        # 标记为加载中
        with self._lock:
            for acc in enabled_accounts:
                self._results[acc.name] = BalanceResult(
                    name=acc.name, currency=acc.currency, is_loading=True
                )

        # 在后台线程中并发查询
        def _do_fetch():
            threads = []
            for acc in enabled_accounts:
                t = threading.Thread(target=self._fetch_single, args=(acc,), daemon=True)
                threads.append(t)
                t.start()

            for t in threads:
                t.join(timeout=30)

            self._schedule_next()

            # 通知更新（通过回调）
            if self._on_update:
                try:
                    self._on_update()
                except Exception as e:
                    logger.warning("AI 余额更新回调失败: %s", e)

        threading.Thread(target=_do_fetch, daemon=True).start()

    def _fetch_single(self, acc: AccountConfig) -> None:
        """查询单个账户的余额。"""
        try:
            headers = {
                "Authorization": f"Bearer {acc.api_key}",
                "Content-Type": "application/json",
                **acc.headers,
            }
            req = urllib.request.Request(
                acc.api_url,
                method=acc.method,
                headers=headers,
            )

            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read().decode("utf-8"))

            balance_raw = _resolve_json_path(body, acc.balance_json_path)
            if balance_raw is None:
                raise ValueError(f"余额字段 '{acc.balance_json_path}' 未找到")

            balance = float(balance_raw)

            with self._lock:
                self._results[acc.name] = BalanceResult(
                    name=acc.name,
                    balance=balance,
                    currency=acc.currency,
                )
            logger.info("AI 余额查询成功: %s = %s %s", acc.name, balance, acc.currency)

        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            err_msg = str(e)
            # 简化错误信息
            if "401" in err_msg or "Unauthorized" in err_msg:
                err_msg = "API Key 无效"
            elif "403" in err_msg or "Forbidden" in err_msg:
                err_msg = "权限不足"
            elif "429" in err_msg or "Too Many" in err_msg:
                err_msg = "请求过于频繁"
            elif "timed out" in err_msg.lower() or "timeout" in err_msg.lower():
                err_msg = "请求超时"
            else:
                err_msg = "连接失败"

            with self._lock:
                self._results[acc.name] = BalanceResult(
                    name=acc.name, error=err_msg, currency=acc.currency
                )
            logger.warning("AI 余额查询失败 [%s]: %s", acc.name, err_msg)

        except (ValueError, TypeError) as e:
            with self._lock:
                self._results[acc.name] = BalanceResult(
                    name=acc.name, error="数据解析失败", currency=acc.currency
                )
            logger.warning("AI 余额解析失败 [%s]: %s", acc.name, e)

        except Exception as e:
            with self._lock:
                self._results[acc.name] = BalanceResult(
                    name=acc.name, error="未知错误", currency=acc.currency
                )
            logger.warning("AI 余额查询异常 [%s]: %s", acc.name, e)

    def _schedule_next(self) -> None:
        """安排下一次定时刷新。"""
        if not self._running:
            return
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(self._refresh_interval_s, self.refresh)
        self._timer.daemon = True
        self._timer.start()

    def reload_config(self) -> None:
        """重新加载配置文件（用户编辑后调用）。"""
        self._load_config()
        # 立即刷新一次
        self.refresh()