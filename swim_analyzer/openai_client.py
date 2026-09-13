from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from openai import OpenAI

from .schemas import INITIAL_ANALYSIS_JSON_SCHEMA, InitialSwimAnalysis

logger = logging.getLogger(__name__)


def get_output_text(response) -> str:
    parts: List[str] = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) == "message":
            for content in getattr(item, "content", []) or []:
                refusal = getattr(content, "refusal", None)
                if refusal:
                    raise ValueError(f"The model refused the request: {refusal}")
                if getattr(content, "type", None) == "output_text":
                    text = getattr(content, "text", "")
                    if text:
                        parts.append(text)
    if parts:
        return "\n".join(parts).strip()
    fallback_text = getattr(response, "output_text", None)
    if isinstance(fallback_text, str) and fallback_text.strip():
        return fallback_text.strip()
    return ""


def request_kwargs(model: str, temperature: Optional[float]) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {"model": model, "truncation": "auto"}
    if temperature is not None:
        kwargs["temperature"] = temperature
    return kwargs


def responses_create_with_temperature_fallback(client: OpenAI, **kwargs):
    try:
        return client.responses.create(**kwargs)
    except Exception as exc:
        message = str(exc).lower()
        if "temperature" in message and "temperature" in kwargs:
            kwargs = dict(kwargs)
            kwargs.pop("temperature", None)
            return client.responses.create(**kwargs)
        raise


def chat_with_context(client: OpenAI, messages: List[dict], model: str, system_message: dict, temperature: float = 0.7) -> str:
    response = responses_create_with_temperature_fallback(
        client,
        input=[system_message, *messages],
        **request_kwargs(model=model, temperature=temperature),
    )
    text = get_output_text(response)
    if not text:
        raise ValueError("The model returned no readable text output.")
    return text


def initial_analysis_with_structured_outputs(
    client: OpenAI,
    messages: List[dict],
    model: str,
    system_message: dict,
    temperature: float = 0.2,
) -> Dict[str, Any]:
    kwargs = request_kwargs(model=model, temperature=temperature)
    if InitialSwimAnalysis is not None and hasattr(client.responses, "parse"):
        try:
            response = client.responses.parse(input=[system_message, *messages], text_format=InitialSwimAnalysis, **kwargs)
            parsed = getattr(response, "output_parsed", None)
            if parsed is not None:
                return parsed.model_dump() if hasattr(parsed, "model_dump") else parsed.dict()
        except Exception as exc:
            logger.warning("Structured parse failed; falling back to manual schema. Error: %s", exc)
    try:
        response = responses_create_with_temperature_fallback(
            client,
            input=[system_message, *messages],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "initial_swim_analysis",
                    "strict": True,
                    "schema": INITIAL_ANALYSIS_JSON_SCHEMA,
                }
            },
            **kwargs,
        )
        return parse_initial_analysis_json(get_output_text(response))
    except Exception as exc:
        logger.warning("Manual structured output failed; falling back to prompt-only JSON. Error: %s", exc)
    fallback_prompt = dict(messages[-1])
    fallback_content = list(fallback_prompt.get("content", []))
    fallback_content.append({"type": "input_text", "text": "Return JSON only that conforms to this schema: " + json.dumps(INITIAL_ANALYSIS_JSON_SCHEMA)})
    fallback_prompt["content"] = fallback_content
    raw_response = chat_with_context(client=client, messages=[*messages[:-1], fallback_prompt], model=model, system_message=system_message, temperature=temperature)
    return parse_initial_analysis_json(raw_response)


def extract_json_from_text(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def parse_initial_analysis_json(text: str) -> Dict[str, Any]:
    data = extract_json_from_text(text)
    if not isinstance(data, dict):
        raise ValueError("Initial analysis JSON is not an object.")
    if "analysis_category" not in data:
        data["analysis_category"] = "general"
    if "pose_metrics" not in data:
        data["pose_metrics"] = None
    if "stroke_id" not in data or "top_3_priorities" not in data:
        raise ValueError("Initial analysis JSON is missing required keys.")
    if not isinstance(data.get("top_3_priorities"), list):
        raise ValueError("top_3_priorities must be a list.")
    return data
