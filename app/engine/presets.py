from __future__ import annotations

from collections.abc import Callable
from app.api.models import PresetGenerateRequest, ScenarioGenerateRequest


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


PresetBuilder = Callable[[PresetGenerateRequest], ScenarioGenerateRequest]


def _build_transaction_preset(request: PresetGenerateRequest) -> ScenarioGenerateRequest:
    overrides = request.overrides
    row_count = request.row_count
    regime_start = int(overrides.get("regime_start_index", max(1, row_count // 2)))

    return ScenarioGenerateRequest.model_validate(
        {
            "schema_version": "1.0",
            "name": "transaction_benchmark",
            "description": "Transaction-like events with benchmark anomalies.",
            "seed": request.seed,
            "row_count": row_count,
            "time": {
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
                            "stddev": float(overrides.get("amount_stddev", 0.35)),
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
                        "parameters": {"probability": float(overrides.get("decline_probability", 0.04))},
                    },
                },
            ],
            "injectors": [
                {
                    "injector_id": "amount_spike",
                    "field": "amount",
                    "selection": {
                        "kind": "rate",
                        "rate": float(overrides.get("anomaly_rate", 0.03)),
                    },
                    "mutation": {
                        "kind": "scale",
                        "factor": float(overrides.get("anomaly_scale", 6.0)),
                    },
                },
                {
                    "injector_id": "amount_regime_shift",
                    "field": "amount",
                    "selection": {
                        "kind": "window",
                        "start_index": regime_start,
                    },
                    "mutation": {
                        "kind": "offset",
                        "amount": float(overrides.get("regime_amount_offset", 35.0)),
                    },
                },
            ],
        }
    )


def _build_iot_sensor_preset(request: PresetGenerateRequest) -> ScenarioGenerateRequest:
    overrides = request.overrides
    row_count = request.row_count
    missing_start = int(overrides.get("missing_start_index", max(1, row_count // 3)))
    stuck_start = int(overrides.get("stuck_start_index", max(1, row_count // 2)))
    stuck_value = float(overrides.get("stuck_value", overrides.get("temperature_mean", 22.0)))

    return ScenarioGenerateRequest.model_validate(
        {
            "schema_version": "1.0",
            "name": "iot_sensor_benchmark",
            "description": "Sensor-like telemetry with quality and regime anomalies.",
            "seed": request.seed,
            "row_count": row_count,
            "time": {
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
                    "injector_id": "sensor_dropout",
                    "field": "pressure_kpa",
                    "selection": {
                        "kind": "window",
                        "start_index": missing_start,
                        "end_index": min(row_count, missing_start + int(overrides.get("missing_length", 5))),
                    },
                    "mutation": {
                        "kind": "set_missing",
                    },
                },
                {
                    "injector_id": "sensor_stuck",
                    "field": "temperature_c",
                    "selection": {
                        "kind": "window",
                        "start_index": stuck_start,
                        "end_index": min(row_count, stuck_start + int(overrides.get("stuck_length", 6))),
                    },
                    "mutation": {
                        "kind": "set_value",
                        "value": stuck_value,
                    },
                },
            ],
        }
    )


def build_preset_generate_request(preset_id: str, request: PresetGenerateRequest) -> ScenarioGenerateRequest:
    builders: dict[str, PresetBuilder] = {
        "iot_sensor_benchmark": _build_iot_sensor_preset,
        "transaction_benchmark": _build_transaction_preset,
    }

    if preset_id not in builders:
        raise ValueError(f"unsupported preset: {preset_id}")

    return builders[preset_id](request)
