from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.api.models import FieldMatchSpec, SelectionSpec
from app.engine.randomness import build_rng


@dataclass(frozen=True)
class SelectionBehavior:
    sample_compatible: bool
    select_indexes: Callable[[Sequence[int], SelectionSpec, np.random.Generator], list[int]]


def _end_index(end_index: int | None, row_count: int) -> int:
    return row_count if end_index is None else min(end_index, row_count)


def _select_index(candidate_indexes: Sequence[int], selection: SelectionSpec, rng: np.random.Generator) -> list[int]:
    if selection.index not in candidate_indexes:
        return []
    return [selection.index]


def _select_window(candidate_indexes: Sequence[int], selection: SelectionSpec, rng: np.random.Generator) -> list[int]:
    end = _end_index(selection.end_index, max(candidate_indexes, default=0) + 1)
    return [index for index in candidate_indexes if selection.start_index <= index < end]


def _select_rate(candidate_indexes: Sequence[int], selection: SelectionSpec, rng: np.random.Generator) -> list[int]:
    return [index for index in candidate_indexes if rng.random() < selection.rate]


def _select_count(candidate_indexes: Sequence[int], selection: SelectionSpec, rng: np.random.Generator) -> list[int]:
    if selection.count > len(candidate_indexes):
        raise ValueError(
            "count selection requires count <= eligible_row_count; "
            f"got count={selection.count}, eligible_row_count={len(candidate_indexes)}"
        )
    return sorted(rng.choice(list(candidate_indexes), size=selection.count, replace=False).tolist())


SELECTION_BEHAVIORS: dict[str, SelectionBehavior] = {
    "count": SelectionBehavior(sample_compatible=True, select_indexes=_select_count),
    "index": SelectionBehavior(sample_compatible=False, select_indexes=_select_index),
    "rate": SelectionBehavior(sample_compatible=True, select_indexes=_select_rate),
    "window": SelectionBehavior(sample_compatible=False, select_indexes=_select_window),
}


def matches_scope(row: dict[str, Any], scope: Sequence[FieldMatchSpec]) -> bool:
    return all(row.get(match.field) == match.equals for match in scope)


def _format_scope(scope: Sequence[FieldMatchSpec]) -> str:
    if not scope:
        return "all rows"
    return ", ".join(f"{match.field} == {match.equals!r}" for match in scope)


def _build_count_selection_error(
    selection: SelectionSpec,
    candidate_indexes: Sequence[int],
    target_kind: str,
    target_id: str,
    field_name: str,
    scope: Sequence[FieldMatchSpec],
) -> ValueError:
    eligible_row_count = len(candidate_indexes)
    base_message = (
        f"{target_kind} {target_id!r} on field {field_name!r} requested count={selection.count}, "
        f"but only eligible_row_count={eligible_row_count} rows matched the selector "
        f"(scope: {_format_scope(scope)})."
    )

    if eligible_row_count == 0:
        return ValueError(
            base_message
            + " With the current seed and row generation, no rows matched the scoped selector. "
            + "Try changing the seed, increasing row_count or entity counts, or broadening the scope."
        )

    return ValueError(
        base_message
        + " Reduce the requested count or broaden the scope so more rows are eligible."
    )


def select_row_indexes(
    rows: Sequence[dict[str, Any]],
    scope: Sequence[FieldMatchSpec],
    selection: SelectionSpec,
    scenario_seed: int | None,
    category: str,
    rule_id: str,
    field_name: str,
) -> list[int]:
    selection_behavior = SELECTION_BEHAVIORS[selection.kind]
    selection_rng = build_rng(scenario_seed, category, rule_id, "selection")
    candidate_indexes = [index for index, row in enumerate(rows) if matches_scope(row, scope)]
    if selection.kind == "count" and selection.count > len(candidate_indexes):
        target_kind = "mutation" if category == "mutation" else "process modifier"
        raise _build_count_selection_error(selection, candidate_indexes, target_kind, rule_id, field_name, scope)
    return selection_behavior.select_indexes(candidate_indexes, selection, selection_rng)


def selection_is_sample_compatible(selection: SelectionSpec) -> bool:
    return SELECTION_BEHAVIORS[selection.kind].sample_compatible
