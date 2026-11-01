"""Multimodal analysis via Meta Muse Spark Open on Fireworks AI."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from openai import APIError, OpenAI

from diagnosis import Diagnosis, diagnosis_from_model_dict, uncertain_diagnosis
from vision import SampledFrame, encode_frame_jpeg_base64

FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"
DEFAULT_MODEL = "accounts/fireworks/models/muse-spark-open"
REASONING_EFFORTS = ("low", "medium", "high", "xhigh")

SYSTEM_PROMPT = """You are DemoDoctor, an assistant that inspects robot demonstration frames.
You assess whether a described manipulation task appears completed, failed, or cannot be judged.
Rules:
- Base claims on what is visible in the provided frames.
- Separate directly observed events from assumptions.
- Prefer verdict "uncertain" when frames are insufficient, occluded, or ambiguous.
- Do NOT invent object tracks, masks, or measurements you cannot see.
- Your verdict is provisional analysis, not ground truth.
- Respond with a single JSON object only (no markdown fences), using this schema:
{
  "verdict": "success" | "failure" | "uncertain",
  "summary": "short explanation",
  "observed_actions": ["..."],
  "failure_mode": "string or null",
  "evidence": [
    {"timestamp_s": 0.0, "description": "...", "kind": "observed" | "assumed", "frame_index": 0}
  ],
  "assumptions": ["..."],
  "uncertainty_notes": ["..."],
  "confidence": 0.0
}
confidence is between 0 and 1. It is a rough self-estimate only — NOT empirical accuracy.
Do not default to high values like 0.9+ unless nearly every required step is directly visible
with little occlusion and few assumptions. If grasp/transport is inferred between frames,
or the outcome is only suggested by the final frame, keep confidence at most 0.7.
Use 0.5 or lower when uncertain or when evidence is thin.
"""


class FireworksConfigError(RuntimeError):
    """Raised when the Fireworks API key is missing."""


def load_fireworks_api_key() -> str:
    """Load FIREWORKS_API_KEY from environment / .env. Never log the key."""
    load_dotenv()
    key = (os.getenv("FIREWORKS_API_KEY") or "").strip()
    if not key:
        raise FireworksConfigError(
            "FIREWORKS_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return key


def get_client(api_key: str | None = None) -> OpenAI:
    key = api_key if api_key is not None else load_fireworks_api_key()
    return OpenAI(api_key=key, base_url=FIREWORKS_BASE_URL, max_retries=0, timeout=120.0)


def analyze_demonstration(
    frames: list[SampledFrame],
    task_description: str,
    *,
    model: str = DEFAULT_MODEL,
    reasoning_effort: str = "low",
    max_tokens: int = 2048,
    jpeg_quality: int = 75,
    api_key: str | None = None,
) -> Diagnosis:
    """Send timestamped frames + task text to Muse Spark Open; return structured Diagnosis."""
    if not frames:
        return uncertain_diagnosis(task_description, "No frames available to analyze.")

    effort = reasoning_effort if reasoning_effort in REASONING_EFFORTS else "low"
    client = get_client(api_key)

    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                f"Task description: {task_description.strip() or '(none provided)'}\n"
                f"You are given {len(frames)} frames sampled from a robot demonstration video. "
                "Each image is labeled with its approximate timestamp and frame_index. "
                "Judge task completion from these frames alone."
            ),
        }
    ]

    for index, frame in enumerate(frames):
        content.append(
            {
                "type": "text",
                "text": f"frame_index={index}, timestamp_s={frame.timestamp_s}",
            }
        )
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": encode_frame_jpeg_base64(frame.rgb, quality=jpeg_quality)},
            }
        )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            max_tokens=max_tokens,
            temperature=0.2,
            extra_body={"reasoning_effort": effort},
        )
    except APIError as error:
        return uncertain_diagnosis(
            task_description,
            f"Fireworks API error: {error.message or type(error).__name__}",
            model_name=model,
        )
    except Exception as error:  # network / client failures
        return uncertain_diagnosis(
            task_description,
            f"Unable to reach Fireworks: {type(error).__name__}: {error}",
            model_name=model,
        )

    message = response.choices[0].message if response.choices else None
    raw_text = (message.content or "").strip() if message else ""
    usage = _usage_dict(response)

    if not raw_text:
        return uncertain_diagnosis(
            task_description,
            "Model returned an empty response.",
            model_name=model,
            usage=usage,
        )

    parsed = extract_json_object(raw_text)
    if parsed is None:
        return uncertain_diagnosis(
            task_description,
            "Model reply was not valid JSON; treating result as uncertain.",
            model_name=model,
            raw_model_text=raw_text,
            usage=usage,
        )

    return diagnosis_from_model_dict(
        parsed,
        task_description=task_description,
        model_name=model,
        raw_model_text=raw_text,
        usage=usage,
        tracking_used=False,
    )


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Parse a JSON object from model text, tolerating optional markdown fences."""
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    else:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start : end + 1]
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _usage_dict(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def estimate_cost_usd(
    usage: dict[str, Any],
    *,
    input_per_m: float = 1.25,
    output_per_m: float = 4.25,
) -> float | None:
    """Rough USD estimate from published serverless rates (subject to change)."""
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    if prompt is None or completion is None:
        return None
    return (prompt / 1_000_000) * input_per_m + (completion / 1_000_000) * output_per_m


def analyze_with_evidence(
    package: Any,
    frames: list[SampledFrame],
    *,
    model: str = DEFAULT_MODEL,
    reasoning_effort: str = "low",
    max_tokens: int = 2048,
    jpeg_quality: int = 75,
    api_key: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Evidence-grounded Muse call. Does not replace analyze_demonstration (Muse-only baseline).

    Returns a dict with keys: dry_run | validated | raw_text | usage | package_id.
    When dry_run=True, no Fireworks request is made.
    Unsupported evidence references are flagged via validated.validation_errors (ok=False).
    """
    import json as _json

    from evidence_fusion import (
        MUSE_EVIDENCE_SYSTEM_PROMPT,
        ValidatedMuseExplanation,
        dry_run_muse_payload,
        validate_muse_explanation,
    )

    payload_preview = dry_run_muse_payload(package, frames)
    if package.provenance.get("strict_grounding") and (
            model != DEFAULT_MODEL or not 0 < max_tokens <= 2048 or len(frames) > 6):
        raise ValueError("Live evidence inference requires the bounded Muse model, <=6 frames and <=2048 output tokens")
    if dry_run:
        return {
            "dry_run": True,
            "paid_call": False,
            "payload": payload_preview,
            "validated": None,
            "raw_text": None,
            "usage": {},
        }

    effort = reasoning_effort if reasoning_effort in REASONING_EFFORTS else "low"
    client = get_client(api_key)
    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "EVIDENCE PACKAGE (authoritative for verified claims):\n"
                + _json.dumps(package.to_muse_text_dict(), indent=2)
                + "\n\nFrames follow in package order (F0, F1, …). "
                "Use them only as visual context for cited evidence; do not invent pipeline events."
            ),
        }
    ]
    for ref, frame in zip(package.frame_refs, frames):
        content.append({
            "type": "text",
            "text": (
                f"{ref.frame_ref}: frame_index={ref.frame_index} timestamp_s={ref.timestamp_s} "
                f"role={ref.role} tied_evidence_ids={ref.tied_evidence_ids}"
            ),
        })
        content.append({
            "type": "image_url",
            "image_url": {"url": encode_frame_jpeg_base64(frame.rgb, quality=jpeg_quality)},
        })

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": MUSE_EVIDENCE_SYSTEM_PROMPT + (
                    "\nSTRICT LIVE CONTRACT: task_outcome must be uncertain or agree with the "
                    "deterministic verdict; partial windows must remain uncertain. Each factual "
                    "claim must copy exactly one evidence_catalog summary verbatim and cite only "
                    "that entry's ID. Put additional reasoning in hypotheses or explicitly "
                    "unverified visual_interpretations. Context frames are not physical measurements."
                    if package.provenance.get("strict_grounding") else "")},
                {"role": "user", "content": content},
            ],
            max_tokens=max_tokens,
            temperature=0.2,
            extra_body={"reasoning_effort": effort},
        )
    except APIError as error:
        empty = ValidatedMuseExplanation(
            ok=False, explanation="", task_outcome="uncertain", earliest_failure_interval=None,
            factual_claims=[], hypotheses=[], visual_interpretations=[], limitations=[],
            outcome_evidence_ids=[], validation_errors=[f"Fireworks API error: {error.message}"],
            validation_warnings=[],
        )
        return {"dry_run": False, "paid_call": True, "validated": empty.to_dict(), "raw_text": None, "usage": {}}
    except Exception as error:
        empty = ValidatedMuseExplanation(
            ok=False, explanation="", task_outcome="uncertain", earliest_failure_interval=None,
            factual_claims=[], hypotheses=[], visual_interpretations=[], limitations=[],
            outcome_evidence_ids=[],
            validation_errors=[f"Unable to reach Fireworks: {type(error).__name__}: {error}"],
            validation_warnings=[],
        )
        return {"dry_run": False, "paid_call": True, "validated": empty.to_dict(), "raw_text": None, "usage": {}}

    message = response.choices[0].message if response.choices else None
    raw_text = (message.content or "").strip() if message else ""
    usage = _usage_dict(response)
    parsed = extract_json_object(raw_text) if raw_text else None
    if parsed is None:
        empty = ValidatedMuseExplanation(
            ok=False, explanation="", task_outcome="uncertain", earliest_failure_interval=None,
            factual_claims=[], hypotheses=[], visual_interpretations=[], limitations=[],
            outcome_evidence_ids=[],
            validation_errors=["Model reply was not valid JSON"],
            validation_warnings=[],
            raw={},
        )
        return {
            "dry_run": False, "paid_call": True, "validated": empty.to_dict(),
            "raw_text": raw_text, "usage": usage, "model": model, "reasoning_effort": effort,
        }

    validated = validate_muse_explanation(parsed, package)
    return {
        "dry_run": False,
        "paid_call": True,
        "validated": validated.to_dict(),
        "raw_text": raw_text,
        "usage": usage,
        "model": model,
        "reasoning_effort": effort,
        "payload_summary": {
            "n_evidence_items": payload_preview["n_evidence_items"],
            "n_frames": payload_preview["n_frames"],
            "user_text_chars": payload_preview["user_text_chars"],
        },
    }
