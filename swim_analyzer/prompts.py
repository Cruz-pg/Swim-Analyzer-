from __future__ import annotations

from typing import Any, Dict, List

from .constants import ANALYSIS_CATEGORIES
from .schemas import SwimmerProfile

SWIM_SYSTEM_PROMPT = """
You are an expert competitive swim coach and biomechanics-informed technique analyst.
You give specific, actionable feedback based on what is visible in the provided images/frames.

Rules:
- If visibility is limited, explicitly state what you can and cannot confirm from the angle/lighting.
- Ask at most 1-2 targeted follow-up questions only when needed.
- Prioritize: (1) body line, (2) timing, (3) propulsion, (4) breathing, (5) kick.
- Give corrections as: Observation -> Why it matters -> Fix cue -> Drill when relevant.
- Use swim-coach language: cues, tempo, catch, EVF, rotation, streamline, line, timing.
- Treat MediaPipe pose metrics as measurement hints only; never override visible evidence with weak metrics.
- Avoid medical diagnosis. If pain/injury is mentioned: advise seeing a qualified professional.
- Keep it concise by default: 3-6 key points unless asked for more.
""".strip()

INITIAL_ANALYSIS_INSTRUCTIONS = """
Return a structured swim analysis that matches the supplied schema.
Requirements:
- Use 1 to 3 technique priorities; do not force weak observations when visibility is poor.
- Use 1 to 3 drills.
- Use 1 to 2 filming suggestions.
- If something cannot be judged visually, say so in visibility, likely_cause, or cue fields.
- Keep cues concise and coach-like.
""".strip()

FOLLOW_UP_SYSTEM_APPEND = """
For follow-up chat answers:
- Answer in normal prose, not JSON.
- Use the existing analysis summary and chat context by default.
- Do not pretend you can see details beyond the uploaded media or the saved analysis.
- If the question depends on something not visible, say so explicitly.
- Default to concise swim-coach language.
""".strip()

CATEGORY_INSTRUCTIONS = {
    "general": "Analyze the most relevant swimming technique elements visible in the media. Choose the right lens yourself: stroke, start, turn, finish, underwater, kick, or a combination when appropriate.",
    "strokes": "Analyze stroke technique: body alignment, arm mechanics/hand entry, head position/breathing, kick timing/shape.",
    "starts": "Analyze start/dive technique: stance or launch position, body line, entry angle, streamline, and transition to breakout.",
    "turns": "Analyze turn technique: approach, wall timing, rotation, feet placement, push-off line, and breakout setup.",
    "finishes": "Analyze finish technique: final stroke timing, extension, head/body line, wall touch, and speed preservation.",
    "underwater": "Analyze underwater phase: streamline, dolphin kick rhythm, body wave, depth, and breakout timing.",
    "kicks": "Analyze kicking technique: hip-driven motion, knee bend, ankle relaxation, amplitude, rhythm, and line.",
}


def format_swimmer_profile(profile: SwimmerProfile) -> str:
    lines: List[str] = []
    if profile.goal:
        lines.append(f"- Goal/event: {profile.goal}")
    if profile.skill_level:
        lines.append(f"- Level: {profile.skill_level}")
    if profile.primary_stroke:
        lines.append(f"- Primary stroke focus: {profile.primary_stroke}")
    if profile.distance:
        lines.append(f"- Typical distance: {profile.distance}")
    if profile.pace_context:
        lines.append(f"- Effort/pace: {profile.pace_context}")
    if profile.breathing:
        lines.append(f"- Breathing pattern: {profile.breathing}")
    if profile.environment:
        lines.append(f"- Environment: {profile.environment}")
    if profile.camera_angle:
        lines.append(f"- Camera angle: {profile.camera_angle}")
    if profile.pain:
        lines.append(f"- Pain/injury notes: {profile.pain}")
    if profile.known_issues:
        lines.append(f"- Known focus areas: {', '.join(profile.known_issues)}")
    if profile.coach_notes:
        lines.append(f"- Coach notes so far: {profile.coach_notes}")
    return "\n".join(lines) if lines else "- (No swimmer context provided.)"


def build_system_message(knowledge_md: str, append_text: str = "") -> dict:
    text_parts = [
        SWIM_SYSTEM_PROMPT,
        "COACHING KNOWLEDGE BASE (use this drill/cue bank and checkpoints):\n" + knowledge_md.strip(),
    ]
    if append_text.strip():
        text_parts.append(append_text.strip())
    return {"role": "system", "content": [{"type": "input_text", "text": "\n\n---\n\n".join(text_parts)}]}


def build_initial_prompt(category: str, is_video: bool, swimmer_profile_text: str, pose_metrics: List[str] | None = None) -> str:
    category_label = ANALYSIS_CATEGORIES.get(category, category)
    media_prefix = "These are frames from a swimming video." if is_video else "This is a swimming image."
    pose_text = "\n".join(f"- {metric}" for metric in (pose_metrics or [])) or "- No high-confidence pose metrics supplied."
    return f"""{media_prefix}

ANALYSIS CATEGORY:
{category} ({category_label})

SWIMMER CONTEXT:
{swimmer_profile_text}

POSE ESTIMATION HINTS:
{pose_text}

TASK:
1) Identify what swimming action or stroke is being performed.
2) {CATEGORY_INSTRUCTIONS.get(category, CATEGORY_INSTRUCTIONS["strokes"])}
3) Tailor advice to the swimmer context.
4) Return the result in the requested structured format.

IMPORTANT:
- If underwater view is missing, do NOT confidently diagnose catch mechanics; state limitations.
- If MediaPipe hints are absent or weak, ignore them and rely on visible evidence.
- If the category is general, choose the most relevant analysis lens based on the media instead of forcing a narrow category.
- If visibility is limited, reflect that in the structured output.
- Set analysis_category to exactly "{category}".
- Keep cues concise and specific.

{INITIAL_ANALYSIS_INSTRUCTIONS}
""".strip()


def build_follow_up_prompt(user_question: str, swimmer_profile_text: str, initial_summary: str, category: str) -> str:
    return f"""ANALYSIS CATEGORY:
{category}

SWIMMER CONTEXT:
{swimmer_profile_text}

INITIAL VISUAL ANALYSIS SUMMARY:
{initial_summary}

USER QUESTION:
{user_question}

INSTRUCTIONS:
- Answer using the saved visual analysis summary and prior chat context by default.
- Do not pretend you can see any new details unless uploaded media was explicitly included in this request.
- If the user asks for a fuller explanation, expand.
- Otherwise answer concisely using Observation -> Why it matters -> Cue -> Drill when relevant.
- If the question depends on details that were not visible in the uploaded media or saved summary, say so explicitly.
""".strip()


def render_initial_analysis_markdown(data: Dict[str, Any]) -> str:
    category = data.get("analysis_category", "general")
    stroke = data.get("stroke_id", {})
    visibility = data.get("visibility", {})
    priorities = data.get("top_3_priorities", [])
    drills = data.get("drills", [])
    film_next = data.get("what_to_film_next", [])
    pose_metrics = data.get("pose_metrics") or []

    lines: List[str] = []
    lines.append(f"**Category:** {ANALYSIS_CATEGORIES.get(category, category)}")
    lines.append("")
    lines.append("**1) Action / stroke ID + confidence %**")
    lines.append(f"{stroke.get('label', 'unclear')} - {stroke.get('confidence_pct', 'N/A')}%")
    lines.append("")
    lines.append("**2) What I can see vs what I cannot see**")
    can_see = visibility.get("can_see", [])
    cannot_see = visibility.get("cannot_see", [])
    if can_see:
        lines.append("**Can see:**")
        lines.extend(f"- {item}" for item in can_see)
    else:
        lines.append("- Can see: Not clearly specified.")
    if cannot_see:
        lines.append("**Cannot see:**")
        lines.extend(f"- {item}" for item in cannot_see)
    else:
        lines.append("- Cannot see: Not clearly specified.")
    if pose_metrics:
        lines.append("")
        lines.append("**Pose estimation hints:**")
        lines.extend(f"- {item}" for item in pose_metrics)
    lines.append("")
    lines.append("**3) Top priorities**")
    for item in priorities:
        lines.append(f"{item.get('rank', '?')}. **Problem:** {item.get('problem', '')}")
        lines.append(f"   **Likely cause:** {item.get('likely_cause', '')}")
        lines.append(f"   **Cue:** {item.get('cue', '')}")
    lines.append("")
    lines.append("**4) Drills**")
    for item in drills:
        lines.append(f"- **{item.get('name', '')}** -> **How:** {item.get('how', '')} -> **Why:** {item.get('why', '')}")
    lines.append("")
    lines.append("**5) What to film next**")
    for item in film_next:
        lines.append(f"- **Angle:** {item.get('angle', '')} -> **Distance:** {item.get('distance', '')}")
    return "\n".join(lines).strip()


def build_analysis_summary_from_json(data: Dict[str, Any], max_chars: int = 1800) -> str:
    parts: List[str] = []
    parts.append(f"Category: {data.get('analysis_category', 'general')}")
    stroke = data.get("stroke_id", {})
    parts.append(f"Action/stroke: {stroke.get('label', 'unclear')} ({stroke.get('confidence_pct', 'N/A')}%)")
    visibility = data.get("visibility", {})
    if visibility.get("can_see"):
        parts.append("Can see: " + "; ".join(visibility.get("can_see", [])[:3]))
    if visibility.get("cannot_see"):
        parts.append("Cannot see: " + "; ".join(visibility.get("cannot_see", [])[:3]))
    if data.get("pose_metrics"):
        parts.append("Pose hints: " + "; ".join(data.get("pose_metrics", [])[:4]))
    for item in data.get("top_3_priorities", [])[:3]:
        parts.append(f"P{item.get('rank', '?')}: {item.get('problem', '')} | Cause: {item.get('likely_cause', '')} | Cue: {item.get('cue', '')}")
    drills = data.get("drills", [])
    if drills:
        parts.append("Drills: " + "; ".join(d.get("name", "") for d in drills[:3]))
    return "\n".join(parts).strip()[:max_chars].rstrip()
