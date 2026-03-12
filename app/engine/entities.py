from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from app.api.models import EntityAttributeGeneratorSpec, EntityIdGeneratorSpec, EntityPoolSpec
from app.engine.generators import generate_primitive_values
from app.engine.randomness import build_rng


@dataclass(frozen=True)
class EntityPoolContext:
    ids: list[str]
    row_entity_indexes: list[int]
    attribute_values: dict[str, list[Any]]


@dataclass(frozen=True)
class EntityContext:
    pools: dict[str, EntityPoolContext]


def _build_entity_ids(pool: EntityPoolSpec) -> list[str]:
    prefix = pool.id_prefix or pool.name
    return [f"{prefix}_{index:04d}" for index in range(1, pool.count + 1)]


def _build_row_entity_indexes(
    entity_count: int,
    row_count: int,
    rng: np.random.Generator,
) -> list[int]:
    if entity_count == 1:
        return [0 for _ in range(row_count)]

    if row_count <= entity_count:
        return rng.choice(entity_count, size=row_count, replace=False).tolist()

    repeats, remainder = divmod(row_count, entity_count)
    base_indexes = np.tile(np.arange(entity_count), repeats)

    if remainder:
        remainder_indexes = rng.choice(entity_count, size=remainder, replace=False)
        all_indexes = np.concatenate((base_indexes, remainder_indexes))
    else:
        all_indexes = base_indexes

    rng.shuffle(all_indexes)
    return all_indexes.tolist()


def build_entity_context(
    entity_pools: list[EntityPoolSpec],
    row_count: int,
    scenario_seed: int | None,
) -> EntityContext:
    pools: dict[str, EntityPoolContext] = {}

    for pool in entity_pools:
        row_assignment_rng = build_rng(scenario_seed, "entity_pool", pool.name, "rows")
        row_entity_indexes = _build_row_entity_indexes(pool.count, row_count, row_assignment_rng)

        attribute_values = {
            attribute.name: generate_primitive_values(
                attribute.generator,
                pool.count,
                scenario_seed,
                "entity_pool",
                pool.name,
                "attribute",
                attribute.name,
            )
            for attribute in pool.attributes
        }

        pools[pool.name] = EntityPoolContext(
            ids=_build_entity_ids(pool),
            row_entity_indexes=row_entity_indexes,
            attribute_values=attribute_values,
        )

    return EntityContext(pools=pools)


def generate_entity_values(
    generator: EntityIdGeneratorSpec | EntityAttributeGeneratorSpec,
    row_count: int,
    entity_context: EntityContext,
) -> list[Any]:
    pool = entity_context.pools[generator.entity_name]
    entity_indexes = pool.row_entity_indexes[:row_count]

    if generator.kind == "entity_id":
        return [pool.ids[index] for index in entity_indexes]

    if generator.kind == "entity_attribute":
        values = pool.attribute_values[generator.attribute]
        return [values[index] for index in entity_indexes]

    raise ValueError(f"unsupported entity generator kind: {generator.kind}")
