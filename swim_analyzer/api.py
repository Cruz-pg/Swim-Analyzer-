"""Same-origin HTTP boundary for the React client; no Streamlit dependency."""
from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, Response, UploadFile
from openai import AuthenticationError, BadRequestError, NotFoundError, RateLimitError, APITimeoutError
from PIL import UnidentifiedImageError
from PIL.Image import DecompressionBombError
from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import service
from .constants import ACCEPTED_IMAGE_EXTENSIONS, ACCEPTED_VIDEO_EXTENSIONS, ANALYSIS_CATEGORIES, DEFAULT_MODELS, MAX_UPLOAD_MB, MAX_VIDEO_SECONDS
from .media import extract_frames_from_uploaded_video, process_uploaded_image, validate_extension, validate_upload_size
from .report import build_report
from .schemas import SwimmerProfile

router = APIRouter(prefix="/api")
store = service.SessionStore()
COOKIE = "swimform_session"


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_max_length=1000)
    goal: str = ""
    skill_level: Literal["Beginner", "Intermediate", "Advanced", "Competitive"] = "Intermediate"
    primary_stroke: str = ""
    distance: str = ""
    pace_context: Literal["Unknown", "Easy", "Technique drill", "Moderate", "Race pace", "Sprint"] = "Unknown"
    breathing: str = ""
    environment: Literal["Pool", "Open water", "Endless pool", "Starting block", "Wall / turn practice", "Unknown"] = "Pool"
    camera_angle: str = ""
    pain: str = ""
    known_issues: List[str] = Field(default_factory=list, max_length=20)
    coach_notes: str = ""


class AnalysisOptions(BaseModel):
    model: str = Field(default=DEFAULT_MODELS[0], min_length=1, max_length=200)
    temperature: float = Field(default=0.6, ge=0, le=1.2)
    image_detail: Literal["auto", "low", "high"] = "auto"
    pose_enabled: bool = False
    include_media_on_followup: bool = False

    @field_validator("model")
    @classmethod
    def model_must_be_allowed(cls, value: str) -> str:
        if value not in DEFAULT_MODELS:
            raise ValueError("Choose one of the available AI models.")
        return value


class AnalysisInput(BaseModel):
    profile: ProfileInput = Field(default_factory=ProfileInput)
    category: Literal["general", "strokes", "starts", "turns", "finishes", "underwater", "kicks"] = "general"
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)


class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=6000)
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)


def current_session(request: Request) -> service.AnalysisSession:
    session = store.get(request.cookies.get(COOKIE))
    if session is None:
        raise HTTPException(409, "Your session has expired. Refresh the page and upload your footage again.")
    return session


@contextmanager
def session_operation(session: service.AnalysisSession):
    if not session.lock.acquire(blocking=False):
        raise HTTPException(409, "This session is still processing. Please wait for it to finish.")
    try:
        yield
    finally:
        session.lock.release()


def api_error(exc: Exception) -> HTTPException:
    # Upstream exception strings may contain credentials or request details.
    if isinstance(exc, AuthenticationError):
        return HTTPException(401, "Your API key was not accepted. Check it in Settings and try again.")
    if isinstance(exc, RateLimitError):
        return HTTPException(429, "Your AI account has reached a rate or usage limit. Check your account or try again shortly.")
    if isinstance(exc, (BadRequestError, NotFoundError)):
        return HTTPException(400, "The AI request could not be completed. Check your model and API access in Settings.")
    if isinstance(exc, APITimeoutError):
        return HTTPException(504, "The analysis took too long. Please try again.")
    if isinstance(exc, ValueError) and str(exc).startswith("Add your OpenAI API key"):
        return HTTPException(400, str(exc))
    return HTTPException(502, "The coach could not complete this request. Your footage is still here; please try again.")


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/config")
def config():
    key = os.getenv("OPENAI_API_KEY", "").strip()
    return {
        "categories": ANALYSIS_CATEGORIES, "models": DEFAULT_MODELS,
        "max_upload_mb": MAX_UPLOAD_MB, "max_video_seconds": MAX_VIDEO_SECONDS,
        "image_extensions": sorted(ACCEPTED_IMAGE_EXTENSIONS),
        "video_extensions": sorted(ACCEPTED_VIDEO_EXTENSIONS),
        "api_key_configured": bool(key and key != "sk-your-key"),
    }


@router.get("/session")
def read_session(request: Request, response: Response):
    session = store.get(request.cookies.get(COOKIE))
    if session is None:
        try:
            token, session = store.create()
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        response.set_cookie(COOKIE, token, httponly=True, samesite="strict", secure=request.url.scheme == "https", path="/api")
    with session_operation(session):
        return service.public_state(session)


@router.delete("/session")
def reset_session(session: service.AnalysisSession = Depends(current_session)):
    with session_operation(session):
        session.clear_media()
        return service.public_state(session)


@router.put("/profile")
def save_profile(data: ProfileInput, session: service.AnalysisSession = Depends(current_session)):
    with session_operation(session):
        session.profile = SwimmerProfile(**data.model_dump())
        return asdict(session.profile)


@router.post("/upload")
def upload(
    file: UploadFile = File(...), max_frames: int = Form(10, ge=5, le=20), smart: bool = Form(True),
    session: service.AnalysisSession = Depends(current_session),
):
    with session_operation(session):
        try:
            name = Path(file.filename or "upload").name[:255]
            ext = validate_extension(name, ACCEPTED_IMAGE_EXTENSIONS | ACCEPTED_VIDEO_EXTENSIONS, "media")
            data = file.file.read(MAX_UPLOAD_MB * 1024 * 1024 + 1)
            validate_upload_size(data)
            if not data:
                raise ValueError("This file is empty. Choose a swimming image or video.")
            uploaded = SimpleNamespace(name=name)
            if ext in ACCEPTED_IMAGE_EXTENSIONS:
                frames, duration, media_type = [process_uploaded_image(uploaded, data)], 0.0, "image"
            else:
                frames, duration = extract_frames_from_uploaded_video(uploaded, data, max_frames=max_frames, smart=smart)
                media_type = "video"
            if not frames:
                raise ValueError("No usable frames were found. Try exporting your clip as MP4.")
        except (UnidentifiedImageError, DecompressionBombError) as exc:
            raise HTTPException(400, "This image could not be opened. Try a smaller JPG or PNG.") from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(400, "This file could not be processed. Try a JPG, PNG, or short MP4.") from exc
        finally:
            file.file.close()
        session.clear_media()
        session.frames, session.duration = frames, duration
        session.media_name, session.media_type = name, media_type
        return service.public_state(session)


@router.post("/analyze")
def analyze(
    data: AnalysisInput, session: service.AnalysisSession = Depends(current_session),
    x_openai_key: Optional[str] = Header(None),
):
    with session_operation(session):
        if not session.frames:
            raise HTTPException(400, "Upload a swimming image or video first.")
        try:
            service.analyze(session, SwimmerProfile(**data.profile.model_dump()), data.category, data.options, x_openai_key)
        except Exception as exc:
            raise api_error(exc) from exc
        return service.public_state(session)


@router.post("/chat")
def chat(
    data: ChatInput, session: service.AnalysisSession = Depends(current_session),
    x_openai_key: Optional[str] = Header(None),
):
    with session_operation(session):
        if not session.analysis:
            raise HTTPException(400, "Analyze your footage before asking the coach a question.")
        question = data.message.strip()
        if not question:
            raise HTTPException(400, "Type a question for your coach.")
        if len(session.chat_messages) >= 100:
            raise HTTPException(400, "This conversation is full. Download your report, then start a new analysis.")
        try:
            service.follow_up(session, question, data.options, x_openai_key)
        except Exception as exc:
            raise api_error(exc) from exc
        return {"chat_messages": session.chat_messages, "profile": asdict(session.profile)}


@router.get("/report")
def report(session: service.AnalysisSession = Depends(current_session)):
    with session_operation(session):
        if not session.analysis:
            raise HTTPException(400, "Complete an analysis to download a report.")
        markdown = build_report(
            profile=session.profile, category=session.category, analysis_markdown=session.analysis_markdown,
            analysis_json=session.analysis, pose_metrics=session.pose_metrics, chat_messages=session.chat_messages,
        )
        return Response(markdown, media_type="text/markdown", headers={"Content-Disposition": 'attachment; filename="swim_analysis_report.md"'})
