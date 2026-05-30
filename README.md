# Swim Form Analyzer

A consolidated Streamlit app for analyzing swim technique from photos or short videos. The app combines OpenAI vision analysis, category-specific coaching prompts, optional MediaPipe pose hints, follow-up chat, and downloadable Markdown reports.

## Features

- Upload a swimming image or short video.
- Analyze general technique or focus on strokes, starts, turns, finishes, underwater work, or kicks.
- Extract representative video frames for model analysis.
- Use optional MediaPipe pose estimation as a beta hint layer.
- Save swimmer context during a session so follow-up coaching gets more specific.
- Ask follow-up questions after the initial analysis.
- Download a Markdown report with the analysis, pose hints, swimmer profile, and chat transcript.

## Project Structure

```text
.
├── app.py                    # Streamlit app entrypoint and UI flow
├── requirements.txt          # Python dependencies
├── swim_knowledge.md         # Coaching cue and drill knowledge base
├── pose_landmarker_heavy.task # Optional MediaPipe pose model
└── swim_analyzer/
    ├── constants.py          # Shared limits, model list, category labels
    ├── knowledge.py          # Knowledge-base loading with fallback text
    ├── media.py              # Upload validation, image prep, video frame extraction
    ├── openai_client.py      # OpenAI Responses API helpers and JSON parsing
    ├── pose.py               # Optional MediaPipe pose metrics and annotations
    ├── prompts.py            # System, initial-analysis, and follow-up prompts
    ├── report.py             # Markdown report builder
    └── schemas.py            # Swimmer profile and structured analysis schema
```

For future development context, see `AGENTS.md`.

## Setup

Use Python 3.10+ if you want MediaPipe pose estimation. The app can still run without pose estimation if MediaPipe is unavailable.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add your OpenAI API key to `.env`:

```bash
OPENAI_API_KEY=sk-your-key
```

You can also paste an API key into the Streamlit sidebar for local testing.

## Run

```bash
streamlit run app.py
```

Then open the local Streamlit URL shown in the terminal.

## Usage Notes

- Leave "Analysis focus" blank for general analysis.
- Choose a specific focus only when you want the app to inspect starts, turns, finishes, underwater work, kicks, or stroke technique.
- Keep video uploads short. The current limit is 30 seconds and 100 MB.
- Pose estimation is optional beta functionality. When enabled, the app uses `pose_landmarker_heavy.task` if present, then falls back to MediaPipe's built-in pose solution.
- If pose landmarks are unavailable or low confidence, the app falls back to normal visual analysis.

## Maintenance

- Keep reusable logic in `swim_analyzer/`; keep `app.py` focused on Streamlit state and layout.
- Update `swim_knowledge.md` when adding coaching cues, drills, or technique checkpoints.
- Do not commit `.env`, `.venv/`, generated reports, or `__pycache__/` directories.
