from __future__ import annotations

from app.api.models import FieldSpec, ScenarioGenerateRequest, ScenarioRequestBase, ScenarioSampleRequest
from app.engine.entities import EntityContext, build_entity_context, generate_entity_values
from app.engine.generators import generate_contextual_distribution_values, generate_primitive_values
from app.engine.injectors import (
    apply_injectors,
    initialize_labels,
    summarize_labels,
    validate_stateless_injectors,
)


def _generate_field_values(
    field: FieldSpec,
    rows: list[dict[str, object]],
    scenario_seed: int | None,
    entity_context: EntityContext,
) -> list[object]:
    generator = field.generator
    row_count = len(rows)

    if generator.kind in {"constant", "categorical", "distribution", "sequence"}:
        return generate_primitive_values(generator, row_count, scenario_seed, "field", field.name)

    if generator.kind == "contextual_distribution":
        return generate_contextual_distribution_values(generator, field.name, rows, scenario_seed, entity_context)

    if generator.kind in {"entity_attribute", "entity_id"}:
        return generate_entity_values(generator, row_count, entity_context)

    raise ValueError(f"unsupported generator kind: {generator.kind}")


def _build_rows(request: ScenarioRequestBase, row_count: int, stateless_only: bool = False) -> list[dict[str, Any]]:
    if stateless_only:
        validate_stateless_injectors(request.injectors)
    entity_context = build_entity_context(request.entity_pools, row_count, request.seed)

    rows = [{"__row_index": index} for index in range(row_count)]

    for field in request.fields:
        values = _generate_field_values(field, rows, request.seed, entity_context)
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
