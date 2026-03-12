from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.api.models import MutationSpec, OffsetMutationSpec, RowMutationSpec, ScaleMutationSpec
from app.engine.labels import add_label
from app.engine.randomness import build_rng
from app.engine.selectors import select_row_indexes, selection_is_sample_compatible


@dataclass(frozen=True)
class MutationBehavior:
    apply: Callable[[dict[str, Any], str, MutationSpec, np.random.Generator], dict[str, Any]]


def _resolve_offset_amount(mutation: OffsetMutationSpec, rng: np.random.Generator) -> float:
    if mutation.amount is not None:
        return mutation.amount
    return float(rng.uniform(mutation.min_amount, mutation.max_amount))


def _resolve_scale_factor(mutation: ScaleMutationSpec, rng: np.random.Generator) -> float:
    if mutation.factor is not None:
        return mutation.factor
    return float(rng.uniform(mutation.min_factor, mutation.max_factor))


def _apply_offset(row: dict[str, Any], field: str, mutation: MutationSpec, rng: np.random.Generator) -> dict[str, Any]:
    original_value = row[field]
    amount = _resolve_offset_amount(mutation, rng)
    mutated_value = original_value + amount
    row[field] = mutated_value
    return {
        "original_value": original_value,
        "mutated_value": mutated_value,
        "applied_mutation": {
            "kind": mutation.kind,
            "amount": amount,
        },
    }


def _apply_scale(row: dict[str, Any], field: str, mutation: MutationSpec, rng: np.random.Generator) -> dict[str, Any]:
    original_value = row[field]
    factor = _resolve_scale_factor(mutation, rng)
    mutated_value = original_value * factor
    row[field] = mutated_value
    return {
        "original_value": original_value,
        "mutated_value": mutated_value,
        "applied_mutation": {
            "kind": mutation.kind,
            "factor": factor,
            "percent_change": factor - 1.0,
        },
    }


def _apply_set_value(row: dict[str, Any], field: str, mutation: MutationSpec, rng: np.random.Generator) -> dict[str, Any]:
    original_value = row[field]
    mutated_value = mutation.value
    row[field] = mutated_value
    return {
        "original_value": original_value,
        "mutated_value": mutated_value,
        "applied_mutation": {
            "kind": mutation.kind,
            "value": mutation.value,
        },
    }


def _apply_set_missing(row: dict[str, Any], field: str, mutation: MutationSpec, rng: np.random.Generator) -> dict[str, Any]:
    original_value = row[field]
    row[field] = None
    return {
        "original_value": original_value,
        "mutated_value": None,
        "applied_mutation": {
            "kind": mutation.kind,
        },
    }


MUTATION_BEHAVIORS: dict[str, MutationBehavior] = {
    "offset": MutationBehavior(apply=_apply_offset),
    "scale": MutationBehavior(apply=_apply_scale),
    "set_missing": MutationBehavior(apply=_apply_set_missing),
    "set_value": MutationBehavior(apply=_apply_set_value),
}


def mutation_is_sample_compatible(row_mutation: RowMutationSpec) -> bool:
    return selection_is_sample_compatible(row_mutation.selection)


def validate_sample_compatible_mutations(mutations: Sequence[RowMutationSpec]) -> None:
    incompatible_ids = [
        row_mutation.mutation_id
        for row_mutation in mutations
        if not mutation_is_sample_compatible(row_mutation)
    ]

    if incompatible_ids:
        ids = ", ".join(incompatible_ids)
        raise ValueError(
            "scenario sample only supports sample-compatible mutations; "
            f"invalid mutations: {ids}"
        )


def _validate_field(rows: Sequence[dict[str, Any]], field: str) -> None:
    if rows and field not in rows[0]:
        raise ValueError(f"mutation references unknown field: {field}")


def _tag_row(row: dict[str, Any], row_mutation: RowMutationSpec, mutation_result: dict[str, Any]) -> None:
    add_label(
        row,
        {
            "label_source": "mutation",
            "anomaly_type": row_mutation.mutation.kind,
            "mutation_id": row_mutation.mutation_id,
            "field": row_mutation.field,
            "selection_kind": row_mutation.selection.kind,
            "severity": row_mutation.severity,
            "original_value": mutation_result["original_value"],
            "mutated_value": mutation_result["mutated_value"],
            "applied_mutation": mutation_result["applied_mutation"],
        },
    )


def apply_mutations(
    rows: Sequence[dict[str, Any]],
    mutations: Sequence[RowMutationSpec],
    scenario_seed: int | None,
) -> None:
    for row_mutation in mutations:
        _validate_field(rows, row_mutation.field)
        mutation_behavior = MUTATION_BEHAVIORS[row_mutation.mutation.kind]

        indexes = select_row_indexes(
            rows,
            row_mutation.scope,
            row_mutation.selection,
            scenario_seed,
            "mutation",
            row_mutation.mutation_id,
            row_mutation.field,
        )

        for index in indexes:
            mutation_rng = build_rng(scenario_seed, "mutation", row_mutation.mutation_id, "row", index)
            mutation_result = mutation_behavior.apply(rows[index], row_mutation.field, row_mutation.mutation, mutation_rng)
            _tag_row(rows[index], row_mutation, mutation_result)
