"""CloudWatch Embedded Metric Format: one JSON log line per question becomes metrics.

Namespace `InfraAtlas/Agent`, per `Model` and without dimensions (for the alarms). The SAM
template's dashboard and alarms read these (deploy/template.yaml).
"""

from __future__ import annotations

import json
import sys
import time

NAMESPACE = "InfraAtlas/Agent"
UNITS = {
    "LatencyMs": "Milliseconds",
    "InputTokens": "Count",
    "OutputTokens": "Count",
    "CachedTokens": "Count",
    "CostUSD": "None",
    "ToolCalls": "Count",
    "Errors": "Count",
    "Ungrounded": "Count",
}


def emit(model: str, values: dict[str, float], route: str = "") -> str:
    line = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": NAMESPACE,
                    "Dimensions": [["Model"], []],
                    "Metrics": [{"Name": k, "Unit": UNITS.get(k, "None")} for k in values],
                }
            ],
        },
        "Model": model,
        "Route": route,
        **values,
    }
    text = json.dumps(line)
    print(text, file=sys.stdout, flush=True)
    return text
