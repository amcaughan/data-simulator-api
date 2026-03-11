from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from app.api.models import DistributionSampleRequest, PresetPreviewRequest, ScenarioPreviewRequest
from app.engine.distributions import build_distribution_response
from app.engine.presets import build_preset_preview, list_presets
from app.engine.scenario import preview_scenario


def json_response(status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }


def _resolve_route(event: dict[str, Any]) -> str:
    return event.get("rawPath") or event.get("path") or event.get("action") or "health"


def _extract_payload(event: dict[str, Any]) -> dict[str, Any]:
    body = event.get("body")
    if isinstance(body, str) and body:
        return json.loads(body)
    if isinstance(body, dict):
        return body

    ignored_keys = {"action", "body", "headers", "httpMethod", "path", "pathParameters", "queryStringParameters", "rawPath", "requestContext"}
    return {key: value for key, value in event.items() if key not in ignored_keys}


def _extract_preset_id(route: str, event: dict[str, Any], payload: dict[str, Any]) -> str | None:
    path_parameters = event.get("pathParameters") or {}
    if "preset_id" in path_parameters:
        return path_parameters["preset_id"]
    if "preset_id" in payload:
        return payload["preset_id"]

    parts = [part for part in route.split("/") if part]
    if len(parts) >= 4 and parts[0] == "v1" and parts[1] == "presets" and parts[3] == "preview":
        return parts[2]

    return None


def _distribution_payload_from_legacy_simulate(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "distribution": payload.get("distribution", "normal"),
        "parameters": {
            "mean": payload.get("mean", 0.0),
            "stddev": payload.get("stddev", 1.0),
        },
        "count": payload.get("count", 1),
        "seed": payload.get("seed"),
        "summary": payload.get("summary", False),
    }


def handle_request(event: dict[str, Any]) -> dict[str, Any]:
    route = _resolve_route(event)
    payload = _extract_payload(event)

    try:
        if route in ("/health", "health"):
            return json_response(
                200,
                {
                    "status": "ok",
                    "service": "data-simulator-api",
                    "environment": os.getenv("ENVIRONMENT", "unknown"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

        if route in ("/simulate", "simulate", "/v1/distributions/sample", "sample_distribution"):
            request = DistributionSampleRequest.model_validate(
                payload if "distribution" in payload else _distribution_payload_from_legacy_simulate(payload)
            )
            return json_response(200, build_distribution_response(request))

        if route in ("/v1/scenarios/preview", "scenario_preview"):
            request = ScenarioPreviewRequest.model_validate(payload)
            return json_response(200, preview_scenario(request))

        if route in ("/v1/presets", "presets", "list_presets"):
            return json_response(200, {"presets": list_presets()})

        if route in ("/v1/presets/preview", "preset_preview") or route.endswith("/preview"):
            preset_id = _extract_preset_id(route, event, payload)
            if not preset_id:
                raise ValueError("preset preview requires a preset_id")

            request = PresetPreviewRequest.model_validate(payload)
            scenario_request = build_preset_preview(preset_id, request)
            return json_response(200, preview_scenario(scenario_request))

    except ValidationError as exc:
        return json_response(400, {"error": "validation_error", "details": json.loads(exc.json())})
    except ValueError as exc:
        return json_response(400, {"error": "bad_request", "message": str(exc)})

    return json_response(
        404,
        {
            "error": "not_found",
            "message": f"unknown route: {route}",
        },
    )
