from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.api.models import InjectorSpec, MutationSpec, OffsetMutationSpec, ScaleMutationSpec, SelectionSpec


LABELS_KEY = "__labels"
IS_ANOMALY_KEY = "__is_anomaly"


@dataclass(frozen=True)
class SelectionBehavior:
    stateless: bool
    select_indexes: Callable[[int, SelectionSpec, np.random.Generator], list[int]]


@dataclass(frozen=True)
class MutationBehavior:
    stateless: bool
    apply: Callable[[dict[str, Any], str, MutationSpec, np.random.Generator], dict[str, Any]]


def initialize_labels(rows: Sequence[dict[str, Any]]) -> None:
    for row in rows:
        row[IS_ANOMALY_KEY] = False
        row[LABELS_KEY] = []


def summarize_labels(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    total_anomalous_rows = 0
    anomaly_counts: dict[str, int] = {}

    for row in rows:
        labels = row.get(LABELS_KEY, [])
        if labels:
            total_anomalous_rows += 1
        for label in labels:
            anomaly_type = label["anomaly_type"]
            anomaly_counts[anomaly_type] = anomaly_counts.get(anomaly_type, 0) + 1

    return {
        "anomalous_rows": total_anomalous_rows,
        "anomaly_counts": anomaly_counts,
    }


def _tag_row(row: dict[str, Any], injector: InjectorSpec, mutation_result: dict[str, Any]) -> None:
    row[IS_ANOMALY_KEY] = True
    row[LABELS_KEY].append(
        {
            "anomaly_type": injector.mutation.kind,
            "injector_id": injector.injector_id,
            "field": injector.field,
            "selection_kind": injector.selection.kind,
            "severity": injector.severity,
            "original_value": mutation_result["original_value"],
            "mutated_value": mutation_result["mutated_value"],
            "applied_mutation": mutation_result["applied_mutation"],
        }
    )


def _validate_field(rows: Sequence[dict[str, Any]], field: str) -> None:
    if rows and field not in rows[0]:
        raise ValueError(f"injector references unknown field: {field}")


def _end_index(end_index: int | None, row_count: int) -> int:
    return row_count if end_index is None else min(end_index, row_count)


def _select_index(row_count: int, selection: SelectionSpec, rng: np.random.Generator) -> list[int]:
    if selection.index >= row_count:
        return []
    return [selection.index]


def _select_window(row_count: int, selection: SelectionSpec, rng: np.random.Generator) -> list[int]:
    start = min(selection.start_index, row_count)
    end = _end_index(selection.end_index, row_count)
    return list(range(start, end))


def _select_rate(row_count: int, selection: SelectionSpec, rng: np.random.Generator) -> list[int]:
    return [index for index in range(row_count) if rng.random() < selection.rate]


def _select_count(row_count: int, selection: SelectionSpec, rng: np.random.Generator) -> list[int]:
    if selection.count > row_count:
        raise ValueError(f"count selection requires count <= row_count; got count={selection.count}, row_count={row_count}")
    return sorted(rng.choice(row_count, size=selection.count, replace=False).tolist())


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


SELECTION_BEHAVIORS: dict[str, SelectionBehavior] = {
    "count": SelectionBehavior(stateless=True, select_indexes=_select_count),
    "index": SelectionBehavior(stateless=False, select_indexes=_select_index),
    "rate": SelectionBehavior(stateless=True, select_indexes=_select_rate),
    "window": SelectionBehavior(stateless=False, select_indexes=_select_window),
}

MUTATION_BEHAVIORS: dict[str, MutationBehavior] = {
    "offset": MutationBehavior(stateless=True, apply=_apply_offset),
    "scale": MutationBehavior(stateless=True, apply=_apply_scale),
    "set_missing": MutationBehavior(stateless=True, apply=_apply_set_missing),
    "set_value": MutationBehavior(stateless=True, apply=_apply_set_value),
}


def injector_is_stateless(injector: InjectorSpec) -> bool:
    selection_behavior = SELECTION_BEHAVIORS[injector.selection.kind]
    mutation_behavior = MUTATION_BEHAVIORS[injector.mutation.kind]
    return selection_behavior.stateless and mutation_behavior.stateless


def validate_stateless_injectors(injectors: Sequence[InjectorSpec]) -> None:
    non_stateless = [
        injector.injector_id
        for injector in injectors
        if not injector_is_stateless(injector)
    ]

    if non_stateless:
        ids = ", ".join(non_stateless)
        raise ValueError(f"scenario sample only supports stateless injectors; invalid injectors: {ids}")


def apply_injectors(
    rows: Sequence[dict[str, Any]],
    injectors: Sequence[InjectorSpec],
    rng: np.random.Generator,
) -> None:
    for injector in injectors:
        _validate_field(rows, injector.field)

        selection_behavior = SELECTION_BEHAVIORS[injector.selection.kind]
        mutation_behavior = MUTATION_BEHAVIORS[injector.mutation.kind]

        indexes = selection_behavior.select_indexes(len(rows), injector.selection, rng)
        for index in indexes:
            mutation_result = mutation_behavior.apply(rows[index], injector.field, injector.mutation, rng)
            _tag_row(rows[index], injector, mutation_result)
