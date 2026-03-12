import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.api.models import PresetGenerateRequest, PresetSampleRequest, ScenarioGenerateRequest, ScenarioSampleRequest
from app.api.router import handle_request
from app.engine.presets import build_preset_generate_request, build_preset_sample_request, list_presets
from app.engine.scenario import generate_scenario, sample_scenario


class ScenarioEngineTest(unittest.TestCase):
    def test_generate_scenario_applies_labels(self):
        request = ScenarioGenerateRequest.model_validate(
            {
                "name": "simple_generate",
                "seed": 11,
                "row_count": 6,
                "fields": [
                    {
                        "name": "value",
                        "generator": {
                            "kind": "distribution",
                            "distribution": "normal",
                            "parameters": {"mean": 5.0, "stddev": 1.0},
                        },
                    }
                ],
                "mutations": [
                    {
                        "mutation_id": "spike_1",
                        "field": "value",
                        "selection": {
                            "kind": "index",
                            "index": 2,
                        },
                        "mutation": {
                            "kind": "scale",
                            "factor": 10.0,
                        },
                    }
                ],
            }
        )

        payload = generate_scenario(request)

        self.assertEqual(payload["scenario_name"], "simple_generate")
        self.assertEqual(payload["row_count"], 6)
        self.assertEqual(payload["label_summary"]["anomalous_rows"], 1)
        self.assertTrue(payload["rows"][2]["__is_anomaly"])
        label = payload["rows"][2]["__labels"][0]
        self.assertEqual(label["mutation_id"], "spike_1")
        self.assertEqual(label["selection_kind"], "index")
        self.assertEqual(label["applied_mutation"]["factor"], 10.0)
        self.assertAlmostEqual(label["mutated_value"], label["original_value"] * 10.0)
        self.assertAlmostEqual(payload["rows"][2]["value"], label["mutated_value"])

    def test_generate_scenario_supports_rate_based_mutations(self):
        request = ScenarioGenerateRequest.model_validate(
            {
                "name": "rate_generate",
                "seed": 17,
                "row_count": 50,
                "fields": [
                    {
                        "name": "value",
                        "generator": {
                            "kind": "distribution",
                            "distribution": "normal",
                            "parameters": {"mean": 10.0, "stddev": 1.5},
                        },
                    }
                ],
                "mutations": [
                    {
                        "mutation_id": "random_spikes",
                        "field": "value",
                        "selection": {
                            "kind": "rate",
                            "rate": 0.1,
                        },
                        "mutation": {
                            "kind": "scale",
                            "factor": 5.0,
                        },
                    }
                ],
            }
        )

        payload = generate_scenario(request)

        self.assertGreater(payload["label_summary"]["anomalous_rows"], 0)
        self.assertEqual(
            payload["label_summary"]["anomaly_counts"]["scale"],
            payload["label_summary"]["anomalous_rows"],
        )

    def test_generate_scenario_supports_count_selection(self):
        request = ScenarioGenerateRequest.model_validate(
            {
                "name": "count_generate",
                "seed": 23,
                "row_count": 10,
                "fields": [
                    {
                        "name": "value",
                        "generator": {
                            "kind": "distribution",
                            "distribution": "normal",
                            "parameters": {"mean": 10.0, "stddev": 1.0},
                        },
                    }
                ],
                "mutations": [
                    {
                        "mutation_id": "three_scales",
                        "field": "value",
                        "selection": {
                            "kind": "count",
                            "count": 3,
                        },
                        "mutation": {
                            "kind": "scale",
                            "factor": 2.0,
                        },
                    }
                ],
            }
        )

        payload = generate_scenario(request)

        self.assertEqual(payload["label_summary"]["anomalous_rows"], 3)
        self.assertEqual(payload["label_summary"]["anomaly_counts"]["scale"], 3)

    def test_generate_scenario_is_deterministic_for_seed(self):
        request = ScenarioGenerateRequest.model_validate(
            {
                "name": "deterministic_generate",
                "seed": 23,
                "row_count": 10,
                "process_modifiers": [
                    {
                        "modifier_id": "mean_shift",
                        "field": "value",
                        "selection": {
                            "kind": "count",
                            "count": 2,
                        },
                        "parameter_modifiers": [
                            {
                                "parameter": "mean",
                                "operation": "add",
                                "value": 1.5,
                            }
                        ],
                    }
                ],
                "fields": [
                    {
                        "name": "value",
                        "generator": {
                            "kind": "distribution",
                            "distribution": "normal",
                            "parameters": {"mean": 10.0, "stddev": 1.0},
                        },
                    }
                ],
                "mutations": [
                    {
                        "mutation_id": "three_scales",
                        "field": "value",
                        "selection": {
                            "kind": "count",
                            "count": 3,
                        },
                        "mutation": {
                            "kind": "offset",
                            "min_amount": 3.0,
                            "max_amount": 5.0,
                        },
                    }
                ],
            }
        )

        first = generate_scenario(request)
        second = generate_scenario(request)

        self.assertEqual(first, second)

    def test_generate_scenario_supports_entity_pools(self):
        request = ScenarioGenerateRequest.model_validate(
            {
                "name": "entity_generate",
                "seed": 29,
                "row_count": 12,
                "entity_pools": [
                    {
                        "name": "customers",
                        "count": 3,
                        "id_prefix": "customer",
                        "attributes": [
                            {
                                "name": "customer_region",
                                "generator": {
                                    "kind": "categorical",
                                    "values": ["west", "south", "northeast"],
                                },
                            },
                            {
                                "name": "loyalty_tier",
                                "generator": {
                                    "kind": "categorical",
                                    "values": ["standard", "gold"],
                                    "weights": [0.8, 0.2],
                                },
                            },
                        ],
                    }
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
                        "name": "amount",
                        "generator": {
                            "kind": "distribution",
                            "distribution": "lognormal",
                            "parameters": {"mean": 3.5, "stddev": 0.3},
                        },
                    },
                ],
            }
        )

        payload = generate_scenario(request)
        entity_values: dict[str, tuple[str, str]] = {}

        self.assertEqual(payload["scenario_name"], "entity_generate")
        self.assertEqual(payload["row_count"], 12)
        self.assertIn("customer_id", payload["fields"])

        for row in payload["rows"]:
            entity_key = row["customer_id"]
            entity_attributes = (row["customer_region"], row["loyalty_tier"])
            if entity_key in entity_values:
                self.assertEqual(entity_values[entity_key], entity_attributes)
            else:
                entity_values[entity_key] = entity_attributes

        self.assertLess(len(entity_values), payload["row_count"])

    def test_generate_scenario_entity_output_is_deterministic_for_seed(self):
        request = ScenarioGenerateRequest.model_validate(
            {
                "name": "deterministic_entity_generate",
                "seed": 31,
                "row_count": 10,
                "entity_pools": [
                    {
                        "name": "devices",
                        "count": 4,
                        "attributes": [
                            {
                                "name": "site_id",
                                "generator": {
                                    "kind": "categorical",
                                    "values": ["site_001", "site_002"],
                                },
                            }
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
                ],
            }
        )

        first = generate_scenario(request)
        second = generate_scenario(request)

        self.assertEqual(first, second)

    def test_generate_scenario_supports_contextual_distribution(self):
        request = ScenarioGenerateRequest.model_validate(
            {
                "name": "contextual_generate",
                "seed": 41,
                "row_count": 4,
                "entity_pools": [
                    {
                        "name": "customers",
                        "count": 1,
                        "attributes": [
                            {
                                "name": "spend_bias",
                                "generator": {
                                    "kind": "constant",
                                    "value": 2.0,
                                },
                            },
                            {
                                "name": "customer_segment",
                                "generator": {
                                    "kind": "constant",
                                    "value": "vip",
                                },
                            },
                        ],
                    }
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
                        "name": "customer_segment",
                        "generator": {
                            "kind": "entity_attribute",
                            "entity_name": "customers",
                            "attribute": "customer_segment",
                        },
                    },
                    {
                        "name": "amount",
                        "generator": {
                            "kind": "contextual_distribution",
                            "distribution": "normal",
                            "parameters": {"mean": 10.0, "stddev": 0.0},
                            "parameter_modifiers": [
                                {
                                    "parameter": "mean",
                                    "operation": "add",
                                    "entity_name": "customers",
                                    "entity_attribute": "spend_bias",
                                },
                                {
                                    "parameter": "mean",
                                    "operation": "add",
                                    "value": 3.0,
                                    "when": [{"field": "customer_segment", "equals": "vip"}],
                                },
                            ],
                        },
                    },
                ],
            }
        )

        payload = generate_scenario(request)

        self.assertEqual([row["amount"] for row in payload["rows"]], [15.0, 15.0, 15.0, 15.0])

    def test_generate_scenario_supports_process_modifiers(self):
        request = ScenarioGenerateRequest.model_validate(
            {
                "name": "process_modifier_generate",
                "seed": 43,
                "row_count": 5,
                "fields": [
                    {
                        "name": "value",
                        "generator": {
                            "kind": "distribution",
                            "distribution": "normal",
                            "parameters": {"mean": 10.0, "stddev": 0.0},
                        },
                    }
                ],
                "process_modifiers": [
                    {
                        "modifier_id": "regime_shift",
                        "field": "value",
                        "selection": {
                            "kind": "window",
                            "start_index": 2,
                        },
                        "parameter_modifiers": [
                            {
                                "parameter": "mean",
                                "operation": "add",
                                "value": 5.0,
                            }
                        ],
                    }
                ],
            }
        )

        payload = generate_scenario(request)

        self.assertEqual([row["value"] for row in payload["rows"]], [10.0, 10.0, 15.0, 15.0, 15.0])
        label = payload["rows"][2]["__labels"][0]
        self.assertEqual(label["label_source"], "process_modifier")
        self.assertEqual(label["modifier_id"], "regime_shift")
        self.assertEqual(label["generated_value"], 15.0)

    def test_generate_scenario_supports_scoped_mutations(self):
        request = ScenarioGenerateRequest.model_validate(
            {
                "name": "scoped_mutations",
                "seed": 43,
                "row_count": 6,
                "fields": [
                    {
                        "name": "segment",
                        "generator": {
                            "kind": "categorical",
                            "values": ["target", "other"],
                            "weights": [0.5, 0.5],
                        },
                    },
                    {
                        "name": "value",
                        "generator": {
                            "kind": "distribution",
                            "distribution": "normal",
                            "parameters": {"mean": 5.0, "stddev": 0.0},
                        },
                    },
                ],
                "mutations": [
                    {
                        "mutation_id": "target_only",
                        "field": "value",
                        "scope": [{"field": "segment", "equals": "target"}],
                        "selection": {
                            "kind": "count",
                            "count": 1,
                        },
                        "mutation": {
                            "kind": "offset",
                            "amount": 5.0,
                        },
                    }
                ],
            }
        )

        payload = generate_scenario(request)

        targeted_rows = [row for row in payload["rows"] if row["segment"] == "target" and row["__is_anomaly"]]
        non_targeted_rows = [row for row in payload["rows"] if row["segment"] != "target" and row["__is_anomaly"]]

        self.assertEqual(len(targeted_rows), 1)
        self.assertEqual(len(non_targeted_rows), 0)

    def test_scenario_rejects_unknown_entity_reference(self):
        with self.assertRaisesRegex(ValueError, "unknown entity pool"):
            ScenarioGenerateRequest.model_validate(
                {
                    "name": "bad_entity_generate",
                    "seed": 13,
                    "row_count": 2,
                    "fields": [
                        {
                            "name": "customer_id",
                            "generator": {
                                "kind": "entity_id",
                                "entity_name": "customers",
                            },
                        }
                    ],
                }
            )

    def test_generate_scenario_rejects_count_selection_above_row_count(self):
        request = ScenarioGenerateRequest.model_validate(
            {
                "name": "bad_count_generate",
                "seed": 23,
                "row_count": 2,
                "fields": [
                    {
                        "name": "value",
                        "generator": {
                            "kind": "distribution",
                            "distribution": "normal",
                            "parameters": {"mean": 10.0, "stddev": 1.0},
                        },
                    }
                ],
                "mutations": [
                    {
                        "mutation_id": "too_many",
                        "field": "value",
                        "selection": {
                            "kind": "count",
                            "count": 3,
                        },
                        "mutation": {
                            "kind": "scale",
                            "factor": 2.0,
                        },
                    }
                ],
            }
        )

        with self.assertRaisesRegex(ValueError, "eligible_row_count=2"):
            generate_scenario(request)

    def test_generate_scenario_explains_empty_scoped_count_selection(self):
        request = ScenarioGenerateRequest.model_validate(
            {
                "name": "empty_scope_generate",
                "seed": 23,
                "row_count": 6,
                "entity_pools": [
                    {
                        "name": "customers",
                        "count": 2,
                        "id_prefix": "customer",
                        "attributes": [
                            {
                                "name": "segment",
                                "generator": {
                                    "kind": "categorical",
                                    "values": ["standard"],
                                },
                            }
                        ],
                    }
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
                        "name": "segment",
                        "generator": {
                            "kind": "entity_attribute",
                            "entity_name": "customers",
                            "attribute": "segment",
                        },
                    },
                    {
                        "name": "amount",
                        "generator": {
                            "kind": "distribution",
                            "distribution": "normal",
                            "parameters": {"mean": 10.0, "stddev": 0.0},
                        },
                    },
                ],
                "mutations": [
                    {
                        "mutation_id": "premium_spike",
                        "field": "amount",
                        "scope": [{"field": "segment", "equals": "premium"}],
                        "selection": {
                            "kind": "count",
                            "count": 1,
                        },
                        "mutation": {
                            "kind": "scale",
                            "factor": 2.0,
                        },
                    }
                ],
            }
        )

        with self.assertRaisesRegex(ValueError, "Try changing the seed"):
            generate_scenario(request)

    def test_sample_scenario_supports_sample_compatible_mutations(self):
        request = ScenarioSampleRequest.model_validate(
            {
                "name": "sample_once",
                "seed": 5,
                "fields": [
                    {
                        "name": "value",
                        "generator": {
                            "kind": "distribution",
                            "distribution": "normal",
                            "parameters": {"mean": 7.0, "stddev": 1.0},
                        },
                    }
                ],
                "mutations": [
                    {
                        "mutation_id": "always_scale",
                        "field": "value",
                        "selection": {
                            "kind": "rate",
                            "rate": 1.0,
                        },
                        "mutation": {
                            "kind": "scale",
                            "factor": 2.0,
                        },
                    }
                ],
            }
        )

        payload = sample_scenario(request)

        self.assertEqual(payload["scenario_name"], "sample_once")
        self.assertTrue(payload["row"]["__is_anomaly"])
        self.assertEqual(payload["row"]["__labels"][0]["mutation_id"], "always_scale")

    def test_sample_scenario_supports_count_selection(self):
        request = ScenarioSampleRequest.model_validate(
            {
                "name": "count_sample",
                "seed": 5,
                "fields": [
                    {
                        "name": "value",
                        "generator": {
                            "kind": "distribution",
                            "distribution": "normal",
                            "parameters": {"mean": 7.0, "stddev": 1.0},
                        },
                    }
                ],
                "mutations": [
                    {
                        "mutation_id": "single_pick",
                        "field": "value",
                        "selection": {
                            "kind": "count",
                            "count": 1,
                        },
                        "mutation": {
                            "kind": "scale",
                            "factor": 2.0,
                        },
                    }
                ],
            }
        )

        payload = sample_scenario(request)

        self.assertTrue(payload["row"]["__is_anomaly"])
        self.assertEqual(payload["row"]["__labels"][0]["selection_kind"], "count")

    def test_sample_scenario_is_deterministic_for_seed(self):
        request = ScenarioSampleRequest.model_validate(
            {
                "name": "deterministic_sample",
                "seed": 5,
                "process_modifiers": [
                    {
                        "modifier_id": "single_shift",
                        "field": "value",
                        "selection": {
                            "kind": "count",
                            "count": 1,
                        },
                        "parameter_modifiers": [
                            {
                                "parameter": "mean",
                                "operation": "set",
                                "value": 14.0,
                            }
                        ],
                    }
                ],
                "fields": [
                    {
                        "name": "value",
                        "generator": {
                            "kind": "distribution",
                            "distribution": "normal",
                            "parameters": {"mean": 7.0, "stddev": 1.0},
                        },
                    }
                ],
                "mutations": [
                    {
                        "mutation_id": "single_pick",
                        "field": "value",
                        "selection": {
                            "kind": "count",
                            "count": 1,
                        },
                        "mutation": {
                            "kind": "scale",
                            "min_factor": 1.5,
                            "max_factor": 2.0,
                        },
                    }
                ],
            }
        )

        first = sample_scenario(request)
        second = sample_scenario(request)

        self.assertEqual(first, second)

    def test_sample_scenario_rejects_count_selection_above_row_count(self):
        request = ScenarioSampleRequest.model_validate(
            {
                "name": "bad_count_sample",
                "seed": 5,
                "fields": [
                    {
                        "name": "value",
                        "generator": {
                            "kind": "distribution",
                            "distribution": "normal",
                            "parameters": {"mean": 7.0, "stddev": 1.0},
                        },
                    }
                ],
                "mutations": [
                    {
                        "mutation_id": "too_many",
                        "field": "value",
                        "selection": {
                            "kind": "count",
                            "count": 2,
                        },
                        "mutation": {
                            "kind": "scale",
                            "factor": 2.0,
                        },
                    }
                ],
            }
        )

        with self.assertRaisesRegex(ValueError, "eligible_row_count=1"):
            sample_scenario(request)

    def test_sample_scenario_rejects_stateful_selectors(self):
        request = ScenarioSampleRequest.model_validate(
            {
                "name": "invalid_sample",
                "seed": 5,
                "fields": [
                    {
                        "name": "value",
                        "generator": {
                            "kind": "distribution",
                            "distribution": "normal",
                            "parameters": {"mean": 7.0, "stddev": 1.0},
                        },
                    }
                ],
                "mutations": [
                    {
                        "mutation_id": "indexed_spike",
                        "field": "value",
                        "selection": {
                            "kind": "index",
                            "index": 0,
                        },
                        "mutation": {
                            "kind": "scale",
                            "factor": 2.0,
                        },
                    }
                ],
            }
        )

        with self.assertRaisesRegex(ValueError, "sample-compatible mutations"):
            sample_scenario(request)

    def test_sample_scenario_rejects_non_sample_compatible_process_modifiers(self):
        request = ScenarioSampleRequest.model_validate(
            {
                "name": "invalid_process_modifier_sample",
                "seed": 5,
                "fields": [
                    {
                        "name": "value",
                        "generator": {
                            "kind": "distribution",
                            "distribution": "normal",
                            "parameters": {"mean": 7.0, "stddev": 1.0},
                        },
                    }
                ],
                "process_modifiers": [
                    {
                        "modifier_id": "window_shift",
                        "field": "value",
                        "selection": {
                            "kind": "window",
                            "start_index": 0,
                            "end_index": 1,
                        },
                        "parameter_modifiers": [
                            {
                                "parameter": "mean",
                                "operation": "add",
                                "value": 2.0,
                            }
                        ],
                    }
                ],
            }
        )

        with self.assertRaisesRegex(ValueError, "sample-compatible process modifiers"):
            sample_scenario(request)

    def test_generate_scenario_supports_ranged_mutations(self):
        request = ScenarioGenerateRequest.model_validate(
            {
                "name": "range_generate",
                "seed": 41,
                "row_count": 4,
                "fields": [
                    {
                        "name": "value",
                        "generator": {
                            "kind": "distribution",
                            "distribution": "normal",
                            "parameters": {"mean": 10.0, "stddev": 1.0},
                        },
                    }
                ],
                "mutations": [
                    {
                        "mutation_id": "ranged_offset",
                        "field": "value",
                        "selection": {
                            "kind": "count",
                            "count": 2,
                        },
                        "mutation": {
                            "kind": "offset",
                            "min_amount": 3.0,
                            "max_amount": 5.0,
                        },
                    }
                ],
            }
        )

        payload = generate_scenario(request)
        labeled_rows = [row for row in payload["rows"] if row["__is_anomaly"]]

        self.assertEqual(len(labeled_rows), 2)
        for row in labeled_rows:
            label = row["__labels"][0]
            applied_amount = label["applied_mutation"]["amount"]
            self.assertGreaterEqual(applied_amount, 3.0)
            self.assertLessEqual(applied_amount, 5.0)
            self.assertAlmostEqual(label["mutated_value"] - label["original_value"], applied_amount)

    def test_preset_generate_builds_rows(self):
        request = build_preset_generate_request(
            "transaction_benchmark",
            PresetGenerateRequest(seed=3, row_count=12, overrides={}),
        )

        payload = generate_scenario(request)

        self.assertEqual(payload["scenario_name"], "transaction_benchmark")
        self.assertEqual(payload["row_count"], 12)
        self.assertIn("amount", payload["fields"])
        self.assertIn("card_id", payload["fields"])
        self.assertIn("merchant_id", payload["fields"])
        self.assertIn("merchant_category", payload["fields"])

    def test_preset_generate_is_deterministic_for_seed(self):
        request = build_preset_generate_request(
            "transaction_benchmark",
            PresetGenerateRequest(seed=3, row_count=12, overrides={}),
        )

        first = generate_scenario(request)
        second = generate_scenario(request)

        self.assertEqual(first, second)

    def test_generate_scenario_supports_sequence_fields(self):
        request = ScenarioGenerateRequest.model_validate(
            {
                "name": "sequence_generate",
                "seed": 13,
                "row_count": 4,
                "fields": [
                    {
                        "name": "customer_id",
                        "generator": {
                            "kind": "sequence",
                            "start": 1000,
                            "step": 5,
                        },
                    }
                ],
            }
        )

        payload = generate_scenario(request)

        self.assertEqual([row["customer_id"] for row in payload["rows"]], [1000, 1005, 1010, 1015])

    def test_iot_preset_includes_device_dimensions(self):
        request = build_preset_generate_request(
            "iot_sensor_benchmark",
            PresetGenerateRequest(seed=5, row_count=8, overrides={}),
        )

        payload = generate_scenario(request)

        self.assertIn("device_id", payload["fields"])
        self.assertIn("site_id", payload["fields"])
        self.assertIn("device_type", payload["fields"])

    def test_order_preset_generate_builds_rows(self):
        request = build_preset_generate_request(
            "order_benchmark",
            PresetGenerateRequest(seed=7, row_count=10, overrides={}),
        )

        payload = generate_scenario(request)

        self.assertEqual(payload["scenario_name"], "order_benchmark")
        self.assertEqual(payload["row_count"], 10)
        self.assertIn("customer_id", payload["fields"])
        self.assertIn("product_id", payload["fields"])
        self.assertIn("order_amount", payload["fields"])

    def test_batch_delivery_preset_models_one_batch_drop(self):
        request = build_preset_generate_request(
            "batch_delivery_benchmark",
            PresetGenerateRequest(
                seed=19,
                row_count=6,
                overrides={
                    "source_system_id": "hospital_system_a",
                    "delivery_id": "hospital_system_a_20260312",
                    "delivery_date": "2026-03-12",
                },
            ),
        )

        payload = generate_scenario(request)

        self.assertEqual(payload["scenario_name"], "batch_delivery_benchmark")
        self.assertEqual(payload["row_count"], 6)
        self.assertIn("source_system_id", payload["fields"])
        self.assertIn("delivery_id", payload["fields"])
        self.assertIn("record_number", payload["fields"])
        self.assertIn("member_id", payload["fields"])
        self.assertIn("facility_id", payload["fields"])
        self.assertIn("allowed_amount", payload["fields"])
        self.assertEqual(
            {row["source_system_id"] for row in payload["rows"]},
            {"hospital_system_a"},
        )
        self.assertEqual(
            {row["delivery_id"] for row in payload["rows"]},
            {"hospital_system_a_20260312"},
        )
        self.assertEqual(
            [row["record_number"] for row in payload["rows"]],
            [1, 2, 3, 4, 5, 6],
        )

    def test_transaction_preset_supports_sample(self):
        request = build_preset_sample_request(
            "transaction_benchmark",
            PresetSampleRequest(seed=17, overrides={}),
        )

        payload = sample_scenario(request)

        self.assertEqual(payload["scenario_name"], "transaction_benchmark")
        self.assertIn("row", payload)
        self.assertIn("card_id", payload["row"])
        self.assertIn("merchant_id", payload["row"])

    def test_batch_delivery_preset_rejects_sample(self):
        with self.assertRaisesRegex(ValueError, "does not support /sample"):
            build_preset_sample_request(
                "batch_delivery_benchmark",
                PresetSampleRequest(seed=17, overrides={}),
            )

    def test_list_presets_exposes_sample_support(self):
        presets = {preset["preset_id"]: preset for preset in list_presets()}

        self.assertFalse(presets["batch_delivery_benchmark"]["supports_sample"])
        self.assertTrue(presets["transaction_benchmark"]["supports_sample"])

    def test_handler_routes_scenario_generate(self):
        event = {
            "action": "/v1/scenarios/generate",
            "name": "handler_generate",
            "seed": 9,
            "row_count": 3,
            "fields": [
                {
                    "name": "status",
                    "generator": {
                        "kind": "categorical",
                        "values": ["ok", "warn"],
                        "weights": [0.8, 0.2],
                    },
                }
            ],
        }

        response = handle_request(event)
        payload = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(payload["scenario_name"], "handler_generate")
        self.assertEqual(len(payload["rows"]), 3)

    def test_handler_routes_scenario_sample(self):
        event = {
            "action": "/v1/scenarios/sample",
            "name": "handler_sample",
            "seed": 9,
            "fields": [
                {
                    "name": "status",
                    "generator": {
                        "kind": "categorical",
                        "values": ["ok", "warn"],
                        "weights": [0.8, 0.2],
                    },
                }
            ],
        }

        response = handle_request(event)
        payload = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(payload["scenario_name"], "handler_sample")
        self.assertIn("row", payload)

    def test_handler_rejects_stateful_scenario_sample(self):
        event = {
            "action": "/v1/scenarios/sample",
            "name": "bad_sample",
            "seed": 9,
            "fields": [
                {
                    "name": "value",
                    "generator": {
                        "kind": "distribution",
                        "distribution": "normal",
                        "parameters": {"mean": 1.0, "stddev": 0.5},
                    },
                }
            ],
            "mutations": [
                {
                    "mutation_id": "indexed_spike",
                    "field": "value",
                    "selection": {
                        "kind": "index",
                        "index": 0,
                    },
                    "mutation": {
                        "kind": "scale",
                        "factor": 4.0,
                    },
                }
            ],
        }

        response = handle_request(event)
        payload = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(payload["error"], "bad_request")

    def test_handler_returns_validation_summary_for_invalid_request(self):
        event = {
            "action": "/v1/scenarios/generate",
            "name": "invalid_request",
            "row_count": 2,
            "fields": [
                {
                    "name": "value",
                    "generator": {
                        "kind": "distribution",
                        "distribution": "normal",
                        "parameters": {"mean": 1.0, "stddev": 0.5},
                    },
                },
                {
                    "name": "value",
                    "generator": {
                        "kind": "distribution",
                        "distribution": "normal",
                        "parameters": {"mean": 2.0, "stddev": 0.5},
                    },
                },
            ],
        }

        response = handle_request(event)
        payload = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(payload["error"], "validation_error")
        self.assertIn("field names must be unique", payload["message"])
        self.assertIn("details", payload)

    def test_handler_returns_json_error_for_invalid_body(self):
        event = {
            "rawPath": "/v1/scenarios/generate",
            "httpMethod": "POST",
            "body": '{"name":"bad_json"',
        }

        response = handle_request(event)
        payload = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(payload["error"], "bad_request")
        self.assertIn("request body must be valid JSON", payload["message"])

    def test_handler_routes_distribution_generate(self):
        event = {
            "action": "/v1/distributions/generate",
            "distribution": "uniform",
            "parameters": {"low": 1.0, "high": 2.0},
            "count": 4,
            "summary": True,
            "seed": 2,
        }

        response = handle_request(event)
        payload = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(payload["count"], 4)
        self.assertIn("summary", payload)

    def test_handler_routes_distribution_generate_over_http(self):
        event = {
            "rawPath": "/v1/distributions/generate",
            "httpMethod": "POST",
            "body": json.dumps(
                {
                    "distribution": "uniform",
                    "parameters": {"low": 1.0, "high": 2.0},
                    "count": 4,
                    "summary": True,
                    "seed": 2,
                }
            ),
        }

        response = handle_request(event)
        payload = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(payload["count"], 4)
        self.assertIn("summary", payload)

    def test_handler_routes_preset_generate(self):
        event = {
            "action": "/v1/presets/iot_sensor_benchmark/generate",
            "seed": 5,
            "row_count": 8,
        }

        response = handle_request(event)
        payload = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(payload["scenario_name"], "iot_sensor_benchmark")
        self.assertEqual(len(payload["rows"]), 8)

    def test_handler_routes_preset_sample(self):
        event = {
            "rawPath": "/v1/presets/transaction_benchmark/sample",
            "httpMethod": "POST",
            "body": json.dumps(
                {
                    "seed": 5,
                }
            ),
        }

        response = handle_request(event)
        payload = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(payload["scenario_name"], "transaction_benchmark")
        self.assertIn("row", payload)

    def test_handler_rejects_unsupported_preset_sample(self):
        event = {
            "rawPath": "/v1/presets/batch_delivery_benchmark/sample",
            "httpMethod": "POST",
            "body": json.dumps(
                {
                    "seed": 5,
                }
            ),
        }

        response = handle_request(event)
        payload = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(payload["error"], "bad_request")
        self.assertIn("does not support /sample", payload["message"])

    def test_handler_routes_presets_list_over_http(self):
        event = {
            "rawPath": "/v1/presets",
            "httpMethod": "GET",
        }

        response = handle_request(event)
        payload = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertIn("presets", payload)

    def test_handler_allows_get_health_for_http_requests(self):
        event = {
            "rawPath": "/health",
            "httpMethod": "GET",
        }

        response = handle_request(event)
        payload = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(payload["status"], "ok")

    def test_handler_rejects_wrong_http_method(self):
        event = {
            "rawPath": "/v1/distributions/generate",
            "httpMethod": "GET",
        }

        response = handle_request(event)
        payload = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 405)
        self.assertEqual(payload["error"], "method_not_allowed")
        self.assertEqual(response["headers"]["Allow"], "POST")


if __name__ == "__main__":
    unittest.main()
