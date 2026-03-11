from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.api.models import PresetPreviewRequest, ScenarioPreviewRequest


def list_presets() -> list[dict[str, str]]:
    return [
        {
            "preset_id": "transaction_benchmark",
            "title": "Transaction Benchmark",
            "description": "Synthetic card-like transactions with amount anomalies and regime shift behavior.",
        },
        {
            "preset_id": "iot_sensor_benchmark",
            "title": "IoT Sensor Benchmark",
            "description": "Synthetic sensor telemetry with level shifts, missing bursts, and stuck values.",
        },
    ]


def _build_transaction_preset(request: PresetPreviewRequest) -> ScenarioPreviewRequest:
    overrides = request.overrides
    row_count = request.row_count
    anomaly_index = int(overrides.get("anomaly_index", max(1, row_count // 5)))
    regime_start = int(overrides.get("regime_start_index", max(1, row_count // 2)))

    return ScenarioPreviewRequest.model_validate(
        {
            "schema_version": "1.0",
            "name": "transaction_benchmark",
            "description": "Transaction-like events with benchmark anomalies.",
            "seed": request.seed,
            "row_count": row_count,
            "time": {
                "start": datetime.now(timezone.utc),
                "frequency_seconds": int(overrides.get("frequency_seconds", 300)),
            },
            "fields": [
                {
                    "name": "amount",
                    "generator": {
                        "kind": "distribution",
                        "distribution": "lognormal",
                        "parameters": {
                            "mean": float(overrides.get("amount_log_mean", 4.0)),
                            "sigma": float(overrides.get("amount_sigma", 0.35)),
                        },
                    },
                },
                {
                    "name": "merchant_category",
                    "generator": {
                        "kind": "categorical",
                        "values": ["grocery", "fuel", "retail", "travel"],
                        "weights": [0.45, 0.2, 0.25, 0.1],
                    },
                },
                {
                    "name": "channel",
                    "generator": {
                        "kind": "categorical",
                        "values": ["card_present", "online", "wallet"],
                        "weights": [0.6, 0.3, 0.1],
                    },
                },
                {
                    "name": "is_declined",
                    "generator": {
                        "kind": "distribution",
                        "distribution": "bernoulli",
                        "parameters": {"p": float(overrides.get("decline_probability", 0.04))},
                    },
                },
            ],
            "injectors": [
                {
                    "kind": "point_spike",
                    "injector_id": "amount_spike",
                    "field": "amount",
                    "index": anomaly_index,
                    "scale": float(overrides.get("anomaly_scale", 6.0)),
                },
                {
                    "kind": "level_shift",
                    "injector_id": "amount_regime_shift",
                    "field": "amount",
                    "start_index": regime_start,
                    "offset": float(overrides.get("regime_amount_offset", 35.0)),
                },
            ],
        }
    )


def _build_iot_sensor_preset(request: PresetPreviewRequest) -> ScenarioPreviewRequest:
    overrides = request.overrides
    row_count = request.row_count
    missing_start = int(overrides.get("missing_start_index", max(1, row_count // 3)))
    stuck_start = int(overrides.get("stuck_start_index", max(1, row_count // 2)))

    return ScenarioPreviewRequest.model_validate(
        {
            "schema_version": "1.0",
            "name": "iot_sensor_benchmark",
            "description": "Sensor-like telemetry with quality and regime anomalies.",
            "seed": request.seed,
            "row_count": row_count,
            "time": {
                "start": datetime.now(timezone.utc),
                "frequency_seconds": int(overrides.get("frequency_seconds", 60)),
            },
            "fields": [
                {
                    "name": "temperature_c",
                    "generator": {
                        "kind": "distribution",
                        "distribution": "normal",
                        "parameters": {
                            "mean": float(overrides.get("temperature_mean", 22.0)),
                            "stddev": float(overrides.get("temperature_stddev", 0.6)),
                        },
                    },
                },
                {
                    "name": "pressure_kpa",
                    "generator": {
                        "kind": "distribution",
                        "distribution": "normal",
                        "parameters": {
                            "mean": float(overrides.get("pressure_mean", 101.3)),
                            "stddev": float(overrides.get("pressure_stddev", 0.15)),
                        },
                    },
                },
                {
                    "name": "device_status",
                    "generator": {
                        "kind": "categorical",
                        "values": ["normal", "normal", "normal", "warning"],
                    },
                },
            ],
            "injectors": [
                {
                    "kind": "missing_burst",
                    "injector_id": "sensor_dropout",
                    "field": "pressure_kpa",
                    "start_index": missing_start,
                    "end_index": min(row_count, missing_start + int(overrides.get("missing_length", 5))),
                },
                {
                    "kind": "stuck_value",
                    "injector_id": "sensor_stuck",
                    "field": "temperature_c",
                    "start_index": stuck_start,
                    "end_index": min(row_count, stuck_start + int(overrides.get("stuck_length", 6))),
                },
            ],
        }
    )


def build_preset_preview(preset_id: str, request: PresetPreviewRequest) -> ScenarioPreviewRequest:
    builders: dict[str, Any] = {
        "iot_sensor_benchmark": _build_iot_sensor_preset,
        "transaction_benchmark": _build_transaction_preset,
    }

    if preset_id not in builders:
        raise ValueError(f"unsupported preset: {preset_id}")

    return builders[preset_id](request)
