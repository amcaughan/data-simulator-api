from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from app.api.models import (
    DistributionGenerateRequest,
    DistributionSampleRequest,
    PresetGenerateRequest,
    ScenarioGenerateRequest,
    ScenarioSampleRequest,
)
from app.engine.distributions import build_distribution_generate_response, build_distribution_sample_response
from app.engine.presets import build_preset_generate_request, list_presets
from app.engine.scenario import generate_scenario, sample_scenario


SUPPORTED_ROUTES = [
    "/health",
    "/v1/distributions/sample",
    "/v1/distributions/generate",
    "/v1/scenarios/sample",
    "/v1/scenarios/generate",
    "/v1/presets",
    "/v1/presets/{preset_id}/generate",
]


def json_response(status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }


def _resolve_route(event: dict[str, Any]) -> str:
    return event.get("rawPath") or event.get("path") or event.get("action") or "/health"


def _extract_payload(event: dict[str, Any]) -> dict[str, Any]:
    body = event.get("body")
    if isinstance(body, str) and body:
        return json.loads(body)
    if isinstance(body, dict):
        return body

    ignored_keys = {"action", "body", "headers", "httpMethod", "path", "pathParameters", "queryStringParameters", "rawPath", "requestContext"}
    return {key: value for key, value in event.items() if key not in ignored_keys}


def _extract_preset_id(route: str, event: dict[str, Any]) -> str | None:
    path_parameters = event.get("pathParameters") or {}
    if "preset_id" in path_parameters:
        return path_parameters["preset_id"]

    parts = [part for part in route.split("/") if part]
    if len(parts) == 4 and parts[0] == "v1" and parts[1] == "presets" and parts[3] == "generate":
        return parts[2]

    return None


def _format_validation_error(exc: ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "request validation failed"

    first_error = errors[0]
    location = ".".join(str(part) for part in first_error.get("loc", ()))
    message = first_error.get("msg", "invalid value")

    if len(errors) == 1:
        return f"validation failed at {location}: {message}"

    return f"validation failed at {location}: {message} ({len(errors) - 1} additional validation issues)"


def handle_request(event: dict[str, Any]) -> dict[str, Any]:
    route = _resolve_route(event)

    try:
        payload = _extract_payload(event)

        if route == "/health":
            return json_response(
                200,
                {
                    "status": "ok",
                    "service": "data-simulator-api",
                    "environment": os.getenv("ENVIRONMENT", "unknown"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

        if route == "/v1/distributions/sample":
            request = DistributionSampleRequest.model_validate(payload)
            return json_response(200, build_distribution_sample_response(request))

        if route == "/v1/distributions/generate":
            request = DistributionGenerateRequest.model_validate(payload)
            return json_response(200, build_distribution_generate_response(request))

        if route == "/v1/scenarios/sample":
            request = ScenarioSampleRequest.model_validate(payload)
            return json_response(200, sample_scenario(request))

        if route == "/v1/scenarios/generate":
            request = ScenarioGenerateRequest.model_validate(payload)
            return json_response(200, generate_scenario(request))

        if route == "/v1/presets":
            return json_response(200, {"presets": list_presets()})

        preset_id = _extract_preset_id(route, event)
        if preset_id:
            request = PresetGenerateRequest.model_validate(payload)
            scenario_request = build_preset_generate_request(preset_id, request)
            return json_response(200, generate_scenario(scenario_request))

        if route.startswith("/v1/presets/") and route.endswith("/generate"):
            raise ValueError(
                "preset generate requires a preset_id in the route, for example "
                "'/v1/presets/transaction_benchmark/generate'"
            )

    except ValidationError as exc:
        return json_response(
            400,
            {
                "error": "validation_error",
                "message": _format_validation_error(exc),
                "details": json.loads(exc.json()),
            },
        )
    except json.JSONDecodeError as exc:
        return json_response(
            400,
            {
                "error": "bad_request",
                "message": f"request body must be valid JSON: {exc.msg}",
            },
        )
    except ValueError as exc:
        return json_response(400, {"error": "bad_request", "message": str(exc)})

    return json_response(
        404,
        {
            "error": "not_found",
            "message": f"unknown route: {route}. Supported routes: {', '.join(SUPPORTED_ROUTES)}",
        },
    )
