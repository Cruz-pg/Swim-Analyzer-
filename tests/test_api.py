"""Migration regressions: real HTTP/media processing, mocked AI responses."""
from __future__ import annotations

import copy
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from app import app
from swim_analyzer import api, service
from swim_analyzer.constants import DEFAULT_MODELS


ANALYSIS = {
    "analysis_category": "general",
    "stroke_id": {"label": "freestyle", "confidence_pct": 88},
    "visibility": {"can_see": ["Recovery and head position"], "cannot_see": ["Underwater catch"]},
    "pose_metrics": None,
    "top_3_priorities": [{"rank": 1, "problem": "Head lifts while breathing", "likely_cause": "Looking forward during the breath", "cue": "Keep one goggle in the water"}],
    "drills": [{"name": "Side-kick drill", "how": "Swim 4 x 25 m on your side", "why": "Practice a balanced breathing position"}],
    "what_to_film_next": [{"angle": "Underwater side view", "distance": "A few complete stroke cycles"}],
}


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (120, 80), (34, 112, 151)).save(buffer, format="PNG")
    return buffer.getvalue()


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        api.store = service.SessionStore()
        self.client = TestClient(app)
        self.client.get("/api/session")
        self.env = patch.dict(os.environ, {"OPENAI_API_KEY": ""})
        self.env.start()

    def tearDown(self):
        self.client.close()
        self.env.stop()

    def upload_image(self):
        response = self.client.post("/api/upload", files={"file": ("swimming.png", png_bytes(), "image/png")})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def analyze(self):
        with patch("swim_analyzer.service.client_for", return_value=MagicMock()), patch(
            "swim_analyzer.service.initial_analysis_with_structured_outputs", return_value=copy.deepcopy(ANALYSIS),
        ) as request:
            response = self.client.post("/api/analyze", json={"category": "strokes", "profile": {"goal": "Cleaner breathing"}})
            self.assertEqual(response.status_code, 200, response.text)
            content = request.call_args.kwargs["messages"][0]["content"]
            self.assertIn("Cleaner breathing", content[0]["text"])
            self.assertEqual(content[1]["type"], "input_image")
            return response.json()

    def test_upload_analysis_followup_and_report(self):
        upload = self.upload_image()
        self.assertEqual(upload["media"]["frame_count"], 1)
        self.assertTrue(upload["media"]["frames"][0].startswith("data:image/jpeg;base64,"))
        result = self.analyze()
        self.assertEqual(result["analysis"]["analysis_category"], "strokes")
        self.assertIn("one goggle", result["profile"]["coach_notes"])
        with patch("swim_analyzer.service.client_for", return_value=MagicMock()), patch(
            "swim_analyzer.service.chat_with_context", return_value="Try 4 x 25 m with one goggle in the water.",
        ) as chat:
            response = self.client.post("/api/chat", json={"message": "What drill should I do?"})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(len(response.json()["chat_messages"]), 2)
            self.assertIn("Head lifts", chat.call_args.kwargs["messages"][-1]["content"][0]["text"])
        report = self.client.get("/api/report")
        self.assertEqual(report.status_code, 200)
        self.assertIn('attachment; filename="swim_analysis_report.md"', report.headers["content-disposition"])
        self.assertIn("Head lifts while breathing", report.text)
        self.assertIn("What drill should I do?", report.text)
        self.assertEqual(report.text.count("## Initial Analysis"), 1)
        self.assertEqual(self.client.get("/api/session").json()["analysis"], result["analysis"])

    def test_video_upload_extracts_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "clip.mp4")
            writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (120, 80))
            self.assertTrue(writer.isOpened())
            for frame in range(20):
                writer.write(np.full((80, 120, 3), (frame * 10, 120, 90), dtype=np.uint8))
            writer.release()
            response = self.client.post("/api/upload", data={"max_frames": "5", "smart": "true"}, files={"file": ("clip.mp4", Path(path).read_bytes(), "video/mp4")})
        self.assertEqual(response.status_code, 200, response.text)
        media = response.json()["media"]
        self.assertEqual(media["type"], "video")
        self.assertEqual(media["frame_count"], 5)
        self.assertAlmostEqual(media["duration"], 2)

    def test_replacement_clears_old_analysis_and_chat(self):
        self.upload_image(); self.analyze()
        current = self.upload_image()
        self.assertIsNone(current["analysis"])
        self.assertEqual(current["chat_messages"], [])
        self.assertEqual(current["profile"]["coach_notes"], "")

    def test_failed_analysis_preserves_previous_result_and_hides_error_details(self):
        self.upload_image(); original = self.analyze()
        with patch("swim_analyzer.service.client_for", return_value=MagicMock()), patch("swim_analyzer.service.initial_analysis_with_structured_outputs", side_effect=RuntimeError("secret-api-key")):
            response = self.client.post("/api/analyze", json={})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("secret-api-key", response.text)
        self.assertEqual(self.client.get("/api/session").json()["analysis"], original["analysis"])

    def test_failed_chat_does_not_leave_dangling_user_message(self):
        self.upload_image(); self.analyze()
        with patch("swim_analyzer.service.client_for", return_value=MagicMock()), patch("swim_analyzer.service.chat_with_context", side_effect=RuntimeError("offline")):
            response = self.client.post("/api/chat", json={"message": "Help with breathing"})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(self.client.get("/api/session").json()["chat_messages"], [])

    def test_followup_media_is_opt_in_and_history_is_reused(self):
        self.upload_image(); self.analyze()
        with patch("swim_analyzer.service.client_for", return_value=MagicMock()), patch("swim_analyzer.service.chat_with_context", return_value="Keep your head aligned.") as chat:
            self.client.post("/api/chat", json={"message": "First question"})
            first = chat.call_args.kwargs["messages"][-1]["content"]
            self.assertEqual(len(first), 1)
            self.client.post("/api/chat", json={"message": "Check the video again", "options": {"include_media_on_followup": True}})
            second = chat.call_args.kwargs["messages"]
            self.assertEqual(second[0]["content"][0]["text"], "First question")
            self.assertEqual(second[-1]["content"][1]["type"], "input_image")

    def test_session_isolation_expiration_and_reset(self):
        self.upload_image(); self.analyze()
        with TestClient(app) as another:
            response = another.get("/api/session")
            self.assertIsNone(response.json()["media"])
            self.assertIn("HttpOnly", response.headers["set-cookie"])
            self.assertEqual(another.get("/api/report").status_code, 400)
        cleared = self.client.delete("/api/session").json()
        self.assertIsNone(cleared["media"])
        self.assertIsNone(cleared["analysis"])
        self.assertEqual(cleared["profile"]["goal"], "Cleaner breathing")
        api.store = service.SessionStore()
        self.assertEqual(self.client.post("/api/chat", json={"message": "Hello"}).status_code, 409)

    def test_upload_validation_preserves_existing_media(self):
        original = self.upload_image()
        for name, payload in [("clip.txt", b"wrong"), ("empty.png", b""), ("broken.jpg", b"not a jpeg")]:
            with self.subTest(name=name):
                response = self.client.post("/api/upload", files={"file": (name, payload)})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.client.get("/api/session").json()["media"], original["media"])
        with patch("swim_analyzer.api.MAX_UPLOAD_MB", 0):
            response = self.client.post("/api/upload", files={"file": ("large.png", png_bytes())})
            # The shared size validation handles the actual configured limit.
            self.assertEqual(response.status_code, 400)
        response = self.client.post("/api/upload", data={"max_frames": "1000"}, files={"file": ("image.png", png_bytes())})
        self.assertEqual(response.status_code, 422)

    def test_profile_and_ai_prerequisites(self):
        self.assertEqual(self.client.post("/api/analyze", json={}).status_code, 400)
        self.assertEqual(self.client.post("/api/chat", json={"message": "Hello"}).status_code, 400)
        self.upload_image()
        response = self.client.post("/api/analyze", json={})
        self.assertEqual(response.status_code, 400)
        self.assertIn("API key", response.text)
        self.assertEqual(self.client.post("/api/analyze", json={"category": "unsupported"}).status_code, 422)
        self.assertEqual(self.client.put("/api/profile", json={"goal": "x" * 1001}).status_code, 422)
        profile = self.client.put("/api/profile", json={"goal": "Clean turn", "known_issues": ["Turn"]})
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(self.client.get("/api/session").json()["profile"]["goal"], "Clean turn")

    def test_config_does_not_expose_key_and_cross_site_writes_fail(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "secret-api-key"}):
            response = self.client.get("/api/config")
        self.assertTrue(response.json()["api_key_configured"])
        self.assertEqual(response.json()["models"], ["gpt-5.6-luna", "gpt-4o", "gpt-4o-mini"])
        self.assertNotIn("secret-api-key", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(self.client.delete("/api/session", headers={"sec-fetch-site": "cross-site"}).status_code, 403)
        self.assertEqual(self.client.post("/api/upload", headers={"content-length": str(102 * 1024 * 1024)}).status_code, 413)

    def test_only_configured_models_are_accepted(self):
        for model in DEFAULT_MODELS:
            with self.subTest(model=model):
                self.assertEqual(api.AnalysisOptions(model=model).model, model)
        response = self.client.post("/api/analyze", json={"options": {"model": "gpt-5.5"}})
        self.assertEqual(response.status_code, 422)
        self.assertIn("available AI models", response.text)

    def test_concurrent_operation_is_rejected(self):
        session = api.store.get(self.client.cookies.get(api.COOKIE))
        with session.lock:
            self.assertEqual(self.client.delete("/api/session").status_code, 409)

    def test_pose_hints_remain_optional(self):
        self.upload_image()
        from swim_analyzer.pose import PoseResult
        with patch("swim_analyzer.service.client_for", return_value=MagicMock()), patch("swim_analyzer.service.initial_analysis_with_structured_outputs", return_value=copy.deepcopy(ANALYSIS)), patch("swim_analyzer.service.analyze_pose", return_value=PoseResult([], [], "Pose unavailable; visual analysis still works.")):
            response = self.client.post("/api/analyze", json={"options": {"pose_enabled": True}})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Pose unavailable", response.json()["pose_warning"])
        self.assertIsNotNone(response.json()["analysis"])


class SessionStoreTests(unittest.TestCase):
    def test_capacity_and_expiration(self):
        sessions = service.SessionStore(capacity=1, ttl=60)
        old, first = sessions.create()
        new, second = sessions.create()
        self.assertIsNone(sessions.get(old))
        self.assertIs(sessions.get(new), second)
        second.last_used -= 61
        self.assertIsNone(sessions.get(new))


if __name__ == "__main__":
    unittest.main()
