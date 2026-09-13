from __future__ import annotations

import os

DEFAULT_KNOWLEDGE_MD = """
# Swim Coaching Cue + Drill Bank (compact)

## Global priorities
- Long line: head neutral, hips high, ribcage down, gentle core tension.
- Timing beats power: connect pull to hip rotation (free/back), body undulation (fly), line + kick (breast).

## Freestyle common faults -> cues -> drills
- Hips sinking -> Cue: "press chest, hide head, breathe with one goggle in"
  - Drill: Superman glide + 6-kick switch
- Crossover entry -> Cue: "hands in front of shoulder, rails not X"
  - Drill: Catch-up with shoulder-width entry marks
- Dropped elbow catch -> Cue: "show armpit, fingertips down, anchor early"
  - Drill: Scull #1 (front scull) + fingertip drag

## Starts, turns, underwater, kicks
- Starts: tight streamline, clean entry, fast transition to breakout.
- Turns: approach speed, compact rotation, feet placement, tight push-off line.
- Underwater: streamline first, dolphin kick rhythm, depth control, clean breakout.
- Kicks: narrow amplitude, kick from hips, relaxed ankles, rhythm that supports the stroke.
""".strip()


def load_knowledge(path: str = "swim_knowledge.md") -> str:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read().strip()
                return text if text else DEFAULT_KNOWLEDGE_MD
        except OSError:
            return DEFAULT_KNOWLEDGE_MD
    return DEFAULT_KNOWLEDGE_MD

