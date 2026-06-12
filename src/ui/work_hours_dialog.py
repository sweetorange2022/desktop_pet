"""工作时间设置对话框。

首次使用时弹出，让用户设定自己的工作时间段和对应的下班时间。
也可通过托盘菜单"设置工作时间"随时修改。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class WorkHoursDialog(QDialog):
    """工作时间设置对话框。"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置工作时间")
        self.setMinimumWidth(380)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._result_data: Optional[dict] = None

        # 读取当前配置
        self._load_current()

        layout = QVBoxLayout(self)

        # 说明
        info = QLabel("请设置您的工作时间和对应的下班时间：")
        info.setStyleSheet("font-size: 13px; margin-bottom: 8px;")
        layout.addWidget(info)

        # 工作时段表单
        self._segments: list[dict] = []
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        for i, (wh, wm, oh, om) in enumerate(self._work_hours_with_off):
            seg_widget = QWidget()
            seg_layout = QHBoxLayout(seg_widget)
            seg_layout.setContentsMargins(0, 0, 0, 0)

            # 上班时间
            start_sh = QSpinBox()
            start_sh.setRange(0, 23)
            start_sh.setValue(wh)
            start_sh.setSuffix("时")
            start_sm = QSpinBox()
            start_sm.setRange(0, 59)
            start_sm.setValue(wm)
            start_sm.setSuffix("分")

            # 下班时间
            end_sh = QSpinBox()
            end_sh.setRange(0, 23)
            end_sh.setValue(oh)
            end_sh.setSuffix("时")
            end_sm = QSpinBox()
            end_sm.setRange(0, 59)
            end_sm.setValue(om)
            end_sm.setSuffix("分")

            seg_layout.addWidget(QLabel("上班:"))
            seg_layout.addWidget(start_sh)
            seg_layout.addWidget(start_sm)
            seg_layout.addWidget(QLabel("  下班:"))
            seg_layout.addWidget(end_sh)
            seg_layout.addWidget(end_sm)

            label = f"时段{i + 1}" if len(self._work_hours_with_off) > 1 else "工作时段"
            form.addRow(label, seg_widget)

            self._segments.append({
                "start_sh": start_sh, "start_sm": start_sm,
                "end_sh": end_sh, "end_sm": end_sm,
            })

        layout.addLayout(form)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("确定")
        btn_ok.setDefault(True)
        btn_cancel = QPushButton("跳过（使用默认值）")

        btn_ok.clicked.connect(self._on_ok)
        btn_cancel.clicked.connect(self._on_skip)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

    def _load_current(self) -> None:
        """从 config 文件读取当前配置。"""
        config_dir = Path(__file__).parent.parent.parent / "config"
        health_path = config_dir / "health.json"

        try:
            with open(health_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}

        work_hours = data.get("health_work_hours", [[9, 0, 12, 10], [13, 30, 24, 0]])
        off_times = data.get("health_off_work_times", [[12, 10], [18, 0]])

        # 合并 work_hours 和 off_times
        self._work_hours_with_off = []
        for i, wh in enumerate(work_hours):
            off = off_times[i] if i < len(off_times) else [wh[2], wh[3]]
            self._work_hours_with_off.append((wh[0], wh[1], off[0], off[1]))

    def _on_ok(self) -> None:
        """确定：收集数据并保存。"""
        work_hours = []
        off_times = []

        for seg in self._segments:
            sh = seg["start_sh"].value()
            sm = seg["start_sm"].value()
            eh = seg["end_sh"].value()
            em = seg["end_sm"].value()

            # 验证：上班时间必须早于下班时间
            if sh * 60 + sm >= eh * 60 + em:
                QMessageBox.warning(
                    self, "时间错误",
                    f"上班时间 ({sh}:{sm:02d}) 必须早于下班时间 ({eh}:{em:02d})",
                )
                return

            work_hours.append([sh, sm, eh, em])
            off_times.append([eh, em])

        self._result_data = {
            "work_hours": work_hours,
            "off_times": off_times,
        }

        # 保存到配置文件
        self._save_config(work_hours, off_times)
        self.accept()

    def _on_skip(self) -> None:
        """跳过：使用默认值，标记为已配置。"""
        self._save_config(None, None, configured=True)
        self.accept()

    def _save_config(
        self,
        work_hours: Optional[list[list[int]]],
        off_times: Optional[list[list[int]]],
        configured: bool = False,
    ) -> None:
        """保存工作时间配置到 health.json。"""
        config_dir = Path(__file__).parent.parent.parent / "config"
        health_path = config_dir / "health.json"

        try:
            with open(health_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}

        data["work_hours_configured"] = True

        if work_hours is not None:
            data["health_work_hours"] = work_hours
        if off_times is not None:
            data["health_off_work_times"] = off_times

        with open(health_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_result(self) -> Optional[dict]:
        """返回用户设置结果。"""
        return self._result_data