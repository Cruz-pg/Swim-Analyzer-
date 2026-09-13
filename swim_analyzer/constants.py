from __future__ import annotations

MAX_IMAGE_SIDE = 1024
JPEG_QUALITY = 85
FOLLOW_UP_CONTEXT_TURNS = 6
MAX_UPLOAD_MB = 100
MAX_VIDEO_SECONDS = 30.0

ACCEPTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}
ACCEPTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}

DEFAULT_MODELS = [
    "gpt-5.6-luna",
    "gpt-4o",
    "gpt-4o-mini",
]

ANALYSIS_CATEGORIES = {
    "general": "General analysis",
    "strokes": "Stroke technique",
    "starts": "Starts / dives",
    "turns": "Turns",
    "finishes": "Finishes",
    "underwater": "Underwater phase",
    "kicks": "Kick technique",
}
