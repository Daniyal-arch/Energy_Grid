"""Probe: which Gemini models a Google AI Studio key can use, and whether they call tools.

Reads GOOGLE_API_KEY (or GEMINI_API_KEY). Lists the models the key may call for
generateContent (newest first), then sends one short request with a tool to each candidate (a
few tokens each) and reports: answered, tool called, tokens, latency, or the error (quota,
free-tier limits, model not available). The key travels in a header, never in a URL or the
output.

    uv run python -m probes.probe_gemini [model ...]
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

API = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200"


def key() -> str:
    k = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not k:
        sys.exit("GOOGLE_API_KEY (or GEMINI_API_KEY) is not set")
    return k


def models() -> list[dict[str, object]]:
    req = urllib.request.Request(API, headers={"x-goog-api-key": key()})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    out = [
        m
        for m in data.get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
        and str(m["name"]).startswith("models/gemini")
    ]
    return sorted(out, key=lambda m: str(m["name"]), reverse=True)


@tool
def peak_load(country: str) -> str:
    """Return the peak electricity load of a country (ISO alpha-2 code)."""
    return "not used"


def try_model(name: str) -> str:
    llm = ChatGoogleGenerativeAI(model=name, google_api_key=key(), max_output_tokens=256)
    t0 = time.perf_counter()
    try:
        r = llm.bind_tools([peak_load]).invoke(
            "What is Germany's peak load? Use the tool.",
        )
    except Exception as e:  # the error is the finding
        return f"error {type(e).__name__}: {str(e)[:200]}"
    ms = (time.perf_counter() - t0) * 1000
    u = r.usage_metadata or {}
    called = [c["name"] for c in r.tool_calls]
    return (
        f"ok {ms:.0f} ms, tool called: {called or 'none'}, "
        f"tokens in {u.get('input_tokens')} out {u.get('output_tokens')}"
    )


def main() -> None:
    listed = models()
    print(f"{len(listed)} Gemini models for generateContent:")
    for m in listed:
        print(
            f"  {str(m['name'])[7:]:42} in {m.get('inputTokenLimit')}  out {m.get('outputTokenLimit')}"
        )
    names = (
        sys.argv[1:]
        or [
            str(m["name"])[7:]
            for m in listed
            if not any(w in str(m["name"]) for w in ("tts", "image", "embedding", "live", "audio"))
        ][:8]
    )
    print("\nTool call per model:")
    for n in names:
        print(f"  {n:42} {try_model(n)}")


if __name__ == "__main__":
    main()
