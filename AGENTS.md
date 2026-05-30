# Agent Project Notes

This file is the shared agent handoff for the Swim Form Analyzer project. Any coding assistant or automation agent should read it before making structural changes.

## Current Status

The project has been consolidated into one Streamlit app. The old standalone apps and generated Python caches were removed. There is no active `legacy/` folder dependency.

The app is not currently inside a Git repository in this workspace, so be careful with deletes and broad rewrites.

## Runbook

```bash
source .venv/bin/activate
streamlit run app.py
```

Required configuration:

```bash
OPENAI_API_KEY=sk-your-key
```

The key can come from `.env`, the environment, or the Streamlit sidebar.

## Architecture

- `app.py`
  Streamlit entrypoint. Owns session state, sidebar controls, upload UI, analysis trigger, follow-up chat, and report download.

- `swim_analyzer/constants.py`
  Shared app limits, accepted upload extensions, default model list, and analysis category labels.

- `swim_analyzer/media.py`
  Upload validation, image normalization/resizing, base64 image content creation, video metadata checks, and frame extraction.

- `swim_analyzer/openai_client.py`
  OpenAI Responses API calls, temperature fallback, structured-output parsing, and JSON extraction fallback.

- `swim_analyzer/pose.py`
  Optional MediaPipe pose estimation. Prefers `pose_landmarker_heavy.task` when available, then falls back to MediaPipe's built-in pose solution.

- `swim_analyzer/prompts.py`
  Coaching system prompt, category instructions, initial prompt builder, follow-up prompt builder, and Markdown rendering for structured analysis.

- `swim_analyzer/schemas.py`
  `SwimmerProfile` dataclass plus optional Pydantic models and the manual JSON schema used for structured analysis.

- `swim_analyzer/knowledge.py`
  Loads `swim_knowledge.md`; includes compact fallback knowledge if the file is unavailable.

- `swim_analyzer/report.py`
  Builds the downloadable Markdown report.

- `swim_knowledge.md`
  The coaching cue and drill knowledge base injected into system prompts.

- `pose_landmarker_heavy.task`
  Optional MediaPipe model file. Large, but used by pose estimation when present.

## Cleanup Decisions Already Made

Removed:

- `legacy/`
- root `__pycache__/`
- `swim_analyzer/__pycache__/`
- `swim_analyzer/setup.md`
- `swim_analyzer/notes.txt`

Kept:

- `.env` because it is local runtime config and ignored.
- `.venv/` because it is the local environment and ignored.
- `.vscode/` because it may contain local editor settings.
- `pose_landmarker_heavy.task` because pose estimation still searches for it.

## Development Guidelines

- Keep `app.py` as the UI orchestration layer; move reusable logic into `swim_analyzer/`.
- Prefer updating prompts in `prompts.py` and coaching content in `swim_knowledge.md` instead of hardcoding coaching text in `app.py`.
- Keep upload validation and media processing in `media.py`.
- Keep OpenAI API request/response handling in `openai_client.py`.
- Treat pose metrics as hints only. Do not make the app present MediaPipe values as definitive technique conclusions.
- Avoid reintroducing archive folders or duplicate standalone apps.
- Do not commit secrets, virtual environments, generated reports, or bytecode caches.

## Verification Checklist

After code changes, run:

```bash
python -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in [pathlib.Path('app.py'), *pathlib.Path('swim_analyzer').glob('*.py')]]; print('syntax ok')"
python -c "import app; print('import ok')"
```

The second command may print a Streamlit bare-mode warning when not launched through `streamlit run`; that is expected.

For UI changes, run the app with:

```bash
streamlit run app.py
```

Then test upload, initial analysis, follow-up chat, and report download manually.
