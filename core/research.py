"""Web research for differential diagnosis using the Parallel Task API."""

import json
import os
import time

from dotenv import load_dotenv
from parallel import Parallel

load_dotenv()

RESEARCH_SCHEMA = {
    "type": "json",
    "json_schema": {
        "type": "object",
        "properties": {
            "differential_diagnosis": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "diagnosis": {"type": "string"},
                        "likelihood": {"type": "string", "enum": ["high", "medium", "low"]},
                        "rationale": {"type": "string"},
                    },
                    "required": ["diagnosis", "likelihood", "rationale"],
                },
            },
            "suggested_tests": {"type": "array", "items": {"type": "string"}},
            "suggested_management": {"type": "array", "items": {"type": "string"}},
            "red_flags": {"type": "array", "items": {"type": "string"}},
            "sources": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                    },
                    "required": ["title", "url"],
                },
            },
        },
        "required": [
            "differential_diagnosis",
            "suggested_tests",
            "suggested_management",
            "red_flags",
            "sources",
        ],
    },
}

TOTAL_TIMEOUT = 120  # seconds

_client = None


def _default():
    return {
        "differential_diagnosis": [],
        "suggested_tests": [],
        "suggested_management": [],
        "red_flags": [],
        "sources": [],
    }


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("PARALLEL_API_KEY")
        if api_key:
            _client = Parallel(api_key=api_key)
        else:
            _client = False  # sentinel: no key configured
    return _client


def _get_attr(obj, name, default=None):
    """Read an attribute from a pydantic model or dict, returning default if missing."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _normalize_item(item):
    """Normalize a differential-diagnosis entry into the expected shape."""
    if not isinstance(item, dict):
        return {"diagnosis": str(item), "likelihood": "low", "rationale": ""}
    diag = _get_attr(item, "diagnosis", "") or ""
    likelihood = _get_attr(item, "likelihood", "low") or "low"
    if likelihood not in ("high", "medium", "low"):
        likelihood = "low"
    rationale = _get_attr(item, "rationale", "") or ""
    return {"diagnosis": diag, "likelihood": likelihood, "rationale": rationale}


def _normalize_source(item):
    """Normalize a source/citation entry into {title, url}."""
    if not isinstance(item, dict):
        return {"title": str(item), "url": ""}
    title = _get_attr(item, "title", "") or ""
    url = _get_attr(item, "url", "") or _get_attr(item, "source_url", "") or ""
    if not title and url:
        title = url
    return {"title": title, "url": url}


def _clean_sources(sources):
    """Keep only well-formed http(s) URLs: no embedded credentials, a real dotted hostname, no duplicates.

    Parallel occasionally returns malformed URLs (e.g. 'https://user:@cdc.gov/...'), and the
    note writer refuses to cite them, so they are dropped here.
    """
    from urllib.parse import urlsplit

    clean, seen = [], set()
    for s in sources:
        url = (s.get("url") or "").strip()
        try:
            parts = urlsplit(url)
        except ValueError:
            continue
        host = parts.hostname or ""
        if (parts.scheme not in ("http", "https") or "@" in parts.netloc
                or "." not in host or not all(p.isalnum() or "-" in p for p in host.split("."))):
            continue
        if url in seen:
            continue
        seen.add(url)
        clean.append({"title": s.get("title") or host, "url": url})
    return clean


def _parse(content, basis):
    """Parse Parallel output content + basis citations into the research schema."""
    data = _default()
    if isinstance(content, dict):
        dd = content.get("differential_diagnosis", [])
        if isinstance(dd, list):
            data["differential_diagnosis"] = [_normalize_item(x) for x in dd]
        data["suggested_tests"] = [str(x) for x in content.get("suggested_tests", [])]
        data["suggested_management"] = [str(x) for x in content.get("suggested_management", [])]
        data["red_flags"] = [str(x) for x in content.get("red_flags", [])]
        srcs = content.get("sources", [])
        if isinstance(srcs, list):
            data["sources"] = [_normalize_source(x) for x in srcs]
    # Augment sources from basis citations if sources were empty.
    if isinstance(basis, list) and not data["sources"]:
        for b in basis:
            if isinstance(b, dict):
                data["sources"].append(_normalize_source(b))
            else:
                data["sources"].append({"title": str(b), "url": ""})
    return data


RESPONSES_URL = "https://api.parallel.ai/v1/responses"
RESPONSES_EFFORT = os.getenv("PARALLEL_EFFORT", "medium")  # low ~5-10s | medium ~15-20s | high ~30-60s


def _strict_schema(schema):
    """Responses API (OpenAI-style) wants additionalProperties:false on every object."""
    if isinstance(schema, dict):
        schema = {k: _strict_schema(v) for k, v in schema.items()}
        if schema.get("type") == "object":
            schema["additionalProperties"] = False
    elif isinstance(schema, list):
        schema = [_strict_schema(x) for x in schema]
    return schema


def research(clinical_question: str, structured: dict) -> dict:
    """Research a clinical question with Parallel's Responses API (low latency).

    The Task API takes 1-4 minutes per run, which is too slow while a doctor
    waits, so this uses Parallel's Responses API (documented for interactive
    use, ~15-20 s at medium effort). On failure it falls back to the Task API
    `lite` processor within the remaining budget. Returns {} on failure so the
    pipeline never breaks; the caller adds a warning.
    """
    api_key = os.getenv("PARALLEL_API_KEY")
    if not api_key:
        return {}

    prompt = (
        "You are assisting a physician. Clinical question: " + (clinical_question or "Not reported") + "\n"
        "Structured consultation data: " + json.dumps(structured) + "\n"
        "Return a differential diagnosis (with likelihood high/medium/low and a short rationale), "
        "suggested tests, suggested management, red flags, and the sources you used (title and URL). "
        "Prefer clinical guidelines, PubMed, CDC, WHO, NIH, and medical societies."
    )
    start = time.monotonic()
    try:
        import httpx

        resp = httpx.post(
            RESPONSES_URL,
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
            json={
                "model": "parallel",
                "input": prompt,
                "reasoning": {"effort": RESPONSES_EFFORT},
                "text": {"format": {
                    "type": "json_schema",
                    "name": "clinical_research",
                    "schema": _strict_schema(RESEARCH_SCHEMA["json_schema"]),
                }},
            },
            timeout=90,
        )
        resp.raise_for_status()
        body = resp.json()
        text, citations = "", []
        for item in body.get("output", []):
            if item.get("type") != "message":
                continue
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    text += part.get("text", "")
                    citations += [a for a in part.get("annotations", []) if a.get("type") == "url_citation"]
        data = _parse(json.loads(text), [])
        # Merge real citation annotations into sources (dedupe by URL).
        seen = {s["url"] for s in data["sources"] if s.get("url")}
        for c in citations:
            if c.get("url") and c["url"] not in seen:
                seen.add(c["url"])
                data["sources"].append({"title": c.get("title") or c["url"], "url": c["url"]})
        data["sources"] = _clean_sources(data["sources"])
        if data["differential_diagnosis"]:
            return data
    except Exception as exc:  # noqa: BLE001 - flow must never break here
        print(f"[research] Responses API failed: {exc}")

    return _task_api_research(clinical_question, structured, TOTAL_TIMEOUT - (time.monotonic() - start))


def _task_api_research(clinical_question: str, structured: dict, budget: float) -> dict:
    """Fallback: Parallel Task API with the fastest processor, bounded by `budget` seconds."""
    client = _get_client()
    if not client or budget < 20:
        return {}

    input_text = (
        "Clinical question: " + clinical_question + "\n"
        "Structured consultation data: " + json.dumps(structured, indent=2) + "\n"
        "Research the differential diagnosis, suggested tests, suggested management, "
        "red flags, and cited sources. Prefer clinical guidelines, PubMed, CDC, WHO, NIH, "
        "and medical societies. Return only the JSON object."
    )

    try:
        run = client.task_run.create(
            input=input_text,
            processor="lite",
            task_spec={"output_schema": RESEARCH_SCHEMA},
        )
        # Block until complete, bounded by the remaining budget.
        result = client.task_run.result(run_id=run.run_id, api_timeout=int(budget), timeout=budget + 5)
        output = _get_attr(result, "output", None)
        data = _parse(_get_attr(output, "content", {}), _get_attr(output, "basis", []))
        data["sources"] = _clean_sources(data["sources"])
        if data["differential_diagnosis"]:
            return data
    except Exception as exc:  # noqa: BLE001 - flow must never break here
        print(f"[research] Task API fallback failed: {exc}")
    return {}