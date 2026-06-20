# -*- coding: utf-8 -*-
"""AI 账户设置对话框。

用户可通过此对话框添加、编辑、删除 AI 账户信息。
配置保存到 config/ai_accounts.json（已被 .gitignore 忽略，不会上传 git）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


def _config_path() -> Path:
    """返回 ai_accounts.json 的绝对路径。"""
    import sys
    if getattr(sys, "frozen", False):
        # 打包后：exe 同目录的 config/
        return Path(sys.executable).parent / "config" / "ai_accounts.json"
    return Path(__file__).parent.parent.parent / "config" / "ai_accounts.json"


def _example_path() -> Path:
    """返回 ai_accounts.example.json 的绝对路径。"""
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "config" / "ai_accounts.example.json"
    return Path(__file__).parent.parent.parent / "config" / "ai_accounts.example.json"


class AIAccountsDialog(QDialog):
    """AI 账户设置对话框。"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI 账户设置")
        self.setMinimumWidth(560)
        self.setMinimumHeight(400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._accounts_data: list[dict] = []
        self._account_widgets: list[dict] = []
        self._global_enabled = True
        self._refresh_interval = 300

        self._load_config()

        layout = QVBoxLayout(self)

        # ---- 全局设置 ----
        global_box = QGroupBox("全局设置")
        global_layout = QHBoxLayout(global_box)
        self._chk_enabled = QCheckBox("启用 AI 余额查询")
        self._chk_enabled.setChecked(self._global_enabled)
        global_layout.addWidget(self._chk_enabled)
        global_layout.addStretch()
        layout.addWidget(global_box)

        # ---- 账户列表（可滚动） ----
        accounts_label = QLabel("账户列表（勾选启用，填入 API Key）：")
        accounts_label.setStyleSheet("font-size: 13px; margin-top: 4px;")
        layout.addWidget(accounts_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        self._accounts_layout = QVBoxLayout(scroll_widget)
        self._accounts_layout.setSpacing(8)

        for acc in self._accounts_data:
            self._add_account_card(acc)

        self._accounts_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # ---- 添加新账户按钮 ----
        btn_add = QPushButton("＋ 添加新账户")
        btn_add.setStyleSheet(
            "QPushButton{background:#3A7DFF;color:white;font:12px 'Microsoft YaHei';"
            "border-radius:4px;padding:6px 16px;}"
            "QPushButton:hover{background:#5A9DFF;}"
        )
        btn_add.clicked.connect(self._on_add_account)
        layout.addWidget(btn_add)

        # ---- 底部按钮 ----
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("保存")
        btn_save.setDefault(True)
        btn_save.setStyleSheet(
            "QPushButton{background:#4CAF50;color:white;font:bold 12px 'Microsoft YaHei';"
            "border-radius:4px;padding:6px 20px;}"
            "QPushButton:hover{background:#66BB6A;}"
        )
        btn_cancel = QPushButton("取消")

        btn_save.clicked.connect(self._on_save)
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def _load_config(self) -> None:
        """从配置文件加载账户数据。"""
        path = _config_path()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # 尝试从模板加载
            path = _example_path()
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                data = {}

        self._global_enabled = data.get("enabled", True)
        self._refresh_interval = data.get("refresh_interval_s", 300)
        self._accounts_data = data.get("accounts", [])

    def _add_account_card(self, acc: dict) -> None:
        """为一个账户添加编辑卡片。"""
        name = acc.get("name", "未命名")
        enabled = acc.get("enabled", False)

        group = QGroupBox()
        group.setStyleSheet(
            "QGroupBox{border:1px solid #555;border-radius:6px;margin-top:8px;padding-top:14px;}"
            "QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 4px;}"
        )
        card_layout = QFormLayout(group)
        card_layout.setLabelAlignment(Qt.AlignRight)

        # 启用复选框
        chk = QCheckBox(f"启用 {name}")
        chk.setChecked(enabled)
        chk.setStyleSheet("font-weight:bold;")
        card_layout.addRow(chk)

        # 名称
        edit_name = QLineEdit(acc.get("name", ""))
        edit_name.setPlaceholderText("如：DeepSeek、豆包")
        card_layout.addRow("名称:", edit_name)

        # API URL
        edit_url = QLineEdit(acc.get("api_url", ""))
        edit_url.setPlaceholderText("如：https://api.deepseek.com/user/balance")
        card_layout.addRow("API 地址:", edit_url)

        # API Key
        edit_key = QLineEdit(acc.get("api_key", ""))
        edit_key.setPlaceholderText("填入你的 API Key")
        edit_key.setEchoMode(QLineEdit.EchoMode.Password)
        card_layout.addRow("API Key:", edit_key)

        # 余额字段路径
        edit_path = QLineEdit(acc.get("balance_json_path", "balance"))
        edit_path.setPlaceholderText("如：balance 或 data.total_balance")
        card_layout.addRow("余额字段路径:", edit_path)

        # 货币
        edit_currency = QLineEdit(acc.get("currency", "CNY"))
        edit_currency.setPlaceholderText("CNY / USD")
        edit_currency.setMaximumWidth(80)
        card_layout.addRow("货币:", edit_currency)

        # 网页查询链接（无余额API时使用）
        edit_web_url = QLineEdit(acc.get("web_url", ""))
        edit_web_url.setPlaceholderText("无API时的网页查询地址（可选）")
        card_layout.addRow("网页查询:", edit_web_url)

        # 删除按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_delete = QPushButton("删除此账户")
        btn_delete.setStyleSheet(
            "QPushButton{background:#D32F2F;color:white;font:11px 'Microsoft YaHei';"
            "border-radius:4px;padding:4px 12px;}"
            "QPushButton:hover{background:#F44336;}"
        )
        btn_delete.clicked.connect(lambda: self._delete_account(group))
        btn_row.addWidget(btn_delete)
        card_layout.addRow(btn_row)

        self._accounts_layout.insertWidget(self._accounts_layout.count() - 1, group)

        self._account_widgets.append({
            "group": group,
            "chk": chk,
            "name": edit_name,
            "url": edit_url,
            "key": edit_key,
            "path": edit_path,
            "currency": edit_currency,
            "web_url": edit_web_url,
        })

    def _on_add_account(self) -> None:
        """添加新账户。"""
        self._add_account_card({
            "name": "",
            "api_url": "",
            "api_key": "",
            "balance_json_path": "balance",
            "currency": "CNY",
            "enabled": True,
        })

    def _delete_account(self, group: QGroupBox) -> None:
        """删除一个账户卡片。"""
        # 找到对应的 widget 条目
        for i, w in enumerate(self._account_widgets):
            if w["group"] is group:
                reply = QMessageBox.question(
                    self, "确认删除",
                    f"确定要删除账户「{w['name'].text() or '未命名'}」吗？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    group.hide()
                    group.deleteLater()
                    self._account_widgets.pop(i)
                return

    def _on_save(self) -> None:
        """保存配置到文件。"""
        accounts = []
        for w in self._account_widgets:
            name = w["name"].text().strip()
            if not name:
                continue
            accounts.append({
                "name": name,
                "api_url": w["url"].text().strip(),
                "api_key": w["key"].text().strip(),
                "method": "GET",
                "headers": {},
                "balance_json_path": w["path"].text().strip() or "balance",
                "currency": w["currency"].text().strip() or "CNY",
                "enabled": w["chk"].isChecked(),
                "web_url": w["web_url"].text().strip(),
            })

        data = {
            "comment": "AI账户余额配置。已被 .gitignore 忽略，不会上传 git。",
            "enabled": self._chk_enabled.isChecked(),
            "refresh_interval_s": self._refresh_interval,
            "accounts": accounts,
        }

        path = _config_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            QMessageBox.critical(self, "保存失败", f"无法写入配置文件：\n{e}")
            return

        self.accept()

    def get_accounts_data(self) -> list[dict]:
        """返回保存后的账户数据。"""
        return self._accounts_data