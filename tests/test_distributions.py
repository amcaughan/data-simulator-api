import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.api.models import DistributionGenerateRequest, DistributionSampleRequest
from app.engine.distributions import build_distribution_generate_response, build_distribution_sample_response


class DistributionEngineTest(unittest.TestCase):
    def test_normal_distribution_generate_response_is_deterministic(self):
        request = DistributionGenerateRequest(
            distribution="normal",
            parameters={"mean": 10.0, "stddev": 2.0},
            count=3,
            seed=42,
            summary=True,
        )

        payload = build_distribution_generate_response(request)

        self.assertEqual(payload["distribution"], "normal")
        self.assertEqual(payload["count"], 3)
        self.assertEqual(payload["seed"], 42)
        self.assertEqual(len(payload["samples"]), 3)
        self.assertIn("summary", payload)
        self.assertIn("mean", payload["summary"])

    def test_categorical_distribution_generate_returns_requested_values(self):
        request = DistributionGenerateRequest(
            distribution="categorical",
            parameters={"values": ["a", "b"], "weights": [0.75, 0.25]},
            count=10,
            seed=7,
            summary=True,
        )

        payload = build_distribution_generate_response(request)

        self.assertTrue(all(value in {"a", "b"} for value in payload["samples"]))
        self.assertIn("value_counts", payload["summary"])

    def test_distribution_sample_returns_single_value(self):
        request = DistributionSampleRequest(
            distribution="poisson",
            parameters={"rate": 4.0},
            seed=9,
        )

        payload = build_distribution_sample_response(request)

        self.assertEqual(payload["distribution"], "poisson")
        self.assertEqual(payload["seed"], 9)
        self.assertIn("sample", payload)
        self.assertNotIn("samples", payload)


if __name__ == "__main__":
    unittest.main()
