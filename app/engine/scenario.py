from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.api.models import FieldSpec, ScenarioGenerateRequest, ScenarioRequestBase, ScenarioSampleRequest
from app.engine.distributions import sample_distribution
from app.engine.injectors import (
    apply_injectors,
    initialize_labels,
    summarize_labels,
    validate_stateless_injectors,
)
from app.engine.randomness import derive_seed


DEFAULT_SCENARIO_START = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _generate_field_values(field: FieldSpec, row_count: int, scenario_seed: int | None) -> list[Any]:
    generator = field.generator
    field_seed = derive_seed(scenario_seed, "field", field.name)

    if generator.kind == "constant":
        return [generator.value for _ in range(row_count)]

    if generator.kind == "categorical":
        return sample_distribution(
            distribution="categorical",
            parameters={"values": generator.values, "weights": generator.weights},
            count=row_count,
            seed=field_seed,
        )

    if generator.kind == "distribution":
        return sample_distribution(
            distribution=generator.distribution,
            parameters=generator.parameters,
            count=row_count,
            seed=field_seed,
        )

    raise ValueError(f"unsupported generator kind: {generator.kind}")


def _scenario_start_time(request: ScenarioRequestBase) -> datetime:
    if request.time.start is not None:
        return request.time.start
    if request.seed is not None:
        return DEFAULT_SCENARIO_START
    return datetime.now(timezone.utc)


def _build_rows(request: ScenarioRequestBase, row_count: int, stateless_only: bool = False) -> list[dict[str, Any]]:
    if stateless_only:
        validate_stateless_injectors(request.injectors)
    start_time = _scenario_start_time(request)

    rows = [
        {
            "__row_index": index,
            "event_ts": (start_time + timedelta(seconds=index * request.time.frequency_seconds)).isoformat(),
        }
        for index in range(row_count)
    ]

    for field in request.fields:
        values = _generate_field_values(field, row_count, request.seed)
        for index, value in enumerate(values):
            rows[index][field.name] = value

    initialize_labels(rows)
    apply_injectors(rows, request.injectors, request.seed)
    return rows


def generate_scenario(request: ScenarioGenerateRequest) -> dict[str, Any]:
    rows = _build_rows(request, request.row_count)

    return {
        "schema_version": request.schema_version,
        "scenario_name": request.name,
        "description": request.description,
        "seed": request.seed,
        "row_count": len(rows),
        "fields": [field.name for field in request.fields],
        "rows": rows,
        "label_summary": summarize_labels(rows),
    }


def sample_scenario(request: ScenarioSampleRequest) -> dict[str, Any]:
    rows = _build_rows(request, row_count=1, stateless_only=True)
    row = rows[0]

    return {
        "schema_version": request.schema_version,
        "scenario_name": request.name,
        "description": request.description,
        "seed": request.seed,
        "fields": [field.name for field in request.fields],
        "row": row,
    }
