from __future__ import annotations

import os
from dataclasses import asdict
from typing import List

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from swim_analyzer.constants import (
    ACCEPTED_IMAGE_EXTENSIONS,
    ACCEPTED_VIDEO_EXTENSIONS,
    ANALYSIS_CATEGORIES,
    DEFAULT_MODELS,
    FOLLOW_UP_CONTEXT_TURNS,
    MAX_UPLOAD_MB,
    MAX_VIDEO_SECONDS,
)
from swim_analyzer.knowledge import load_knowledge
from swim_analyzer.media import (
    build_media_content,
    build_processing_signature,
    extract_frames_from_uploaded_video,
    file_bytes_hash,
    process_uploaded_image,
    validate_extension,
    validate_upload_size,
)
from swim_analyzer.openai_client import chat_with_context, initial_analysis_with_structured_outputs
from swim_analyzer.pose import analyze_pose
from swim_analyzer.prompts import (
    FOLLOW_UP_SYSTEM_APPEND,
    build_analysis_summary_from_json,
    build_follow_up_prompt,
    build_initial_prompt,
    build_system_message,
    format_swimmer_profile,
    render_initial_analysis_markdown,
)
from swim_analyzer.report import build_report
from swim_analyzer.schemas import SwimmerProfile

load_dotenv()

st.set_page_config(page_title="Swim Form Analyzer", page_icon="Swim", layout="wide")


def default_swimmer_profile() -> SwimmerProfile:
    return SwimmerProfile()


def init_session_state() -> None:
    defaults = {
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "chat_messages": [],
        "media_content": None,
        "media_type": None,
        "initial_analysis_done": False,
        "analysis_summary": "",
        "analysis_markdown": "",
        "analysis_json": None,
        "last_uploaded_hash": None,
        "last_uploaded_name": None,
        "media_processing_signature": None,
        "swimmer_profile": default_swimmer_profile(),
        "analysis_category": "general",
        "smart_frames": True,
        "pose_enabled": False,
        "pose_metrics": [],
        "pose_warning": "",
        "annotated_frames": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_analysis_state(clear_media: bool = False) -> None:
    st.session_state.chat_messages = []
    st.session_state.initial_analysis_done = False
    st.session_state.analysis_summary = ""
    st.session_state.analysis_markdown = ""
    st.session_state.analysis_json = None
    st.session_state.pose_metrics = []
    st.session_state.pose_warning = ""
    st.session_state.annotated_frames = []
    if clear_media:
        st.session_state.media_content = None
        st.session_state.media_type = None
        st.session_state.last_uploaded_hash = None
        st.session_state.last_uploaded_name = None
        st.session_state.media_processing_signature = None


def update_profile_memory_from_json(profile: SwimmerProfile, data: dict) -> SwimmerProfile:
    parts: List[str] = []
    for item in data.get("top_3_priorities", [])[:3]:
        problem = item.get("problem", "").strip()
        cue = item.get("cue", "").strip()
        if problem or cue:
            parts.append(f"{problem} -> {cue}".strip(" ->"))
    if parts:
        profile.coach_notes = " | ".join(parts)[:400]
    return profile


def update_profile_memory_from_followup(profile: SwimmerProfile, response_text: str) -> SwimmerProfile:
    snippet = " ".join(response_text.strip().split())[:300]
    if snippet:
        existing = profile.coach_notes.strip()
        profile.coach_notes = (f"{existing} || {snippet}" if existing else snippet)[-400:]
    return profile


def build_follow_up_messages(user_prompt: str, include_media: bool, image_detail: str) -> List[dict]:
    swimmer_profile_text = format_swimmer_profile(st.session_state.swimmer_profile)
    initial_summary = st.session_state.analysis_summary or "No prior visual analysis summary available."
    prompt = build_follow_up_prompt(
        user_question=user_prompt,
        swimmer_profile_text=swimmer_profile_text,
        initial_summary=initial_summary,
        category=st.session_state.analysis_category,
    )
    recent_messages = [msg for msg in st.session_state.chat_messages if msg.get("display", True)][-FOLLOW_UP_CONTEXT_TURNS:]
    api_messages: List[dict] = []
    for msg in recent_messages:
        if msg["role"] == "assistant":
            api_messages.append({"role": "assistant", "content": [{"type": "output_text", "text": msg["content"]}]})
        elif msg["role"] == "user":
            api_messages.append({"role": "user", "content": [{"type": "input_text", "text": msg["content"]}]})
    content = [{"type": "input_text", "text": prompt}]
    if include_media and st.session_state.media_content:
        content.append({"type": "input_text", "text": "The uploaded media is included again for this answer. Re-check visual details against these frames/images."})
        content.extend(build_media_content(st.session_state.media_content or [], detail=image_detail))
    api_messages.append({"role": "user", "content": content})
    return api_messages


def handle_api_exception(exc: Exception) -> None:
    error_message = str(exc)
    lowered = error_message.lower()
    if "api key" in lowered or "authentication" in lowered or "unauthorized" in lowered:
        st.error("Invalid API key. Please check your OpenAI API key.")
    elif "rate limit" in lowered:
        st.error("Rate limit exceeded. Please wait a moment and try again.")
    elif "model" in lowered and ("not found" in lowered or "does not exist" in lowered or "not available" in lowered):
        st.error("Model not available for this API key. Try a different model or enter a custom model ID.")
    else:
        st.error(f"Error: {error_message}")


def render_sidebar() -> tuple[str, float, int, str, bool]:
    with st.sidebar:
        st.header("Settings")
        api_key_input = st.text_input(
            "OpenAI API Key",
            type="password",
            value=st.session_state.api_key,
            help="Loaded from .env or OPENAI_API_KEY when available. This sidebar value only lives in Streamlit session state.",
        )
        if api_key_input != st.session_state.api_key:
            st.session_state.api_key = api_key_input
        st.divider()
        with st.expander("Swimmer Context", expanded=True):
            st.caption("Optional details help tailor general analysis, strokes, starts, turns, underwater work, kicks, and finishes.")
            prof: SwimmerProfile = st.session_state.swimmer_profile
            prof.goal = st.text_input("Goal / session objective", value=prof.goal, placeholder="Drop time in 100 free, cleaner turns, better breakout")
            prof.skill_level = st.selectbox(
                "Swimmer level",
                ["Beginner", "Intermediate", "Advanced", "Competitive"],
                index=["Beginner", "Intermediate", "Advanced", "Competitive"].index(prof.skill_level),
            )
            prof.primary_stroke = st.text_input("Stroke or skill focus", value=prof.primary_stroke, placeholder="Freestyle, breaststroke, starts, flip turns, underwater")
            prof.distance = st.text_input("Event / distance context", value=prof.distance, placeholder="25/50/100/200+, open water, drill set")
            pace_options = ["Unknown", "Easy", "Technique drill", "Moderate", "Race pace", "Sprint"]
            pace_index = pace_options.index(prof.pace_context) if prof.pace_context in pace_options else 0
            prof.pace_context = st.selectbox("Effort / pace", pace_options, index=pace_index)
            prof.breathing = st.text_input("Breathing / rhythm notes", value=prof.breathing, placeholder="Every 3, bilateral, breath timing issue, not relevant")
            environment_options = ["Pool", "Open water", "Endless pool", "Starting block", "Wall / turn practice", "Unknown"]
            environment_index = environment_options.index(prof.environment) if prof.environment in environment_options else 0
            prof.environment = st.selectbox("Environment / setup", environment_options, index=environment_index)
            prof.camera_angle = st.text_input("Camera view", value=prof.camera_angle, placeholder="Side, head-on, rear, above water, underwater, deck")
            prof.pain = st.text_input("Pain / injury notes", value=prof.pain, placeholder="Optional; app will avoid medical diagnosis")
            prof.known_issues = st.multiselect(
                "Known focus areas",
                [
                    "Body position",
                    "Breathing",
                    "Catch",
                    "Kick",
                    "Timing",
                    "Rotation",
                    "Streamline",
                    "Start",
                    "Dive / entry",
                    "Turn",
                    "Wall approach",
                    "Push-off",
                    "Underwater",
                    "Breakout",
                    "Finish",
                ],
                default=prof.known_issues,
            )
            if prof.coach_notes:
                st.caption("Coach notes")
                st.code(prof.coach_notes)
            st.session_state.swimmer_profile = prof
        st.divider()
        with st.expander("Advanced", expanded=True):
            selected_model = st.selectbox("Model", DEFAULT_MODELS, index=0)
            custom_model = st.text_input("Custom model ID", value="", placeholder="Optional")
            model = custom_model.strip() or selected_model
            temperature = st.slider("Creativity", 0.0, 1.2, 0.6, 0.1)
            max_frames = st.slider("Max video frames", 5, 20, 10)
            image_detail = st.selectbox("Image detail", ["auto", "low", "high"], index=0)
            st.session_state.smart_frames = st.checkbox("Smart frame selection", value=st.session_state.smart_frames)
            pose_enabled = st.checkbox("Use pose estimation beta", value=st.session_state.pose_enabled)
            if pose_enabled != st.session_state.pose_enabled:
                st.session_state.pose_enabled = pose_enabled
                reset_analysis_state(clear_media=False)
            include_media_on_followup = st.checkbox(
                "Re-include media in follow-up chat",
                value=False,
                help="Costs more, but lets visual follow-up questions re-check the uploaded image/frames.",
            )
        st.divider()
        if st.button("Reset Conversation", use_container_width=True):
            reset_analysis_state(clear_media=False)
            st.rerun()
        if st.button("Reset Swimmer Info", use_container_width=True):
            st.session_state.swimmer_profile = default_swimmer_profile()
            st.rerun()
    return model, temperature, max_frames, image_detail, include_media_on_followup


def render_upload_area(max_frames: int) -> None:
    st.subheader("Upload Media")
    st.caption(f"Limits: images/videos under {MAX_UPLOAD_MB} MB; videos under {MAX_VIDEO_SECONDS:.0f}s.")
    specific_categories = [key for key in ANALYSIS_CATEGORIES.keys() if key != "general"]
    current_specific_category = st.session_state.analysis_category if st.session_state.analysis_category in specific_categories else None
    if "analysis_focus_select" not in st.session_state:
        st.session_state.analysis_focus_select = current_specific_category
    if current_specific_category is None:
        st.session_state.analysis_focus_select = None
    selected_category = st.selectbox(
        "Analysis focus (optional)",
        specific_categories,
        format_func=lambda key: ANALYSIS_CATEGORIES[key],
        index=specific_categories.index(current_specific_category) if current_specific_category else None,
        placeholder="General analysis (no specific category)",
        key="analysis_focus_select",
    )
    category = selected_category or "general"
    if category != st.session_state.analysis_category:
        st.session_state.analysis_category = category
        reset_analysis_state(clear_media=False)
    media_type_ui = st.radio("Media type", ["Image", "Video"], horizontal=True)
    if media_type_ui == "Image":
        uploaded_file = st.file_uploader("Choose a swimming image", type=sorted(ext.lstrip(".") for ext in ACCEPTED_IMAGE_EXTENSIONS), key="image_uploader")
        if uploaded_file:
            try:
                file_bytes = uploaded_file.getvalue()
                validate_extension(uploaded_file.name, ACCEPTED_IMAGE_EXTENSIONS, "image")
                validate_upload_size(file_bytes)
                current_hash = file_bytes_hash(file_bytes)
                image = process_uploaded_image(uploaded_file, file_bytes)
                st.image(image, caption="Uploaded image", use_container_width=True)
                signature = build_processing_signature(current_hash, "image", 1, False, st.session_state.pose_enabled)
                if st.session_state.media_processing_signature != signature:
                    reset_analysis_state(clear_media=False)
                    st.session_state.media_content = [image]
                    st.session_state.media_type = "image"
                    st.session_state.last_uploaded_hash = current_hash
                    st.session_state.last_uploaded_name = uploaded_file.name
                    st.session_state.media_processing_signature = signature
            except Exception as exc:
                st.error(f"Could not load image: {exc}")
    else:
        uploaded_file = st.file_uploader("Choose a swimming video", type=sorted(ext.lstrip(".") for ext in ACCEPTED_VIDEO_EXTENSIONS), key="video_uploader")
        if uploaded_file:
            try:
                file_bytes = uploaded_file.getvalue()
                validate_extension(uploaded_file.name, ACCEPTED_VIDEO_EXTENSIONS, "video")
                validate_upload_size(file_bytes)
                st.video(file_bytes)
                current_hash = file_bytes_hash(file_bytes)
                signature = build_processing_signature(current_hash, "video", max_frames, st.session_state.smart_frames, st.session_state.pose_enabled)
                if st.session_state.media_processing_signature != signature:
                    with st.spinner("Extracting key frames..."):
                        frames, duration = extract_frames_from_uploaded_video(uploaded_file, file_bytes, max_frames=max_frames, smart=st.session_state.smart_frames)
                    reset_analysis_state(clear_media=False)
                    st.session_state.media_content = frames
                    st.session_state.media_type = "video"
                    st.session_state.last_uploaded_hash = current_hash
                    st.session_state.last_uploaded_name = uploaded_file.name
                    st.session_state.media_processing_signature = signature
                    st.success(f"Extracted {len(frames)} frames from {duration:.1f}s video.")
                with st.expander("Preview extracted frames", expanded=False):
                    if st.session_state.media_content:
                        cols = st.columns(5)
                        for idx, frame in enumerate(st.session_state.media_content):
                            with cols[idx % 5]:
                                st.image(frame, caption=f"Frame {idx + 1}", use_container_width=True)
            except Exception as exc:
                st.error(f"Could not process video: {exc}")


def maybe_run_pose_beta() -> None:
    if not st.session_state.pose_enabled or not st.session_state.media_content:
        st.session_state.pose_metrics = []
        st.session_state.pose_warning = ""
        st.session_state.annotated_frames = []
        return
    with st.spinner("Running pose estimation beta..."):
        pose_result = analyze_pose(st.session_state.media_content)
    st.session_state.pose_metrics = pose_result.metrics
    st.session_state.pose_warning = pose_result.warning
    st.session_state.annotated_frames = pose_result.annotated_frames


def render_pose_output() -> None:
    if st.session_state.pose_warning:
        st.info(st.session_state.pose_warning)
    if st.session_state.pose_metrics:
        with st.expander("Pose estimation beta", expanded=False):
            for metric in st.session_state.pose_metrics:
                st.write(f"- {metric}")
            if st.session_state.annotated_frames:
                cols = st.columns(3)
                for idx, frame in enumerate(st.session_state.annotated_frames[:6]):
                    with cols[idx % 3]:
                        st.image(frame, caption=f"Pose frame {idx + 1}", use_container_width=True)


def render_analysis_and_chat(model: str, temperature: float, image_detail: str, include_media_on_followup: bool) -> None:
    st.subheader("Analysis & Chat")
    if not st.session_state.media_content:
        st.info("Upload an image or video to get started.")
        return
    if not st.session_state.api_key:
        st.warning("Enter your OpenAI API key in the sidebar to continue.")
        return

    if st.session_state.initial_analysis_done:
        if st.button("Re-analyze uploaded media", use_container_width=True):
            reset_analysis_state(clear_media=False)
            st.rerun()

    if not st.session_state.initial_analysis_done:
        if st.button("Start Analysis", type="primary", use_container_width=True):
            try:
                maybe_run_pose_beta()
                client = OpenAI(api_key=st.session_state.api_key)
                knowledge_md = load_knowledge()
                swimmer_profile_text = format_swimmer_profile(st.session_state.swimmer_profile)
                system_message = build_system_message(knowledge_md=knowledge_md)
                prompt_text = build_initial_prompt(
                    category=st.session_state.analysis_category,
                    is_video=(st.session_state.media_type == "video"),
                    swimmer_profile_text=swimmer_profile_text,
                    pose_metrics=st.session_state.pose_metrics,
                )
                content = [{"type": "input_text", "text": prompt_text}]
                content.extend(build_media_content(st.session_state.media_content or [], detail=image_detail))
                messages = [{"role": "user", "content": content}]
                with st.spinner("Analyzing technique..."):
                    analysis_json = initial_analysis_with_structured_outputs(
                        client=client,
                        messages=messages,
                        model=model,
                        system_message=system_message,
                        temperature=0.2,
                    )
                analysis_json["analysis_category"] = st.session_state.analysis_category
                if st.session_state.pose_metrics and not analysis_json.get("pose_metrics"):
                    analysis_json["pose_metrics"] = st.session_state.pose_metrics
                analysis_markdown = render_initial_analysis_markdown(analysis_json)
                st.session_state.swimmer_profile = update_profile_memory_from_json(st.session_state.swimmer_profile, analysis_json)
                st.session_state.analysis_json = analysis_json
                st.session_state.analysis_markdown = analysis_markdown
                st.session_state.analysis_summary = build_analysis_summary_from_json(analysis_json)
                st.session_state.chat_messages.append({"role": "user", "content": "Initial analysis request.", "display": False})
                st.session_state.chat_messages.append({"role": "assistant", "content": analysis_markdown, "display": True})
                st.session_state.initial_analysis_done = True
                st.rerun()
            except Exception as exc:
                handle_api_exception(exc)

    if st.session_state.initial_analysis_done:
        render_pose_output()
        st.markdown(st.session_state.analysis_markdown)
        st.caption("Follow-up chat uses the saved analysis summary by default. Turn on media re-checks in Advanced for visual follow-up questions.")
        chat_container = st.container(height=420)
        with chat_container:
            for msg in st.session_state.chat_messages:
                if msg.get("display", True):
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])
        if user_prompt := st.chat_input("Ask a question about the swimming technique..."):
            try:
                client = OpenAI(api_key=st.session_state.api_key)
                knowledge_md = load_knowledge()
                system_message = build_system_message(knowledge_md=knowledge_md, append_text=FOLLOW_UP_SYSTEM_APPEND)
                api_messages = build_follow_up_messages(user_prompt, include_media=include_media_on_followup, image_detail=image_detail)
                st.session_state.chat_messages.append({"role": "user", "content": user_prompt, "display": True})
                with st.spinner("Thinking..."):
                    response_text = chat_with_context(
                        client=client,
                        messages=api_messages,
                        model=model,
                        system_message=system_message,
                        temperature=temperature,
                    )
                st.session_state.swimmer_profile = update_profile_memory_from_followup(st.session_state.swimmer_profile, response_text)
                existing_summary = st.session_state.analysis_summary.strip()
                st.session_state.analysis_summary = (existing_summary + "\nFollow-up note: " + response_text.strip())[:2400]
                st.session_state.chat_messages.append({"role": "assistant", "content": response_text, "display": True})
                st.rerun()
            except Exception as exc:
                handle_api_exception(exc)
        report_text = build_report(
            profile=st.session_state.swimmer_profile,
            category=st.session_state.analysis_category,
            analysis_markdown=st.session_state.analysis_markdown,
            analysis_json=st.session_state.analysis_json,
            pose_metrics=st.session_state.pose_metrics,
            chat_messages=st.session_state.chat_messages,
        )
        st.download_button(
            "Download report",
            data=report_text,
            file_name="swim_analysis_report.md",
            mime="text/markdown",
            use_container_width=True,
        )
        with st.expander("Structured initial analysis JSON"):
            st.json(st.session_state.analysis_json)
        with st.expander("Swimmer profile state"):
            st.json(asdict(st.session_state.swimmer_profile))


def main() -> None:
    init_session_state()
    st.title("AI Swim Form Analyzer")
    st.write("Upload a swimming photo or short video for category-specific technique analysis, optional pose-estimation hints, and follow-up coaching chat.")
    model, temperature, max_frames, image_detail, include_media_on_followup = render_sidebar()
    col1, col2 = st.columns([1, 1])
    with col1:
        render_upload_area(max_frames=max_frames)
    with col2:
        render_analysis_and_chat(
            model=model,
            temperature=temperature,
            image_detail=image_detail,
            include_media_on_followup=include_media_on_followup,
        )


if __name__ == "__main__":
    main()
