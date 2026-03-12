from __future__ import annotations

from typing import Any

from app.api.models import (
    CategoricalGeneratorSpec,
    ConstantGeneratorSpec,
    DistributionGeneratorSpec,
)
from app.engine.distributions import sample_distribution
from app.engine.randomness import derive_seed


PrimitiveGenerator = DistributionGeneratorSpec | ConstantGeneratorSpec | CategoricalGeneratorSpec


def generate_primitive_values(
    generator: PrimitiveGenerator,
    row_count: int,
    scenario_seed: int | None,
    *seed_parts: Any,
) -> list[Any]:
    generator_seed = derive_seed(scenario_seed, *seed_parts)

    if generator.kind == "constant":
        return [generator.value for _ in range(row_count)]

    if generator.kind == "categorical":
        return sample_distribution(
            distribution="categorical",
            parameters={"values": generator.values, "weights": generator.weights},
            count=row_count,
            seed=generator_seed,
        )

    if generator.kind == "distribution":
        return sample_distribution(
            distribution=generator.distribution,
            parameters=generator.parameters,
            count=row_count,
            seed=generator_seed,
        )

    raise ValueError(f"unsupported primitive generator kind: {generator.kind}")
