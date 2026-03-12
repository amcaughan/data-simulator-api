from __future__ import annotations

from collections.abc import Callable
from app.api.models import PresetGenerateRequest, ScenarioGenerateRequest


def _default_entity_count(row_count: int, ratio: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, max(1, row_count // ratio)))


def _prefixed_values(prefix: str, count: int) -> list[str]:
    return [f"{prefix}_{index:03d}" for index in range(1, count + 1)]


def list_presets() -> list[dict[str, str]]:
    return [
        {
            "preset_id": "transaction_benchmark",
            "title": "Transaction Benchmark",
            "description": "Synthetic card-like transactions with card and merchant dimensions.",
        },
        {
            "preset_id": "iot_sensor_benchmark",
            "title": "IoT Sensor Benchmark",
            "description": "Synthetic sensor telemetry with device and site dimensions.",
        },
        {
            "preset_id": "order_benchmark",
            "title": "Order Benchmark",
            "description": "Synthetic order events with customer and product dimensions.",
        },
    ]


PresetBuilder = Callable[[PresetGenerateRequest], ScenarioGenerateRequest]


def _build_transaction_preset(request: PresetGenerateRequest) -> ScenarioGenerateRequest:
    overrides = request.overrides
    row_count = request.row_count
    regime_start = int(overrides.get("regime_start_index", max(1, row_count // 2)))
    card_count = int(overrides.get("card_count", _default_entity_count(row_count, ratio=4, minimum=6, maximum=250)))
    merchant_count = int(
        overrides.get("merchant_count", _default_entity_count(row_count, ratio=6, minimum=4, maximum=100))
    )

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
            "entity_pools": [
                {
                    "name": "cards",
                    "count": card_count,
                    "id_prefix": "card",
                    "attributes": [
                        {
                            "name": "card_region",
                            "generator": {
                                "kind": "categorical",
                                "values": ["west", "midwest", "south", "northeast"],
                                "weights": [0.22, 0.24, 0.32, 0.22],
                            },
                        },
                        {
                            "name": "card_segment",
                            "generator": {
                                "kind": "categorical",
                                "values": ["standard", "premium", "small_business"],
                                "weights": [0.7, 0.2, 0.1],
                            },
                        },
                        {
                            "name": "spend_bias",
                            "generator": {
                                "kind": "distribution",
                                "distribution": "normal",
                                "parameters": {"mean": 0.0, "stddev": 0.18},
                            },
                        },
                    ],
                },
                {
                    "name": "merchants",
                    "count": merchant_count,
                    "id_prefix": "merchant",
                    "attributes": [
                        {
                            "name": "merchant_category",
                            "generator": {
                                "kind": "categorical",
                                "values": ["grocery", "fuel", "retail", "travel", "dining"],
                                "weights": [0.3, 0.18, 0.28, 0.08, 0.16],
                            },
                        },
                        {
                            "name": "merchant_region",
                            "generator": {
                                "kind": "categorical",
                                "values": ["west", "midwest", "south", "northeast"],
                                "weights": [0.21, 0.25, 0.31, 0.23],
                            },
                        },
                        {
                            "name": "merchant_risk_tier",
                            "generator": {
                                "kind": "categorical",
                                "values": ["low", "medium", "high"],
                                "weights": [0.65, 0.25, 0.1],
                            },
                        },
                        {
                            "name": "ticket_size_bias",
                            "generator": {
                                "kind": "distribution",
                                "distribution": "normal",
                                "parameters": {"mean": 0.0, "stddev": 0.14},
                            },
                        },
                    ],
                },
            ],
            "fields": [
                {
                    "name": "card_id",
                    "generator": {
                        "kind": "entity_id",
                        "entity_name": "cards",
                    },
                },
                {
                    "name": "card_region",
                    "generator": {
                        "kind": "entity_attribute",
                        "entity_name": "cards",
                        "attribute": "card_region",
                    },
                },
                {
                    "name": "card_segment",
                    "generator": {
                        "kind": "entity_attribute",
                        "entity_name": "cards",
                        "attribute": "card_segment",
                    },
                },
                {
                    "name": "merchant_id",
                    "generator": {
                        "kind": "entity_id",
                        "entity_name": "merchants",
                    },
                },
                {
                    "name": "merchant_category",
                    "generator": {
                        "kind": "entity_attribute",
                        "entity_name": "merchants",
                        "attribute": "merchant_category",
                    },
                },
                {
                    "name": "merchant_region",
                    "generator": {
                        "kind": "entity_attribute",
                        "entity_name": "merchants",
                        "attribute": "merchant_region",
                    },
                },
                {
                    "name": "merchant_risk_tier",
                    "generator": {
                        "kind": "entity_attribute",
                        "entity_name": "merchants",
                        "attribute": "merchant_risk_tier",
                    },
                },
                {
                    "name": "amount",
                    "generator": {
                        "kind": "contextual_distribution",
                        "distribution": "lognormal",
                        "parameters": {
                            "mean": float(overrides.get("amount_log_mean", 4.0)),
                            "stddev": float(overrides.get("amount_stddev", 0.35)),
                        },
                        "parameter_modifiers": [
                            {
                                "parameter": "mean",
                                "operation": "add",
                                "entity_name": "cards",
                                "entity_attribute": "spend_bias",
                            },
                            {
                                "parameter": "mean",
                                "operation": "add",
                                "entity_name": "merchants",
                                "entity_attribute": "ticket_size_bias",
                            },
                            {
                                "parameter": "mean",
                                "operation": "add",
                                "value": float(overrides.get("premium_segment_amount_shift", 0.22)),
                                "when": [{"field": "card_segment", "equals": "premium"}],
                            },
                            {
                                "parameter": "mean",
                                "operation": "add",
                                "value": float(overrides.get("high_risk_amount_shift", 0.18)),
                                "when": [{"field": "merchant_risk_tier", "equals": "high"}],
                            },
                        ],
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
                        "kind": "contextual_distribution",
                        "distribution": "bernoulli",
                        "parameters": {"probability": float(overrides.get("decline_probability", 0.04))},
                        "parameter_modifiers": [
                            {
                                "parameter": "probability",
                                "operation": "multiply",
                                "value": float(overrides.get("online_decline_multiplier", 1.6)),
                                "when": [{"field": "channel", "equals": "online"}],
                            },
                            {
                                "parameter": "probability",
                                "operation": "multiply",
                                "value": float(overrides.get("high_risk_decline_multiplier", 2.0)),
                                "when": [{"field": "merchant_risk_tier", "equals": "high"}],
                            },
                            {
                                "parameter": "probability",
                                "operation": "multiply",
                                "value": float(overrides.get("premium_decline_multiplier", 0.8)),
                                "when": [{"field": "card_segment", "equals": "premium"}],
                            },
                        ],
                    },
                },
            ],
            "injectors": [
                {
                    "injector_id": "amount_spike",
                    "field": "amount",
                    "scope": [
                        {
                            "field": "merchant_risk_tier",
                            "equals": "high",
                        }
                    ],
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
    site_count = int(overrides.get("site_count", _default_entity_count(row_count, ratio=30, minimum=3, maximum=24)))
    device_count = int(overrides.get("device_count", _default_entity_count(row_count, ratio=8, minimum=6, maximum=150)))

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
            "entity_pools": [
                {
                    "name": "devices",
                    "count": device_count,
                    "id_prefix": "device",
                    "attributes": [
                        {
                            "name": "site_id",
                            "generator": {
                                "kind": "categorical",
                                "values": _prefixed_values("site", site_count),
                            },
                        },
                        {
                            "name": "device_type",
                            "generator": {
                                "kind": "categorical",
                                "values": ["thermometer", "pressure_sensor", "combo_sensor"],
                                "weights": [0.35, 0.25, 0.4],
                            },
                        },
                        {
                            "name": "temperature_offset",
                            "generator": {
                                "kind": "distribution",
                                "distribution": "normal",
                                "parameters": {"mean": 0.0, "stddev": 0.45},
                            },
                        },
                        {
                            "name": "pressure_offset",
                            "generator": {
                                "kind": "distribution",
                                "distribution": "normal",
                                "parameters": {"mean": 0.0, "stddev": 0.08},
                            },
                        },
                        {
                            "name": "noise_multiplier",
                            "generator": {
                                "kind": "categorical",
                                "values": [0.8, 1.0, 1.25],
                                "weights": [0.2, 0.55, 0.25],
                            },
                        },
                    ],
                }
            ],
            "fields": [
                {
                    "name": "device_id",
                    "generator": {
                        "kind": "entity_id",
                        "entity_name": "devices",
                    },
                },
                {
                    "name": "site_id",
                    "generator": {
                        "kind": "entity_attribute",
                        "entity_name": "devices",
                        "attribute": "site_id",
                    },
                },
                {
                    "name": "device_type",
                    "generator": {
                        "kind": "entity_attribute",
                        "entity_name": "devices",
                        "attribute": "device_type",
                    },
                },
                {
                    "name": "temperature_c",
                    "generator": {
                        "kind": "contextual_distribution",
                        "distribution": "normal",
                        "parameters": {
                            "mean": float(overrides.get("temperature_mean", 22.0)),
                            "stddev": float(overrides.get("temperature_stddev", 0.6)),
                        },
                        "parameter_modifiers": [
                            {
                                "parameter": "mean",
                                "operation": "add",
                                "entity_name": "devices",
                                "entity_attribute": "temperature_offset",
                            },
                            {
                                "parameter": "stddev",
                                "operation": "multiply",
                                "entity_name": "devices",
                                "entity_attribute": "noise_multiplier",
                            },
                            {
                                "parameter": "stddev",
                                "operation": "multiply",
                                "value": float(overrides.get("combo_sensor_noise_multiplier", 1.15)),
                                "when": [{"field": "device_type", "equals": "combo_sensor"}],
                            },
                        ],
                    },
                },
                {
                    "name": "pressure_kpa",
                    "generator": {
                        "kind": "contextual_distribution",
                        "distribution": "normal",
                        "parameters": {
                            "mean": float(overrides.get("pressure_mean", 101.3)),
                            "stddev": float(overrides.get("pressure_stddev", 0.15)),
                        },
                        "parameter_modifiers": [
                            {
                                "parameter": "mean",
                                "operation": "add",
                                "entity_name": "devices",
                                "entity_attribute": "pressure_offset",
                            },
                            {
                                "parameter": "stddev",
                                "operation": "multiply",
                                "entity_name": "devices",
                                "entity_attribute": "noise_multiplier",
                            },
                        ],
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
                    "scope": [
                        {
                            "field": "device_type",
                            "equals": "pressure_sensor",
                        }
                    ],
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
                    "scope": [
                        {
                            "field": "device_type",
                            "equals": "thermometer",
                        }
                    ],
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


def _build_order_preset(request: PresetGenerateRequest) -> ScenarioGenerateRequest:
    overrides = request.overrides
    row_count = request.row_count
    delay_start = int(overrides.get("delay_start_index", max(1, row_count // 2)))
    customer_count = int(
        overrides.get("customer_count", _default_entity_count(row_count, ratio=5, minimum=8, maximum=300))
    )
    product_count = int(
        overrides.get("product_count", _default_entity_count(row_count, ratio=7, minimum=6, maximum=200))
    )

    return ScenarioGenerateRequest.model_validate(
        {
            "schema_version": "1.0",
            "name": "order_benchmark",
            "description": "Order-like events with customer and product dimensions.",
            "seed": request.seed,
            "row_count": row_count,
            "time": {
                "frequency_seconds": int(overrides.get("frequency_seconds", 900)),
            },
            "entity_pools": [
                {
                    "name": "customers",
                    "count": customer_count,
                    "id_prefix": "customer",
                    "attributes": [
                        {
                            "name": "customer_region",
                            "generator": {
                                "kind": "categorical",
                                "values": ["west", "midwest", "south", "northeast"],
                                "weights": [0.2, 0.24, 0.34, 0.22],
                            },
                        },
                        {
                            "name": "loyalty_tier",
                            "generator": {
                                "kind": "categorical",
                                "values": ["standard", "silver", "gold"],
                                "weights": [0.65, 0.23, 0.12],
                            },
                        },
                        {
                            "name": "customer_spend_bias",
                            "generator": {
                                "kind": "distribution",
                                "distribution": "normal",
                                "parameters": {"mean": 0.0, "stddev": 0.16},
                            },
                        },
                    ],
                },
                {
                    "name": "products",
                    "count": product_count,
                    "id_prefix": "product",
                    "attributes": [
                        {
                            "name": "product_category",
                            "generator": {
                                "kind": "categorical",
                                "values": ["apparel", "electronics", "home", "beauty", "outdoor"],
                                "weights": [0.24, 0.18, 0.22, 0.16, 0.2],
                            },
                        },
                        {
                            "name": "price_band",
                            "generator": {
                                "kind": "categorical",
                                "values": ["budget", "midrange", "premium"],
                                "weights": [0.4, 0.42, 0.18],
                            },
                        },
                        {
                            "name": "product_price_bias",
                            "generator": {
                                "kind": "distribution",
                                "distribution": "normal",
                                "parameters": {"mean": 0.0, "stddev": 0.22},
                            },
                        },
                    ],
                },
            ],
            "fields": [
                {
                    "name": "customer_id",
                    "generator": {
                        "kind": "entity_id",
                        "entity_name": "customers",
                    },
                },
                {
                    "name": "customer_region",
                    "generator": {
                        "kind": "entity_attribute",
                        "entity_name": "customers",
                        "attribute": "customer_region",
                    },
                },
                {
                    "name": "loyalty_tier",
                    "generator": {
                        "kind": "entity_attribute",
                        "entity_name": "customers",
                        "attribute": "loyalty_tier",
                    },
                },
                {
                    "name": "product_id",
                    "generator": {
                        "kind": "entity_id",
                        "entity_name": "products",
                    },
                },
                {
                    "name": "product_category",
                    "generator": {
                        "kind": "entity_attribute",
                        "entity_name": "products",
                        "attribute": "product_category",
                    },
                },
                {
                    "name": "price_band",
                    "generator": {
                        "kind": "entity_attribute",
                        "entity_name": "products",
                        "attribute": "price_band",
                    },
                },
                {
                    "name": "sales_channel",
                    "generator": {
                        "kind": "categorical",
                        "values": ["web", "mobile", "marketplace"],
                        "weights": [0.45, 0.4, 0.15],
                    },
                },
                {
                    "name": "fulfillment_status",
                    "generator": {
                        "kind": "categorical",
                        "values": ["processing", "packed", "shipped"],
                        "weights": [0.25, 0.2, 0.55],
                    },
                },
                {
                    "name": "order_amount",
                    "generator": {
                        "kind": "contextual_distribution",
                        "distribution": "lognormal",
                        "parameters": {
                            "mean": float(overrides.get("amount_log_mean", 3.8)),
                            "stddev": float(overrides.get("amount_stddev", 0.42)),
                        },
                        "parameter_modifiers": [
                            {
                                "parameter": "mean",
                                "operation": "add",
                                "entity_name": "customers",
                                "entity_attribute": "customer_spend_bias",
                            },
                            {
                                "parameter": "mean",
                                "operation": "add",
                                "entity_name": "products",
                                "entity_attribute": "product_price_bias",
                            },
                            {
                                "parameter": "mean",
                                "operation": "add",
                                "value": float(overrides.get("gold_loyalty_amount_shift", -0.08)),
                                "when": [{"field": "loyalty_tier", "equals": "gold"}],
                            },
                            {
                                "parameter": "mean",
                                "operation": "add",
                                "value": float(overrides.get("premium_band_amount_shift", 0.3)),
                                "when": [{"field": "price_band", "equals": "premium"}],
                            },
                        ],
                    },
                },
                {
                    "name": "is_returned",
                    "generator": {
                        "kind": "contextual_distribution",
                        "distribution": "bernoulli",
                        "parameters": {"probability": float(overrides.get("return_probability", 0.08))},
                        "parameter_modifiers": [
                            {
                                "parameter": "probability",
                                "operation": "multiply",
                                "value": float(overrides.get("apparel_return_multiplier", 1.4)),
                                "when": [{"field": "product_category", "equals": "apparel"}],
                            },
                            {
                                "parameter": "probability",
                                "operation": "multiply",
                                "value": float(overrides.get("gold_return_multiplier", 0.7)),
                                "when": [{"field": "loyalty_tier", "equals": "gold"}],
                            },
                        ],
                    },
                },
            ],
            "injectors": [
                {
                    "injector_id": "order_amount_spike",
                    "field": "order_amount",
                    "scope": [
                        {
                            "field": "sales_channel",
                            "equals": "marketplace",
                        }
                    ],
                    "selection": {
                        "kind": "rate",
                        "rate": float(overrides.get("anomaly_rate", 0.025)),
                    },
                    "mutation": {
                        "kind": "scale",
                        "min_factor": float(overrides.get("min_anomaly_scale", 2.0)),
                        "max_factor": float(overrides.get("max_anomaly_scale", 4.5)),
                    },
                },
                {
                    "injector_id": "fulfillment_delay",
                    "field": "fulfillment_status",
                    "scope": [
                        {
                            "field": "sales_channel",
                            "equals": "marketplace",
                        }
                    ],
                    "selection": {
                        "kind": "window",
                        "start_index": delay_start,
                        "end_index": min(row_count, delay_start + int(overrides.get("delay_length", 10))),
                    },
                    "mutation": {
                        "kind": "set_value",
                        "value": "delayed",
                    },
                },
            ],
        }
    )


def build_preset_generate_request(preset_id: str, request: PresetGenerateRequest) -> ScenarioGenerateRequest:
    builders: dict[str, PresetBuilder] = {
        "iot_sensor_benchmark": _build_iot_sensor_preset,
        "order_benchmark": _build_order_preset,
        "transaction_benchmark": _build_transaction_preset,
    }

    if preset_id not in builders:
        raise ValueError(f"unsupported preset: {preset_id}")

    return builders[preset_id](request)
