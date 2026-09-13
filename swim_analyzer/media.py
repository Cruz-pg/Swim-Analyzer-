from __future__ import annotations

import base64
import hashlib
import os
import tempfile
from io import BytesIO
from typing import List, Tuple

import cv2
from PIL import Image, ImageOps

from .constants import (
    ACCEPTED_IMAGE_EXTENSIONS,
    ACCEPTED_VIDEO_EXTENSIONS,
    JPEG_QUALITY,
    MAX_IMAGE_SIDE,
    MAX_UPLOAD_MB,
    MAX_VIDEO_SECONDS,
)


def bytes_to_mb(num_bytes: int) -> float:
    return num_bytes / (1024 * 1024)


def validate_upload_size(file_bytes: bytes) -> None:
    size_mb = bytes_to_mb(len(file_bytes))
    if size_mb > MAX_UPLOAD_MB:
        raise ValueError(f"Upload is {size_mb:.1f} MB. Please upload a file under {MAX_UPLOAD_MB} MB.")


def get_file_extension(filename: str) -> str:
    _, ext = os.path.splitext(filename or "")
    return ext.lower()


def validate_extension(filename: str, allowed: set[str], label: str) -> str:
    ext = get_file_extension(filename)
    if ext not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ValueError(f"Unsupported {label} type '{ext or 'unknown'}'. Allowed types: {allowed_text}.")
    return ext


def normalize_image(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    if image.mode != "RGB":
        image = image.convert("RGB")
    return image


def resize_image_for_model(image: Image.Image, max_side: int = MAX_IMAGE_SIDE) -> Image.Image:
    image = normalize_image(image)
    width, height = image.size
    longest = max(width, height)
    if longest <= max_side:
        return image
    scale = max_side / float(longest)
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return image.resize(new_size, Image.LANCZOS)


def image_to_base64(image: Image.Image, image_format: str = "JPEG") -> str:
    buffer = BytesIO()
    if image_format.upper() == "JPEG":
        image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    else:
        image.save(buffer, format=image_format.upper())
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def build_media_content(images: List[Image.Image], detail: str = "auto") -> List[dict]:
    content: List[dict] = []
    for img in images:
        prepared = resize_image_for_model(img)
        base64_image = image_to_base64(prepared, image_format="JPEG")
        content.append(
            {
                "type": "input_image",
                "image_url": f"data:image/jpeg;base64,{base64_image}",
                "detail": detail,
            }
        )
    return content


def _pil_from_bgr(frame_bgr) -> Image.Image:
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(frame_rgb)


def file_bytes_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def build_processing_signature(file_hash: str, media_type: str, max_frames: int, smart: bool, pose_enabled: bool) -> str:
    return f"{media_type}:{file_hash}:frames={max_frames}:smart={smart}:pose={pose_enabled}:side={MAX_IMAGE_SIDE}:q={JPEG_QUALITY}"


def get_video_metadata(video_path: str) -> Tuple[int, float, float]:
    cap = cv2.VideoCapture(video_path)
    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps if fps and fps > 0 else 0.0
        return total_frames, fps, duration
    finally:
        cap.release()


def validate_video_duration(video_path: str) -> float:
    total_frames, fps, duration = get_video_metadata(video_path)
    if total_frames <= 0:
        raise ValueError("Could not read video frames. Try a shorter MP4/MOV clip.")
    if duration > MAX_VIDEO_SECONDS:
        raise ValueError(f"Video is {duration:.1f}s. Please upload a clip under {MAX_VIDEO_SECONDS:.0f}s.")
    if not fps or fps <= 0:
        raise ValueError("Could not read the video's frame rate. Try exporting as MP4 or MOV.")
    return duration


def extract_frames_uniform(video_path: str, max_frames: int = 10) -> Tuple[List[Image.Image], float]:
    video = cv2.VideoCapture(video_path)
    total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = video.get(cv2.CAP_PROP_FPS)
    duration = total_frames / fps if fps and fps > 0 else 0.0
    if total_frames <= 0:
        video.release()
        return [], duration
    frame_indices = sorted(set(int(i * total_frames / max_frames) for i in range(max_frames)))
    frames: List[Image.Image] = []
    for idx in frame_indices:
        video.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = video.read()
        if ret:
            frames.append(resize_image_for_model(_pil_from_bgr(frame)))
    video.release()
    return frames[:max_frames], duration


def extract_frames_motion_based(video_path: str, max_frames: int = 10, scan_step: int = 2) -> Tuple[List[Image.Image], float]:
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = total_frames / fps if fps and fps > 0 else 0.0
    if total_frames <= 0:
        cap.release()
        return [], duration
    scored: List[Tuple[float, int]] = []
    prev_gray = None
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % scan_step != 0:
            idx += 1
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if prev_gray is not None:
            diff = cv2.absdiff(gray, prev_gray)
            scored.append((float(diff.mean()), idx))
        prev_gray = gray
        idx += 1
    cap.release()
    if not scored:
        return extract_frames_uniform(video_path, max_frames=max_frames)
    selected_idxs: List[int] = []
    seed_count = min(3, max_frames)
    selected_idxs.extend(sorted(set(int(i * (total_frames - 1) / max(1, seed_count - 1)) for i in range(seed_count))))
    scored.sort(key=lambda x: x[0], reverse=True)
    min_sep_frames = max(int((total_frames / max_frames) * 0.45), 5)
    for _, fidx in scored:
        if all(abs(fidx - used) >= min_sep_frames for used in selected_idxs):
            selected_idxs.append(fidx)
        if len(selected_idxs) >= max_frames:
            break
    if len(selected_idxs) < max_frames:
        for fidx in sorted(set(int(i * total_frames / max_frames) for i in range(max_frames))):
            if fidx not in selected_idxs:
                selected_idxs.append(fidx)
            if len(selected_idxs) >= max_frames:
                break
    selected_idxs = sorted(selected_idxs[:max_frames])
    cap = cv2.VideoCapture(video_path)
    frames_pil: List[Image.Image] = []
    for frame_idx in selected_idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if ret:
            frames_pil.append(resize_image_for_model(_pil_from_bgr(frame)))
    cap.release()
    return frames_pil, duration


def process_uploaded_image(uploaded_file, file_bytes: bytes) -> Image.Image:
    validate_extension(getattr(uploaded_file, "name", ""), ACCEPTED_IMAGE_EXTENSIONS, "image")
    validate_upload_size(file_bytes)
    return resize_image_for_model(Image.open(BytesIO(file_bytes)))


def extract_frames_from_uploaded_video(video_file, file_bytes: bytes, max_frames: int = 10, smart: bool = True) -> Tuple[List[Image.Image], float]:
    original_name = getattr(video_file, "name", "") or ""
    ext = validate_extension(original_name, ACCEPTED_VIDEO_EXTENSIONS, "video")
    validate_upload_size(file_bytes)
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
        tmp_file.write(file_bytes)
        tmp_path = tmp_file.name
    try:
        validate_video_duration(tmp_path)
        if smart:
            frames, duration = extract_frames_motion_based(tmp_path, max_frames=max_frames, scan_step=2)
            if frames:
                return frames, duration
        return extract_frames_uniform(tmp_path, max_frames=max_frames)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

