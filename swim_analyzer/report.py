from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from .constants import ANALYSIS_CATEGORIES
from .schemas import SwimmerProfile


def build_report(
    profile: SwimmerProfile,
    category: str,
    analysis_markdown: str,
    analysis_json: Dict[str, Any] | None,
    pose_metrics: List[str] | None,
    chat_messages: List[dict],
) -> str:
    lines: List[str] = []
    lines.append("# Swim Analysis Report")
    lines.append("")
    lines.append(f"Category: {ANALYSIS_CATEGORIES.get(category, category)}")
    lines.append("")
    lines.append("## Swimmer Context")
    profile_data = asdict(profile)
    wrote_profile = False
    for key, value in profile_data.items():
        if value:
            lines.append(f"- {key.replace('_', ' ').title()}: {value}")
            wrote_profile = True
    if not wrote_profile:
        lines.append("- No swimmer context provided.")
    if pose_metrics:
        lines.append("")
        lines.append("## Pose Estimation Hints")
        lines.extend(f"- {metric}" for metric in pose_metrics)
    lines.append("")
    lines.append("## Initial Analysis")
    lines.append(analysis_markdown or "No analysis available.")
    if analysis_json:
        lines.append("")
        lines.append("## Structured Summary")
        lines.append(f"- Action/stroke: {analysis_json.get('stroke_id', {}).get('label', 'unclear')}")
        for item in analysis_json.get("top_3_priorities", []):
            lines.append(f"- Priority {item.get('rank', '?')}: {item.get('problem', '')} -> {item.get('cue', '')}")
    display_messages = [msg for msg in chat_messages if msg.get("display", True)]
    if display_messages:
        lines.append("")
        lines.append("## Chat Transcript")
        for msg in display_messages:
            role = msg.get("role", "message").title()
            lines.append(f"**{role}:** {msg.get('content', '')}")
            lines.append("")
    return "\n".join(lines).strip() + "\n"

