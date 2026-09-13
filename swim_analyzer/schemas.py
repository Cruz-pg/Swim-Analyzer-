from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover
    BaseModel = None  # type: ignore
    Field = None  # type: ignore


@dataclass
class SwimmerProfile:
    goal: str = ""
    skill_level: str = "Intermediate"
    primary_stroke: str = ""
    distance: str = ""
    pace_context: str = "Unknown"
    breathing: str = ""
    environment: str = "Pool"
    camera_angle: str = ""
    pain: str = ""
    known_issues: List[str] = field(default_factory=list)
    coach_notes: str = ""


if BaseModel is not None:
    class StrokeId(BaseModel):
        label: str = Field(description="freestyle, backstroke, breaststroke, butterfly, individual medley, start, turn, finish, underwater, kick, or unclear")
        confidence_pct: int = Field(ge=0, le=100)

    class Visibility(BaseModel):
        can_see: List[str]
        cannot_see: List[str]

    class TechniquePriority(BaseModel):
        rank: int = Field(ge=1, le=3)
        problem: str
        likely_cause: str
        cue: str

    class Drill(BaseModel):
        name: str
        how: str
        why: str

    class FilmingSuggestion(BaseModel):
        angle: str
        distance: str

    class InitialSwimAnalysis(BaseModel):
        analysis_category: str
        stroke_id: StrokeId
        visibility: Visibility
        pose_metrics: Optional[List[str]] = Field(default=None, description="High-confidence MediaPipe-derived measurement hints, if supplied.")
        top_3_priorities: List[TechniquePriority] = Field(min_length=1, max_length=3)
        drills: List[Drill] = Field(min_length=1, max_length=3)
        what_to_film_next: List[FilmingSuggestion] = Field(min_length=1, max_length=2)
else:
    InitialSwimAnalysis = None  # type: ignore


INITIAL_ANALYSIS_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "analysis_category",
        "stroke_id",
        "visibility",
        "pose_metrics",
        "top_3_priorities",
        "drills",
        "what_to_film_next",
    ],
    "properties": {
        "analysis_category": {"type": "string", "enum": ["general", "strokes", "starts", "turns", "finishes", "underwater", "kicks"]},
        "stroke_id": {
            "type": "object",
            "additionalProperties": False,
            "required": ["label", "confidence_pct"],
            "properties": {
                "label": {"type": "string"},
                "confidence_pct": {"type": "integer", "minimum": 0, "maximum": 100},
            },
        },
        "visibility": {
            "type": "object",
            "additionalProperties": False,
            "required": ["can_see", "cannot_see"],
            "properties": {
                "can_see": {"type": "array", "items": {"type": "string"}},
                "cannot_see": {"type": "array", "items": {"type": "string"}},
            },
        },
        "pose_metrics": {
            "type": ["array", "null"],
            "items": {"type": "string"},
        },
        "top_3_priorities": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["rank", "problem", "likely_cause", "cue"],
                "properties": {
                    "rank": {"type": "integer", "minimum": 1, "maximum": 3},
                    "problem": {"type": "string"},
                    "likely_cause": {"type": "string"},
                    "cue": {"type": "string"},
                },
            },
        },
        "drills": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "how", "why"],
                "properties": {
                    "name": {"type": "string"},
                    "how": {"type": "string"},
                    "why": {"type": "string"},
                },
            },
        },
        "what_to_film_next": {
            "type": "array",
            "minItems": 1,
            "maxItems": 2,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["angle", "distance"],
                "properties": {
                    "angle": {"type": "string"},
                    "distance": {"type": "string"},
                },
            },
        },
    },
}
