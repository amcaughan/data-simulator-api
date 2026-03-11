import json
import os
from datetime import datetime, timezone

import numpy as np


def _json_response(status_code: int, payload: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }


def handler(event, context):
    event = event or {}

    route = event.get("rawPath") or event.get("path") or event.get("action") or "health"

    if route in ("/health", "health"):
        return _json_response(
            200,
            {
                "status": "ok",
                "service": "data-simulator-api",
                "environment": os.getenv("ENVIRONMENT", "unknown"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    if route in ("/simulate", "simulate"):
        mean = float(event.get("mean", 0.0))
        stddev = float(event.get("stddev", 1.0))
        seed = event.get("seed")

        rng = np.random.default_rng(seed)
        sample = float(rng.normal(loc=mean, scale=stddev))

        return _json_response(
            200,
            {
                "status": "ok",
                "distribution": "normal",
                "mean": mean,
                "stddev": stddev,
                "seed": seed,
                "sample": sample,
            },
        )

    return _json_response(
        404,
        {
            "status": "error",
            "message": f"unknown route: {route}",
        },
    )
