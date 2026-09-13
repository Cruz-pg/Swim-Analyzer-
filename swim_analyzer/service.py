"""Framework-independent, session-scoped analysis and coaching workflows."""
from __future__ import annotations

import os
import secrets
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from openai import OpenAI
from PIL import Image

from .constants import FOLLOW_UP_CONTEXT_TURNS
from .knowledge import load_knowledge
from .media import build_media_content, image_to_base64
from .openai_client import chat_with_context, initial_analysis_with_structured_outputs
from .pose import analyze_pose
from .prompts import (
    FOLLOW_UP_SYSTEM_APPEND, build_analysis_summary_from_json, build_follow_up_prompt,
    build_initial_prompt, build_system_message, format_swimmer_profile,
    render_initial_analysis_markdown,
)
from .schemas import InitialSwimAnalysis, SwimmerProfile


@dataclass
class AnalysisSession:
    profile: SwimmerProfile = field(default_factory=SwimmerProfile)
    frames: List[Image.Image] = field(default_factory=list)
    media_name: str = ""
    media_type: str = ""
    duration: float = 0.0
    category: str = "general"
    analysis: Optional[Dict[str, Any]] = None
    analysis_markdown: str = ""
    summary: str = ""
    chat_messages: List[dict] = field(default_factory=list)
    pose_metrics: List[str] = field(default_factory=list)
    pose_warning: str = ""
    annotated_frames: List[Image.Image] = field(default_factory=list)
    last_used: float = field(default_factory=time.monotonic)
    lock: Any = field(default_factory=threading.Lock, repr=False)

    def clear_analysis(self) -> None:
        self.analysis = None
        self.analysis_markdown = ""
        self.summary = ""
        self.chat_messages = []
        self.pose_metrics = []
        self.pose_warning = ""
        self.annotated_frames = []
        self.profile.coach_notes = ""

    def clear_media(self) -> None:
        self.clear_analysis()
        self.frames = []
        self.media_name = ""
        self.media_type = ""
        self.duration = 0.0


class SessionStore:
    """Bounded, ephemeral local sessions. Active operations are never evicted."""
    def __init__(self, capacity: int = 8, ttl: int = 3600):
        self.capacity, self.ttl = capacity, ttl
        self.sessions: Dict[str, AnalysisSession] = {}
        self.lock = threading.Lock()

    def get(self, token: Optional[str]) -> Optional[AnalysisSession]:
        with self.lock:
            now = time.monotonic()
            for key, session in list(self.sessions.items()):
                if now - session.last_used > self.ttl and not session.lock.locked():
                    del self.sessions[key]
            session = self.sessions.get(token or "")
            if session:
                session.last_used = now
            return session

    def create(self) -> tuple[str, AnalysisSession]:
        with self.lock:
            if len(self.sessions) >= self.capacity:
                idle = [(key, value) for key, value in self.sessions.items() if not value.lock.locked()]
                if not idle:
                    raise RuntimeError("All sessions are busy. Please try again shortly.")
                oldest = min(idle, key=lambda item: item[1].last_used)[0]
                del self.sessions[oldest]
            token = secrets.token_urlsafe(32)
            session = AnalysisSession()
            self.sessions[token] = session
            return token, session


def image_url(image: Image.Image) -> str:
    return "data:image/jpeg;base64," + image_to_base64(image)


def public_state(session: AnalysisSession) -> dict:
    return {
        "profile": asdict(session.profile), "category": session.category,
        "media": {
            "name": session.media_name, "type": session.media_type,
            "duration": session.duration, "frame_count": len(session.frames),
            "frames": [image_url(frame) for frame in session.frames],
        } if session.frames else None,
        "analysis": session.analysis, "analysis_markdown": session.analysis_markdown,
        "chat_messages": session.chat_messages, "pose_metrics": session.pose_metrics,
        "pose_warning": session.pose_warning,
        "annotated_frames": [image_url(frame) for frame in session.annotated_frames[:6]],
    }


def client_for(api_key: Optional[str]) -> OpenAI:
    key = (api_key or os.getenv("OPENAI_API_KEY", "")).strip()
    if not key or key == "sk-your-key":
        raise ValueError("Add your OpenAI API key in Settings to start your analysis.")
    return OpenAI(api_key=key, timeout=120.0, max_retries=1)


def analyze(session: AnalysisSession, profile: SwimmerProfile, category: str, options: Any, api_key: Optional[str]) -> None:
    """Commit results together, so failed retries never destroy a good analysis."""
    profile.coach_notes = ""
    with client_for(api_key) as client:
        pose = analyze_pose(session.frames) if options.pose_enabled else None
        metrics = pose.metrics if pose else []
        content = [{"type": "input_text", "text": build_initial_prompt(
            category=category, is_video=session.media_type == "video",
            swimmer_profile_text=format_swimmer_profile(profile), pose_metrics=metrics,
        )}]
        content.extend(build_media_content(session.frames, detail=options.image_detail))
        result = initial_analysis_with_structured_outputs(
            client=client, messages=[{"role": "user", "content": content}],
            model=options.model, system_message=build_system_message(load_knowledge()), temperature=0.2,
        )
    result["analysis_category"] = category
    if metrics and not result.get("pose_metrics"):
        result["pose_metrics"] = metrics
    if InitialSwimAnalysis is not None:
        result = InitialSwimAnalysis.model_validate(result).model_dump()
    markdown = render_initial_analysis_markdown(result)
    summary = build_analysis_summary_from_json(result)
    profile.coach_notes = " | ".join(
        f"{item['problem']} -> {item['cue']}" for item in result["top_3_priorities"]
    )[:400]
    session.clear_analysis()
    session.profile = profile
    session.category = category
    session.analysis = result
    session.analysis_markdown = markdown
    session.summary = summary
    session.pose_metrics = metrics
    session.pose_warning = pose.warning if pose else ""
    session.annotated_frames = pose.annotated_frames if pose else []


def follow_up(session: AnalysisSession, question: str, options: Any, api_key: Optional[str]) -> str:
    prompt = build_follow_up_prompt(
        user_question=question, swimmer_profile_text=format_swimmer_profile(session.profile),
        initial_summary=session.summary, category=session.category,
    )
    messages = []
    for message in session.chat_messages[-FOLLOW_UP_CONTEXT_TURNS:]:
        kind = "output_text" if message["role"] == "assistant" else "input_text"
        messages.append({"role": message["role"], "content": [{"type": kind, "text": message["content"]}]})
    content = [{"type": "input_text", "text": prompt}]
    if options.include_media_on_followup:
        content.extend(build_media_content(session.frames, detail=options.image_detail))
    messages.append({"role": "user", "content": content})
    with client_for(api_key) as client:
        answer = chat_with_context(
            client=client, messages=messages, model=options.model,
            system_message=build_system_message(load_knowledge(), append_text=FOLLOW_UP_SYSTEM_APPEND),
            temperature=options.temperature,
        )
    session.chat_messages.extend([
        {"role": "user", "content": question}, {"role": "assistant", "content": answer},
    ])
    note = " ".join(answer.split())[:300]
    session.profile.coach_notes = (session.profile.coach_notes + " | " + note)[-400:]
    session.summary = build_analysis_summary_from_json(session.analysis or {})
    return answer
