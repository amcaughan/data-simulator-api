from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.api.models import DistributionName, ProcessModifierSpec
from app.engine.parameter_modifiers import apply_parameter_modifiers
from app.engine.selectors import select_row_indexes, selection_is_sample_compatible


@dataclass(frozen=True)
class PlannedProcessModifier:
    spec: ProcessModifierSpec
    selected_indexes: frozenset[int]


def process_modifier_is_sample_compatible(process_modifier: ProcessModifierSpec) -> bool:
    return selection_is_sample_compatible(process_modifier.selection)


def validate_sample_compatible_process_modifiers(process_modifiers: Sequence[ProcessModifierSpec]) -> None:
    incompatible_ids = [
        process_modifier.modifier_id
        for process_modifier in process_modifiers
        if not process_modifier_is_sample_compatible(process_modifier)
    ]

    if incompatible_ids:
        ids = ", ".join(incompatible_ids)
        raise ValueError(
            "scenario sample only supports sample-compatible process modifiers; "
            f"invalid process modifiers: {ids}"
        )


def plan_process_modifiers(
    rows: Sequence[dict[str, Any]],
    field_name: str,
    process_modifiers: Sequence[ProcessModifierSpec],
    scenario_seed: int | None,
) -> list[PlannedProcessModifier]:
    plans: list[PlannedProcessModifier] = []

    for process_modifier in process_modifiers:
        if process_modifier.field != field_name:
            continue

        selected_indexes = frozenset(
            select_row_indexes(
                rows,
                process_modifier.scope,
                process_modifier.selection,
                scenario_seed,
                "process_modifier",
                process_modifier.modifier_id,
                process_modifier.field,
            )
        )
        plans.append(PlannedProcessModifier(spec=process_modifier, selected_indexes=selected_indexes))

    return plans


def apply_planned_process_modifiers(
    field_name: str,
    distribution: DistributionName,
    base_parameters: dict[str, Any],
    row: dict[str, Any],
    row_index: int,
    plans: Sequence[PlannedProcessModifier],
    entity_context: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    parameters = dict(base_parameters)
    labels: list[dict[str, Any]] = []

    for plan in plans:
        if row_index not in plan.selected_indexes:
            continue

        parameters, applied_adjustments = apply_parameter_modifiers(
            distribution,
            parameters,
            plan.spec.parameter_modifiers,
            row,
            row_index,
            entity_context,
        )
        if not applied_adjustments:
            continue

        labels.append(
            {
                "label_source": "process_modifier",
                "anomaly_type": "parameter_adjustment",
                "modifier_id": plan.spec.modifier_id,
                "field": field_name,
                "selection_kind": plan.spec.selection.kind,
                "severity": plan.spec.severity,
                "applied_parameter_modifiers": applied_adjustments,
            }
        )

    return parameters, labels
