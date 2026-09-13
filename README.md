<div align="center">

# Swimform

**Upload swimming footage. Get technique priorities, coaching cues, and drills.**

A local-first swim technique studio: a React + TypeScript frontend, a FastAPI backend,
and a Python coaching engine that turns video frames into structured feedback.

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)
![Node](https://img.shields.io/badge/Node-22.12%2B-5FA04E?logo=nodedotjs&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-646CFF?logo=vite&logoColor=white)

</div>

---

## What it does

Drop in a clip of yourself swimming and Swimform identifies the stroke, ranks the three things
worth fixing first, explains the likely cause of each, and gives you a cue and a drill for it.
You can then ask the coach follow-up questions about your own footage and download the whole
session as Markdown.

| Panel | What you get |
|---|---|
| **Analyze** | Stroke identification with a confidence score, three ranked priorities, cause + coaching cue for each |
| **Drills** | Targeted drills with how to run them and why they address what the footage shows |
| **Details** | What the camera angle can and can't tell you, what to film next, and the raw structured output |
| **Coach chat** | Follow-up questions grounded in your clip, optionally re-checking the frames |
| **Report** | One-click Markdown export of the analysis, pose hints, and full transcript |

The app runs entirely on your machine — only the extracted frames and prompts leave it, for the
OpenAI API call. Fonts are bundled locally, so there are no external font or image requests.

## Quick start

**Requirements:** Node.js 22.12+ and Python 3.9+. Optional MediaPipe pose estimation needs Python 3.10+.

**1. Install dependencies**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
```

**2. Add your API key**

Keep your existing `.env`, or copy it from `.env.example`:

```dotenv
OPENAI_API_KEY=sk-your-key
```

You can also enter a key in **Settings** instead. A key typed there lives in that tab's memory
only and is cleared on refresh. Server-configured keys are never sent back to the browser.

**3. Run both servers**

```bash
npm run dev
```

Open **<http://127.0.0.1:5173>**. The frontend proxies `/api` to FastAPI on port 8000, and
Ctrl+C stops both. The launcher picks up `.venv` automatically — set `SWIMFORM_PYTHON` to
override the interpreter.

## Running it

| Mode | Commands | Open |
|---|---|---|
| **Development** | `npm run dev` | <http://127.0.0.1:5173> |
| **Production** | `npm run build`<br>`.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000` | <http://127.0.0.1:8000> |

In production FastAPI serves the compiled frontend from `dist/` alongside the API on one origin.
Build before starting the server, and restart it after the first build. `python app.py` starts the
same server.

> [!IMPORTANT]
> The default configuration is a personal, local app. Sessions live in a single Python process,
> expire after an hour of inactivity, and are capped at eight. **Run one worker.** A restart clears
> footage, analyses, and conversations — download any report you want to keep. Public or
> multi-worker hosting would need authentication and a shared session store.

## Using the studio

1. **Upload** one JPG/PNG image, or an MP4, MOV, AVI, MKV, or M4V video — up to **100 MB** and **30 seconds**.
2. **Pick a focus:** Overall form, Stroke, Start, Turn, Underwater, Kick, or Finish.
3. **Analyze technique.** Read through **Key priorities**, **Your drills**, and **Details**.
4. **Ask follow-ups** in the coach panel — answers are grounded in the analysis and the recent conversation.
5. **Download your session report** when you're done.

On wide screens the three areas sit side by side as full-height columns and scroll independently;
narrower windows fold the coach into a full-width panel below, then into a single column on mobile.

### Settings

| Setting | What it controls |
|---|---|
| Model | `gpt-5.6-luna`, `gpt-4o`, or `gpt-4o-mini` |
| Image detail | Resolution sent to the model: `auto`, `low`, or `high` |
| Chat creativity | Temperature for follow-up answers |
| Video frames | How many frames to extract — more detail, more usage |
| Smart frame selection | Pick representative moments instead of evenly spaced ones |
| Pose estimation | Optional beta measurement hints |
| Recheck footage in chat | Send frames along with follow-up questions |

Frame settings apply to your **next** upload — replace or re-upload a video to use different ones.
Video playback depends on your browser's codec support; when a clip won't play, the extracted
frames are still there and still analyzable.

> [!NOTE]
> Pose estimation is a hint layer, not a verdict. It uses `pose_landmarker_heavy.task` when
> available, with the existing MediaPipe fallback, and normal visual analysis continues without it.

## Verification

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
npm run build
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -c "import app; print('import ok')"
```

The suite exercises real image and video processing and the full HTTP upload → analysis → chat →
report workflow, plus profile validation, session isolation/expiry/reset, failed requests, media
rechecks, and the pose fallback. AI responses are mocked, so it makes **no paid API calls**.

<details>
<summary><b>If OpenCV can't read video files</b></summary>

The installed OpenCV wheel must include video codecs. An older macOS Python that reports macOS
10.16 may install a locally built wheel without FFmpeg. Install the official binary instead:

```bash
SYSTEM_VERSION_COMPAT=0 .venv/bin/python -m pip install \
  --only-binary=:all: --no-cache-dir --force-reinstall "opencv-python>=4.10,<4.12"
```

This workspace is already configured with a working wheel.

</details>

## Project structure

<details>
<summary><b>Full tree</b></summary>

```text
app.py                         FastAPI entrypoint; production frontend serving
frontend/
  index.html                   HTML metadata
  public/favicon.svg           Swimform icon
  src/
    App.tsx                    Studio workflow and application state
    styles.css                 Responsive layout, tokens, and interaction states
    api.ts                     Same-origin API and report-download helpers
    types.ts                   Shared frontend contracts
    components/
      Results.tsx              Coaching cards, analysis tabs, and follow-up chat
      ui.tsx                   Accessible Radix dialogs and form controls
scripts/dev.mjs                Starts/stops the frontend and backend together
swim_analyzer/
  api.py                       HTTP validation, uploads, sessions, and routes
  service.py                   Analysis/chat orchestration and bounded session store
  constants.py                 Shared limits, models, categories
  media.py                     Image prep, upload validation, video frames
  openai_client.py             OpenAI Responses API helpers
  pose.py                      Optional pose metrics and annotations
  prompts.py                   Coaching prompts and Markdown rendering
  schemas.py                   Swimmer profile and structured analysis schema
  report.py                    Markdown report builder
  knowledge.py                 Coaching knowledge loader
swim_knowledge.md              Coaching cues and drills
pose_landmarker_heavy.task     Optional local pose model
requirements.txt               Python runtime dependencies
requirements-dev.txt           Adds the API test client
package.json                   Frontend dependencies and commands
vite.config.ts                 Frontend build and development proxy
```

</details>

### API

All routes are served under `/api` on the same origin, with HttpOnly cookie sessions.

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/config` | Limits, models, accepted extensions, whether a server key is set |
| `GET` | `/session` | Current session state |
| `DELETE` | `/session` | Start over |
| `PUT` | `/profile` | Update swimmer context |
| `POST` | `/upload` | Upload footage and extract frames |
| `POST` | `/analyze` | Run the technique analysis |
| `POST` | `/chat` | Ask a follow-up question |
| `GET` | `/report` | Download the Markdown report |
| `GET` | `/health` | Liveness check |

---

See [`AGENTS.md`](AGENTS.md) for project conventions. Keep `.env`, `.venv`, `node_modules`,
`dist`, bytecode, and generated reports out of source control.
