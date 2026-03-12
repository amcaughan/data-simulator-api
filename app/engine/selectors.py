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


def select_row_indexes(
    rows: Sequence[dict[str, Any]],
    scope: Sequence[FieldMatchSpec],
    selection: SelectionSpec,
    scenario_seed: int | None,
    category: str,
    rule_id: str,
) -> list[int]:
    selection_behavior = SELECTION_BEHAVIORS[selection.kind]
    selection_rng = build_rng(scenario_seed, category, rule_id, "selection")
    candidate_indexes = [index for index, row in enumerate(rows) if matches_scope(row, scope)]
    return selection_behavior.select_indexes(candidate_indexes, selection, selection_rng)


def selection_is_sample_compatible(selection: SelectionSpec) -> bool:
    return SELECTION_BEHAVIORS[selection.kind].sample_compatible
