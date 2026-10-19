"""LLM helpers: structure a transcript into clinical JSON, and write SOAP/patient notes."""

import json
import os

from dotenv import load_dotenv
from anthropic import Anthropic

from .prompts import STRUCTURE_PROMPT, WRITE_PROMPT

load_dotenv()

STRUCTURE_SCHEMA = {
    "chief_complaint": "Not reported",
    "history_of_present_illness": "Not reported",
    "past_medical_history": "Not reported",
    "medications": [],
    "allergies": [],
    "vital_signs": "Not reported",
    "physical_exam": "Not reported",
    "key_symptoms": [],
    "clinical_question": "",
}

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            # Hard timeout so a slow call can never hang the request forever.
            _client = Anthropic(api_key=api_key, timeout=60, max_retries=1)
        else:
            _client = False  # sentinel: no key configured
    return _client


# Haiku 5.5: ~3 s to structure, ~14 s to write both notes (measured).
_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5")


def _ask(prompt: str, max_tokens: int) -> str:
    """Call Claude with thinking off and return only the text blocks."""
    resp = _get_client().messages.create(
        model=_MODEL,
        max_tokens=max_tokens,
        thinking={"type": "disabled"},
        messages=[{"role": "user", "content": prompt}],
    )
    if resp.stop_reason == "max_tokens":
        print(f"[llm] WARNING: response truncated at {max_tokens} tokens")
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


def _default_structure():
    return dict(STRUCTURE_SCHEMA)


def structure(transcript: str) -> dict:
    """Structure a consultation transcript into the clinical JSON schema.

    Degrades gracefully (returns all "Not reported" / empty) if Claude is
    unavailable or misconfigured so the pipeline never breaks.
    """
    client = _get_client()
    if not client:
        return _default_structure()

    try:
        data = _parse_json(_ask(STRUCTURE_PROMPT.format(transcript=transcript), 2000))
        # Ensure every expected key exists with sane defaults.
        result = _default_structure()
        for key in result:
            if key in data and data[key] not in (None, ""):
                result[key] = data[key]
        return result
    except Exception as exc:  # pragma: no cover - defensive, flow must not break
        print(f"[llm] structure failed: {exc}")
        return _default_structure()


def _parse_json(text: str) -> dict:
    text = text.strip()
    # Strip markdown code fences if present.
    if text.startswith("```"):
        text = text.split("```", 2)
        text = text[1] if len(text) > 1 else text[-1]
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to salvage by extracting the first {...} block.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return {}
        return {}


def write_notes(structured: dict, research: dict) -> tuple:
    """Write the doctor SOAP note (HTML) and patient summary (HTML).

    Returns (doctor_html, patient_html). Degrades gracefully on failure.
    """
    client = _get_client()
    if not client:
        return _fallback_notes(structured, research)

    try:
        prompt = WRITE_PROMPT.format(
            structured=json.dumps(structured, indent=2),
            research=json.dumps(research, indent=2),
        )
        data = {}
        for attempt in range(2):  # one retry if the model replies with prose instead of JSON
            data = _parse_json(_ask(prompt, 8000))
            if data.get("doctor_html") and data.get("patient_html"):
                break
            print(f"[llm] write_notes attempt {attempt + 1} returned no valid JSON")
        doctor_html = data.get("doctor_html") or ""
        patient_html = data.get("patient_html") or ""
        if not doctor_html or not patient_html:
            return _fallback_notes(structured, research)
        return doctor_html, patient_html
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[llm] write_notes failed: {exc}")
        return _fallback_notes(structured, research)


def _fallback_notes(structured: dict, research: dict) -> tuple:
    cc = structured.get("chief_complaint", "Not reported")
    doctor_html = (
        "<h2>SOAP Note (AI-generated, requires review)</h2>"
        "<p><strong>Disclaimer:</strong> AI-generated suggestion. "
        "Requires review by the treating physician.</p>"
        f"<p><strong>Chief complaint:</strong> {cc}</p>"
        "<p>Structured data and research were not available to generate a full note.</p>"
    )
    patient_html = (
        "<h2>Your Visit Summary</h2>"
        f"<p><strong>Reason for visit:</strong> {cc}</p>"
        "<p>Please review this note with your doctor. "
        "If you have urgent warning signs, go to the ER.</p>"
    )
    return doctor_html, patient_html