"""摄像头健康检测模块（OpenCV 版）。

短暂开启摄像头采集帧 → OpenCV Haar 人脸检测 → 输出评分 + 快照保存。
不依赖 mediapipe，仅用 OpenCV + numpy。
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Haar 级联分类器路径（OpenCV 自带）
_CASCADE_FACE = None
_CASCADE_EYE = None


def _get_cascades():
    global _CASCADE_FACE, _CASCADE_EYE
    if _CASCADE_FACE is not None:
        return _CASCADE_FACE, _CASCADE_EYE

    # 多路径尝试（兼容打包后环境）
    candidates = []
    try:
        candidates.append(cv2.data.haarcascades)
    except Exception:
        pass
    # PyInstaller 打包后的 cv2 数据目录
    import sys
    if getattr(sys, "frozen", False):
        meipass = sys._MEIPASS
        candidates.append(os.path.join(meipass, "cv2", "data"))
        candidates.append(os.path.join(meipass, "cv2", "data", "haarcascades"))
    # 本机 Python 安装目录
    try:
        import cv2 as _cv2
        cv2_dir = os.path.dirname(_cv2.__file__)
        candidates.append(os.path.join(cv2_dir, "data"))
        candidates.append(os.path.join(cv2_dir, "data", "haarcascades"))
    except Exception:
        pass

    face_xml = "haarcascade_frontalface_default.xml"
    eye_xml = "haarcascade_eye.xml"

    for d in candidates:
        face_path = os.path.join(d, face_xml)
        eye_path = os.path.join(d, eye_xml)
        if os.path.isfile(face_path):
            _CASCADE_FACE = cv2.CascadeClassifier(face_path)
            _CASCADE_EYE = cv2.CascadeClassifier(eye_path)
            if not _CASCADE_FACE.empty():
                logger.info("Haar 级联加载成功: %s", d)
                return _CASCADE_FACE, _CASCADE_EYE

    # 最后尝试直接加载（让 OpenCV 自己找）
    _CASCADE_FACE = cv2.CascadeClassifier(face_xml)
    _CASCADE_EYE = cv2.CascadeClassifier(eye_xml)
    if _CASCADE_FACE.empty():
        logger.error("无法加载 Haar 级联文件，人脸检测将不可用")
    return _CASCADE_FACE, _CASCADE_EYE


@dataclass
class CameraSnapshot:
    """单次摄像头检测结果。"""
    timestamp: str
    fatigue: int = 50
    posture: int = 80
    skin_tone: str = "正常"
    eye_dark: int = 30
    tension: int = 40
    face_detected: bool = False
    image_path: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class CameraMonitor:
    """摄像头健康检测器（OpenCV 版）。

    用法：
        monitor = CameraMonitor(config)
        snapshot = monitor.capture_and_analyze()
    """

    def __init__(self, config: dict) -> None:
        self._enabled = config.get("enabled", True)
        self._camera_index = config.get("camera_index", 0)
        self._width = config.get("resolution_width", 1280)
        self._height = config.get("resolution_height", 720)
        self._duration = config.get("capture_duration_s", 5)
        self._fps = config.get("capture_fps", 10)
        self._snapshot_dir = config.get("snapshot_dir", "data/camera_snapshots")
        self._quality = config.get("snapshot_quality", 85)

    def capture_and_analyze(self) -> CameraSnapshot:
        """采集 5 秒帧 → OpenCV 人脸分析 → 返回评分 + 保存快照。"""
        ts = datetime.now()
        logger.info("摄像头采集开始 (%s)", ts.strftime("%H:%M:%S"))
        frames = self._capture_frames()
        if not frames:
            logger.warning("摄像头采集失败: 无帧数据")
            return CameraSnapshot(timestamp=ts.isoformat(), face_detected=False)
        logger.info("采集到 %d 帧，开始分析...", len(frames))

        # 取中间帧保存为快照
        mid_frame = frames[len(frames) // 2]
        image_path = self._save_snapshot(mid_frame, ts)

        # 逐帧分析
        cascade_face, cascade_eye = _get_cascades()
        if cascade_face is None or cascade_face.empty():
            logger.error("Haar 级联未加载，跳过分析")
            return CameraSnapshot(
                timestamp=ts.isoformat(), face_detected=False, image_path=image_path
            )
        face_found_count = 0
        eye_counts = []
        skin_samples = []
        face_positions = []
        brightness_values = []
        eye_region_darks = []

        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # 人脸检测
            faces = cascade_face.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80)
            )

            if len(faces) == 0:
                continue

            face_found_count += 1
            x, y, w, h = faces[0]  # 取最大人脸
            face_positions.append((x, y, w, h))

            # 人脸 ROI
            face_roi_gray = gray[y:y + h, x:x + w]
            face_roi_rgb = rgb[y:y + h, x:x + w]

            # 眼睛检测（在人脸区域内）
            eyes = cascade_eye.detectMultiScale(
                face_roi_gray, scaleFactor=1.1, minNeighbors=3, minSize=(20, 20)
            )
            eye_counts.append(len(eyes))

            # 面部亮度 → 疲劳判断（暗 → 疲劳）
            brightness = float(face_roi_gray.mean())
            brightness_values.append(brightness)

            # 眼部区域暗度（眼睛上方1/3区域）
            eye_region = face_roi_gray[h // 4:h // 2, :]
            if eye_region.size > 0:
                eye_region_darks.append(float(eye_region.mean()))

            # 肤色分析
            skin = self._analyze_skin_tone(face_roi_rgb)
            skin_samples.append(skin)

        if face_found_count == 0:
            logger.info("未检测到人脸")
            return CameraSnapshot(
                timestamp=ts.isoformat(), face_detected=False, image_path=image_path
            )

        # 计算综合评分
        face_ratio = face_found_count / len(frames)
        avg_brightness = np.mean(brightness_values)
        avg_eye_dark = np.mean(eye_region_darks) if eye_region_darks else 128

        fatigue = self._calc_fatigue(avg_brightness, avg_eye_dark, face_ratio)
        posture = self._calc_posture(face_positions)
        skin_tone = self._classify_skin(skin_samples)
        eye_dark = int(np.clip((1.0 - avg_eye_dark / 255.0) * 150, 0, 100))
        tension = self._calc_tension(face_positions)

        snapshot = CameraSnapshot(
            timestamp=ts.isoformat(),
            fatigue=int(np.clip(fatigue, 0, 100)),
            posture=int(np.clip(posture, 0, 100)),
            skin_tone=skin_tone,
            eye_dark=eye_dark,
            tension=tension,
            face_detected=True,
            image_path=image_path,
        )

        self._save_meta(image_path, snapshot)
        logger.info(
            "分析完成: fatigue=%d posture=%d skin=%s eye_dark=%d tension=%d face_ratio=%.1f%% → %s",
            snapshot.fatigue, snapshot.posture, snapshot.skin_tone,
            snapshot.eye_dark, snapshot.tension, face_ratio * 100, image_path,
        )
        return snapshot

    def _capture_frames(self) -> list[np.ndarray]:
        """短暂开启摄像头，采集指定帧数。"""
        cap = cv2.VideoCapture(self._camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            logger.warning("摄像头 %d 无法打开", self._camera_index)
            return []
        try:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
            cap.set(cv2.CAP_PROP_FPS, self._fps)

            frames = []
            target_count = self._duration * self._fps
            interval = 1.0 / self._fps
            start = time.monotonic()

            while len(frames) < target_count:
                ret, frame = cap.read()
                if not ret:
                    break
                frames.append(frame)
                elapsed = time.monotonic() - start
                expected = len(frames) * interval
                if expected > elapsed:
                    time.sleep(expected - elapsed)

            logger.info("摄像头实际采集 %d 帧 (目标 %d)", len(frames), target_count)
            return frames
        finally:
            cap.release()

    def _save_snapshot(self, frame: np.ndarray, ts: datetime) -> str:
        """保存快照到目录（每次检测独立子文件夹）。"""
        time_dir = os.path.join(
            self._snapshot_dir,
            f"{ts.year}-W{ts.isocalendar()[1]:02d}",
            ts.strftime("%Y%m%d"),
            ts.strftime("%H%M%S"),
        )
        os.makedirs(time_dir, exist_ok=True)
        path = os.path.join(time_dir, "snapshot.jpg")
        cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, self._quality])
        return path

    def _save_meta(self, image_path: str, snapshot: CameraSnapshot) -> None:
        """保存元数据 JSON。"""
        meta_path = image_path.rsplit(".", 1)[0] + "_meta.json"
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(snapshot.to_dict(), f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning("保存元数据失败: %s", e)

    # ---- 评分计算 ----

    @staticmethod
    def _calc_fatigue(brightness: float, eye_dark: float, face_ratio: float) -> int:
        """根据面部亮度和眼部暗度计算疲劳评分。

        亮度低 + 眼部暗 → 疲劳分高。
        face_ratio 低（人脸检测不稳定）→ 可能低头 → 疲劳。
        """
        # 亮度映射：正常 ~120-180，暗 <100
        if brightness >= 150:
            brightness_score = 20
        elif brightness >= 120:
            brightness_score = 35
        elif brightness >= 100:
            brightness_score = 55
        elif brightness >= 80:
            brightness_score = 70
        else:
            brightness_score = 85

        # 眼部暗度：暗 → 疲劳
        eye_score = int(np.clip((1.0 - eye_dark / 255.0) * 100, 0, 100))

        # 人脸检测率：低 → 可能低头/闭眼
        ratio_score = int(max(0, (1.0 - face_ratio) * 100))

        # 加权平均
        return int(brightness_score * 0.4 + eye_score * 0.4 + ratio_score * 0.2)

    @staticmethod
    def _calc_posture(positions: list[tuple]) -> int:
        """根据人脸位置变化估算坐姿。

        人脸位置大幅偏移 → 坐姿不稳。
        人脸位置偏低 → 可能低头。
        """
        if not positions:
            return 50

        # 取最后几帧的人脸位置
        recent = positions[-min(10, len(positions)):]
        if len(recent) < 2:
            return 75

        # 计算人脸中心的 y 坐标变化
        centers_y = [y + h // 2 for x, y, w, h in recent]
        centers_x = [x + w // 2 for x, y, w, h in recent]

        y_std = float(np.std(centers_y))
        x_std = float(np.std(centers_x))

        # 位置稳定 → 坐姿好
        stability = y_std + x_std
        if stability < 10:
            return 90
        elif stability < 20:
            return 75
        elif stability < 40:
            return 55
        else:
            return 35

    @staticmethod
    def _calc_tension(positions: list[tuple]) -> int:
        """根据人脸大小变化估算肌肉紧张度。"""
        if len(positions) < 3:
            return 40
        recent = positions[-min(10, len(positions)):]
        sizes = [w * h for x, y, w, h in recent]
        std = float(np.std(sizes))
        return int(np.clip(std / 100, 20, 80))

    @staticmethod
    def _analyze_skin_tone(face_rgb: np.ndarray) -> dict:
        """分析面部肤色（HSV）。"""
        hsv = cv2.cvtColor(face_rgb, cv2.COLOR_RGB2HSV)
        return {
            "h": float(hsv[:, :, 0].mean()),
            "s": float(hsv[:, :, 1].mean()),
            "v": float(hsv[:, :, 2].mean()),
        }

    @staticmethod
    def _classify_skin(samples: list[dict]) -> str:
        """根据多次采样判定肤色类别。"""
        if not samples:
            return "正常"
        avg_v = np.mean([s["v"] for s in samples])
        avg_s = np.mean([s["s"] for s in samples])
        if avg_v > 180 and avg_s < 40:
            return "苍白"
        elif avg_s > 80 and avg_v > 100:
            return "红润"
        elif avg_v < 80:
            return "暗沉"
        return "正常"


def cleanup_old_snapshots(snapshot_dir: str) -> int:
    """清理非本周的快照目录。"""
    current_week = datetime.now().isocalendar()[1]
    current_year = datetime.now().year
    removed = 0
    base = Path(snapshot_dir)
    if not base.exists():
        return 0
    for week_dir in base.iterdir():
        if not week_dir.is_dir():
            continue
        name = week_dir.name
        try:
            if "-W" in name:
                parts = name.split("-W")
                year = int(parts[0])
                week = int(parts[1])
                if year != current_year or week != current_week:
                    import shutil
                    shutil.rmtree(week_dir)
                    removed += 1
                    logger.info("清理旧快照: %s", week_dir)
        except (ValueError, OSError):
            continue
    return removed
