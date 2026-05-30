from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
from PIL import Image, ImageDraw


@dataclass
class PoseResult:
    metrics: List[str]
    annotated_frames: List[Image.Image]
    warning: str = ""


POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24), (23, 25), (25, 27),
    (24, 26), (26, 28), (27, 31), (28, 32),
]

_TASK_FILENAME = "pose_landmarker_heavy.task"
_TASK_SEARCH_DIRS = [
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models"),
]


def _find_task_model() -> Optional[str]:
    for directory in _TASK_SEARCH_DIRS:
        path = os.path.join(directory, _TASK_FILENAME)
        if os.path.isfile(path):
            return path
    return None


def _angle_deg(a, b) -> float:
    return float(np.degrees(np.arctan2(b.y - a.y, b.x - a.x)))


def _angle_3pt(a, b, c) -> float:
    """Angle at point b, formed by vectors b→a and b→c."""
    v1 = np.array([a.x - b.x, a.y - b.y])
    v2 = np.array([c.x - b.x, c.y - b.y])
    cos_a = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9)
    return float(np.degrees(np.arccos(np.clip(cos_a, -1.0, 1.0))))


def _vis(lm, threshold: float = 0.55) -> bool:
    return getattr(lm, "visibility", 1.0) >= threshold


def _draw_landmarks(image: Image.Image, landmarks) -> Image.Image:
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    width, height = annotated.size
    for start, end in POSE_CONNECTIONS:
        if start < len(landmarks) and end < len(landmarks):
            a = landmarks[start]
            b = landmarks[end]
            draw.line((a.x * width, a.y * height, b.x * width, b.y * height), fill=(32, 160, 210), width=3)
    for lm in landmarks:
        x, y = lm.x * width, lm.y * height
        draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 214, 78))
    return annotated


def _accumulate_angles(landmarks, acc: Dict[str, List[float]]) -> None:
    """Compute swimming-specific angles from a landmark list and append to accumulators."""
    lm = landmarks

    # Body roll: shoulder-line angle from horizontal
    ls, rs = lm[11], lm[12]
    if _vis(ls) and _vis(rs):
        acc["body_roll"].append(abs(_angle_deg(ls, rs)))

    # Body inclination: shoulder-midpoint to hip-midpoint tilt from horizontal
    lh, rh = lm[23], lm[24]
    if _vis(ls) and _vis(rs) and _vis(lh) and _vis(rh):
        sh_mid_y = (ls.y + rs.y) / 2
        hi_mid_x = (lh.x + rh.x) / 2
        hi_mid_y = (lh.y + rh.y) / 2
        sh_mid_x = (ls.x + rs.x) / 2
        acc["body_tilt"].append(abs(float(np.degrees(np.arctan2(hi_mid_y - sh_mid_y, hi_mid_x - sh_mid_x)))))

        # Hip-shoulder angle separation (body rotation asymmetry)
        hip_angle = abs(_angle_deg(lh, rh))
        shoulder_angle = abs(_angle_deg(ls, rs))
        acc["hip_shoulder_sep"].append(abs(hip_angle - shoulder_angle))

    # Left elbow bend: shoulder(11) → elbow(13) → wrist(15)
    le = lm[13]
    lw = lm[15]
    if _vis(ls) and _vis(le) and _vis(lw):
        acc["left_elbow"].append(_angle_3pt(ls, le, lw))

    # Right elbow bend: shoulder(12) → elbow(14) → wrist(16)
    re = lm[14]
    rw = lm[16]
    if _vis(rs) and _vis(re) and _vis(rw):
        acc["right_elbow"].append(_angle_3pt(rs, re, rw))

    # Left knee flexion: hip(23) → knee(25) → ankle(27)
    lk, la = lm[25], lm[27]
    if _vis(lh) and _vis(lk) and _vis(la):
        acc["left_knee"].append(_angle_3pt(lh, lk, la))

    # Right knee flexion: hip(24) → knee(26) → ankle(28)
    rk, ra = lm[26], lm[28]
    if _vis(rh) and _vis(rk) and _vis(ra):
        acc["right_knee"].append(_angle_3pt(rh, rk, ra))


def _build_metrics(acc: Dict[str, List[float]], detections: int, model_label: str) -> List[str]:
    metrics: List[str] = [f"Pose detected on {detections} frame(s) using {model_label}."]

    if acc["body_roll"]:
        lo, hi = min(acc["body_roll"]), max(acc["body_roll"])
        metrics.append(f"Body roll angle range: {lo:.0f}–{hi:.0f}° (shoulder line from horizontal); >20° suggests active rotation.")

    if acc["body_tilt"]:
        avg = sum(acc["body_tilt"]) / len(acc["body_tilt"])
        metrics.append(f"Body inclination (shoulder-to-hip tilt): {avg:.0f}° avg; near 0° = flat streamline.")

    if acc["left_elbow"] or acc["right_elbow"]:
        parts = []
        if acc["left_elbow"]:
            parts.append(f"left {sum(acc['left_elbow']) / len(acc['left_elbow']):.0f}°")
        if acc["right_elbow"]:
            parts.append(f"right {sum(acc['right_elbow']) / len(acc['right_elbow']):.0f}°")
        metrics.append(f"Elbow bend avg: {', '.join(parts)}; <90° = high-elbow EVF catch position.")

    if acc["left_knee"] or acc["right_knee"]:
        parts = []
        if acc["left_knee"]:
            lo, hi = min(acc["left_knee"]), max(acc["left_knee"])
            parts.append(f"left {lo:.0f}–{hi:.0f}°")
        if acc["right_knee"]:
            lo, hi = min(acc["right_knee"]), max(acc["right_knee"])
            parts.append(f"right {lo:.0f}–{hi:.0f}°")
        metrics.append(f"Knee flexion range: {', '.join(parts)}; 120–160° typical for flutter kick.")

    if acc["hip_shoulder_sep"]:
        avg = sum(acc["hip_shoulder_sep"]) / len(acc["hip_shoulder_sep"])
        metrics.append(f"Hip-shoulder angle separation: {avg:.0f}° avg; >15° may indicate body rotation asymmetry.")

    return metrics[:8]


def _empty_acc() -> Dict[str, List[float]]:
    return {k: [] for k in ("body_roll", "body_tilt", "left_elbow", "right_elbow", "left_knee", "right_knee", "hip_shoulder_sep")}


def _analyze_with_landmarker(frames: List[Image.Image], task_path: str, max_frames: int) -> PoseResult:
    try:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_tasks
        from mediapipe.tasks.python import vision as mp_vision
    except ImportError:
        return PoseResult(metrics=[], annotated_frames=[], warning="MediaPipe is not installed. Install requirements.txt to enable pose estimation.")

    base_options = mp_tasks.BaseOptions(model_asset_path=task_path)
    options = mp_vision.PoseLandmarkerOptions(
        base_options=base_options,
        num_poses=1,
        min_pose_detection_confidence=0.6,
        min_pose_presence_confidence=0.6,
        min_tracking_confidence=0.5,
    )

    acc = _empty_acc()
    annotated_frames: List[Image.Image] = []
    detections = 0

    with mp_vision.PoseLandmarker.create_from_options(options) as landmarker:
        for frame in frames[:max_frames]:
            rgb = np.array(frame.convert("RGB"))
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect(mp_image)
            if not result.pose_landmarks:
                continue
            landmarks = result.pose_landmarks[0]
            visible = [lm for lm in landmarks if _vis(lm)]
            if len(visible) < 12:
                continue
            detections += 1
            annotated_frames.append(_draw_landmarks(frame, landmarks))
            _accumulate_angles(landmarks, acc)

    if detections == 0:
        return PoseResult(metrics=[], annotated_frames=[], warning="No high-confidence pose landmarks were detected; analysis will use visual frames only.")

    return PoseResult(
        metrics=_build_metrics(acc, detections, "heavy pose landmarker"),
        annotated_frames=annotated_frames[:max_frames],
    )


def _analyze_with_fallback_pose(frames: List[Image.Image], max_frames: int) -> PoseResult:
    try:
        import mediapipe as mp
    except ImportError:
        return PoseResult(metrics=[], annotated_frames=[], warning="MediaPipe is not installed. Install requirements.txt to enable pose estimation.")

    mp_pose = mp.solutions.pose
    acc = _empty_acc()
    annotated_frames: List[Image.Image] = []
    detections = 0

    with mp_pose.Pose(static_image_mode=True, model_complexity=2, enable_segmentation=False, min_detection_confidence=0.6) as pose:
        for frame in frames[:max_frames]:
            rgb = np.array(frame.convert("RGB"))
            results = pose.process(rgb)
            if not results.pose_landmarks:
                continue
            landmarks = results.pose_landmarks.landmark
            visible = [lm for lm in landmarks if _vis(lm)]
            if len(visible) < 12:
                continue
            detections += 1
            annotated_frames.append(_draw_landmarks(frame, landmarks))
            _accumulate_angles(landmarks, acc)

    if detections == 0:
        return PoseResult(metrics=[], annotated_frames=[], warning="No high-confidence pose landmarks were detected; analysis will use visual frames only.")

    return PoseResult(
        metrics=_build_metrics(acc, detections, "fallback MediaPipe pose model"),
        annotated_frames=annotated_frames[:max_frames],
    )


def analyze_pose(frames: List[Image.Image], max_frames: int = 6) -> PoseResult:
    task_path = _find_task_model()
    if task_path:
        return _analyze_with_landmarker(frames, task_path, max_frames)
    return _analyze_with_fallback_pose(frames, max_frames)
