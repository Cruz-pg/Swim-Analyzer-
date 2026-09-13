"""FastAPI entrypoint. In production, serves the built React app as well."""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

from swim_analyzer.api import router
from swim_analyzer.constants import MAX_UPLOAD_MB

app = FastAPI(title="Swimform API", version="2.0.0")


@app.middleware("http")
async def local_request_guard(request: Request, call_next):
    if request.url.path.startswith("/api"):
        if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cross-site requests are not allowed."}, status_code=403)
        length = request.headers.get("content-length")
        if length:
            try:
                if int(length) > (MAX_UPLOAD_MB + 1) * 1024 * 1024:
                    return JSONResponse({"detail": f"Choose a file under {MAX_UPLOAD_MB} MB."}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "Invalid request size."}, status_code=400)
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


app.include_router(router)

if (ROOT / "dist" / "index.html").is_file():
    app.mount("/", StaticFiles(directory=ROOT / "dist", html=True), name="frontend")
else:
    @app.get("/")
    def frontend_setup():
        return JSONResponse({"message": "Run npm run dev for development, or npm run build then restart the server."})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
