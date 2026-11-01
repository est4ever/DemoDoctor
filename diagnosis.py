"""Structured diagnosis schema and helpers for DemoDoctor verdicts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


Verdict = Literal["success", "failure", "uncertain"]
EvidenceKind = Literal["observed", "assumed"]


@dataclass
class EvidenceItem:
    """One piece of evidence cited by the model or rule engine."""

    timestamp_s: float | None
    description: str
    kind: EvidenceKind = "observed"
    frame_index: int | None = None


@dataclass
class Diagnosis:
    """Structured task assessment. Not ground truth unless labeled separately."""

    verdict: Verdict
    task_description: str
    summary: str
    observed_actions: list[str] = field(default_factory=list)
    failure_mode: str | None = None
    evidence: list[EvidenceItem] = field(default_factory=list)
    uncertainty_notes: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    confidence: float | None = None
    model_name: str | None = None
    tracking_used: bool = False
    provisional: bool = True
    raw_model_text: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload


def normalize_verdict(value: str | None) -> Verdict:
    if not value:
        return "uncertain"
    cleaned = value.strip().lower()
    if cleaned in {"success", "failure", "uncertain"}:
        return cleaned  # type: ignore[return-value]
    if cleaned in {"pass", "passed", "ok", "completed"}:
        return "success"
    if cleaned in {"fail", "failed", "error"}:
        return "failure"
    return "uncertain"


def diagnosis_from_model_dict(
    data: dict[str, Any],
    *,
    task_description: str,
    model_name: str,
    raw_model_text: str | None = None,
    usage: dict[str, Any] | None = None,
    tracking_used: bool = False,
) -> Diagnosis:
    """Build a Diagnosis from parsed model JSON (best-effort, safe defaults)."""
    evidence_raw = data.get("evidence") or []
    evidence: list[EvidenceItem] = []
    if isinstance(evidence_raw, list):
        for item in evidence_raw:
            if not isinstance(item, dict):
                continue
            kind = item.get("kind", "observed")
            if kind not in ("observed", "assumed"):
                kind = "assumed"
            evidence.append(
                EvidenceItem(
                    timestamp_s=_as_optional_float(item.get("timestamp_s")),
                    description=str(item.get("description") or "").strip() or "Unspecified",
                    kind=kind,  # type: ignore[arg-type]
                    frame_index=_as_optional_int(item.get("frame_index")),
                )
            )

    observed = data.get("observed_actions") or []
    if not isinstance(observed, list):
        observed = [str(observed)]
    assumptions = data.get("assumptions") or []
    if not isinstance(assumptions, list):
        assumptions = [str(assumptions)]
    uncertainty = data.get("uncertainty_notes") or data.get("uncertainty") or []
    if isinstance(uncertainty, str):
        uncertainty = [uncertainty]
    if not isinstance(uncertainty, list):
        uncertainty = []

    failure_mode = data.get("failure_mode")
    if failure_mode is not None:
        failure_mode = str(failure_mode).strip() or None

    confidence = _as_optional_float(data.get("confidence"))
    if confidence is not None:
        confidence = max(0.0, min(1.0, confidence))

    return Diagnosis(
        verdict=normalize_verdict(str(data.get("verdict", "uncertain"))),
        task_description=task_description,
        summary=str(data.get("summary") or data.get("explanation") or "").strip()
        or "No summary returned by the model.",
        observed_actions=[str(x).strip() for x in observed if str(x).strip()],
        failure_mode=failure_mode,
        evidence=evidence,
        uncertainty_notes=[str(x).strip() for x in uncertainty if str(x).strip()],
        assumptions=[str(x).strip() for x in assumptions if str(x).strip()],
        confidence=confidence,
        model_name=model_name,
        tracking_used=tracking_used,
        provisional=True,
        raw_model_text=raw_model_text,
        usage=usage or {},
    )


def uncertain_diagnosis(
    task_description: str,
    reason: str,
    *,
    model_name: str | None = None,
    raw_model_text: str | None = None,
    usage: dict[str, Any] | None = None,
) -> Diagnosis:
    return Diagnosis(
        verdict="uncertain",
        task_description=task_description,
        summary=reason,
        uncertainty_notes=[reason],
        model_name=model_name,
        provisional=True,
        raw_model_text=raw_model_text,
        usage=usage or {},
    )


def merge_tracking_context(diagnosis: Diagnosis, tracking_available: bool) -> Diagnosis:
    """Annotate whether object tracks informed the diagnosis (future SAM path)."""
    diagnosis.tracking_used = tracking_available
    if not tracking_available:
        note = "Object tracks unavailable; verdict is multimodal-frame reasoning only."
        if note not in diagnosis.uncertainty_notes:
            diagnosis.uncertainty_notes.append(note)
    return diagnosis


def _as_optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
