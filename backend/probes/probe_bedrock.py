"""Probe: which Amazon Bedrock models answer with tool calls for this account, per region.

Authenticates with a Bedrock API key (BEDROCK_API_KEY, read by boto3 as
AWS_BEARER_TOKEN_BEDROCK) or IAM credentials. Lists the region's text models that support
Converse and tool use where the key may list them, then sends one short Converse request with a
tool to each candidate (a few tokens each) and reports: answered, tool called, tokens, latency,
or the error (access, quota, not available in the region). Claude models are left out (AWS
credits do not pay for them; vault decision 2026-10-18).

    uv run python -m probes.probe_bedrock [region ...]
"""

from __future__ import annotations

import os
import sys
import time

import boto3

REGIONS = sys.argv[1:] or ["us-east-1", "us-west-2", "eu-central-1", "eu-west-1"]
# candidates by family; inference-profile prefixes (us., eu.) are tried per region
CANDIDATES = [
    "amazon.nova-pro-v1:0",
    "amazon.nova-lite-v1:0",
    "amazon.nova-micro-v1:0",
    "amazon.nova-premier-v1:0",
    "meta.llama3-3-70b-instruct-v1:0",
    "meta.llama4-maverick-17b-instruct-v1:0",
    "mistral.mistral-large-2407-v1:0",
    "openai.gpt-oss-120b-1:0",
    "openai.gpt-oss-20b-1:0",
    "qwen.qwen3-235b-a22b-2507-v1:0",
    "qwen.qwen3-32b-v1:0",
    "deepseek.v3-v1:0",
]
TOOL = {
    "tools": [
        {
            "toolSpec": {
                "name": "find_place",
                "description": "Resolve a place name to codes.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                    }
                },
            }
        }
    ]
}

if os.environ.get("BEDROCK_API_KEY") and not os.environ.get("AWS_BEARER_TOKEN_BEDROCK"):
    os.environ["AWS_BEARER_TOKEN_BEDROCK"] = os.environ["BEDROCK_API_KEY"]


def ids_for(region: str, model: str) -> list[str]:
    geo = "eu" if region.startswith("eu-") else "us" if region.startswith("us-") else ""
    return [model] + ([f"{geo}.{model}"] if geo else [])


for region in REGIONS:
    print(f"\n== {region}")
    try:
        listed = boto3.client("bedrock", region_name=region).list_foundation_models(
            byOutputModality="TEXT"
        )["modelSummaries"]
        names = sorted(
            m["modelId"]
            for m in listed
            if "ON_DEMAND" in m.get("inferenceTypesSupported", [])
            and not m["modelId"].startswith("anthropic.")
        )
        print(f"   listed {len(names)} on-demand text models (non-Claude): {names[:40]}")
    except Exception as e:  # an API key may not allow listing
        print(f"   list_foundation_models: {type(e).__name__}: {str(e)[:120]}")
    rt = boto3.client("bedrock-runtime", region_name=region)
    for model in CANDIDATES:
        for mid in ids_for(region, model):
            t0 = time.perf_counter()
            try:
                r = rt.converse(
                    modelId=mid,
                    messages=[
                        {"role": "user", "content": [{"text": "Call find_place for 'Amsterdam'."}]}
                    ],
                    toolConfig=TOOL,
                    inferenceConfig={"maxTokens": 120},
                )
            except Exception as e:
                msg = str(e).replace("\n", " ")
                print(f"   {mid}: {type(e).__name__}: {msg[:110]}")
                continue
            blocks = r["output"]["message"]["content"]
            tools = [b["toolUse"]["name"] for b in blocks if "toolUse" in b]
            u = r.get("usage", {})
            print(
                f"   {mid}: OK stop={r.get('stopReason')} tools={tools} "
                f"tokens in/out={u.get('inputTokens')}/{u.get('outputTokens')} "
                f"{time.perf_counter() - t0:.2f}s"
            )
            break
