import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.api.models import PresetGenerateRequest, ScenarioGenerateRequest, ScenarioSampleRequest
from app.api.router import handle_request
from app.engine.presets import build_preset_generate_request
from app.engine.scenario import generate_scenario, sample_scenario


class ScenarioEngineTest(unittest.TestCase):
    def test_generate_scenario_applies_labels(self):
        request = ScenarioGenerateRequest.model_validate(
            {
                "name": "simple_generate",
                "seed": 11,
                "row_count": 6,
                "time": {"frequency_seconds": 60},
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
                "injectors": [
                    {
                        "injector_id": "spike_1",
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
        self.assertEqual(payload["rows"][2]["__labels"][0]["injector_id"], "spike_1")
        self.assertEqual(payload["rows"][2]["__labels"][0]["selection_kind"], "index")

    def test_generate_scenario_supports_rate_based_injectors(self):
        request = ScenarioGenerateRequest.model_validate(
            {
                "name": "rate_generate",
                "seed": 17,
                "row_count": 50,
                "time": {"frequency_seconds": 60},
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
                "injectors": [
                    {
                        "injector_id": "random_spikes",
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

    def test_sample_scenario_supports_stateless_injectors(self):
        request = ScenarioSampleRequest.model_validate(
            {
                "name": "sample_once",
                "seed": 5,
                "time": {"frequency_seconds": 60},
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
                "injectors": [
                    {
                        "injector_id": "always_scale",
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
        self.assertEqual(payload["row"]["__labels"][0]["injector_id"], "always_scale")

    def test_sample_scenario_rejects_stateful_selectors(self):
        request = ScenarioSampleRequest.model_validate(
            {
                "name": "invalid_sample",
                "seed": 5,
                "time": {"frequency_seconds": 60},
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
                "injectors": [
                    {
                        "injector_id": "indexed_spike",
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

        with self.assertRaisesRegex(ValueError, "stateless injectors"):
            sample_scenario(request)

    def test_preset_generate_builds_rows(self):
        request = build_preset_generate_request(
            "transaction_benchmark",
            PresetGenerateRequest(seed=3, row_count=12, overrides={}),
        )

        payload = generate_scenario(request)

        self.assertEqual(payload["scenario_name"], "transaction_benchmark")
        self.assertEqual(payload["row_count"], 12)
        self.assertIn("amount", payload["fields"])

    def test_handler_routes_scenario_generate(self):
        event = {
            "action": "/v1/scenarios/generate",
            "name": "handler_generate",
            "seed": 9,
            "row_count": 3,
            "time": {"frequency_seconds": 60},
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
            "time": {"frequency_seconds": 60},
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
            "time": {"frequency_seconds": 60},
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
            "injectors": [
                {
                    "injector_id": "indexed_spike",
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


if __name__ == "__main__":
    unittest.main()
