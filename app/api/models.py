from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _find_duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []

    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)

    return duplicates


DistributionName = Literal[
    "bernoulli",
    "categorical",
    "exponential",
    "lognormal",
    "normal",
    "poisson",
    "uniform",
]


class DistributionRequestBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    distribution: DistributionName
    parameters: dict[str, Any] = Field(default_factory=dict)
    seed: int | None = None


class DistributionSampleRequest(DistributionRequestBase):
    model_config = ConfigDict(extra="forbid")


class DistributionGenerateRequest(DistributionRequestBase):
    model_config = ConfigDict(extra="forbid")

    count: int = Field(default=100, ge=1, le=5000)
    summary: bool = False


class DistributionGeneratorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["distribution"]
    distribution: DistributionName
    parameters: dict[str, Any] = Field(default_factory=dict)


class SequenceGeneratorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["sequence"]
    start: int | float = 0
    step: int | float = 1


class FieldMatchSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    equals: Any


class ParameterModifierSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parameter: str
    operation: Literal["add", "multiply", "set"]
    value: float | None = None
    source_field: str | None = None
    entity_name: str | None = None
    entity_attribute: str | None = None
    when: list[FieldMatchSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_source_config(self) -> ParameterModifierSpec:
        sources = [
            self.value is not None,
            self.source_field is not None,
            self.entity_name is not None or self.entity_attribute is not None,
        ]
        if sum(sources) != 1:
            raise ValueError(
                "parameter modifiers must use exactly one source: value, source_field, "
                "or entity_name/entity_attribute"
            )

        if (self.entity_name is None) != (self.entity_attribute is None):
            raise ValueError("entity_name and entity_attribute must be provided together")

        return self


class ContextualDistributionGeneratorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["contextual_distribution"]
    distribution: DistributionName
    parameters: dict[str, Any] = Field(default_factory=dict)
    parameter_modifiers: list[ParameterModifierSpec] = Field(default_factory=list)


class ConstantGeneratorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["constant"]
    value: Any


class CategoricalGeneratorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["categorical"]
    values: list[Any]
    weights: list[float] | None = None


PrimitiveGeneratorSpec = Annotated[
    DistributionGeneratorSpec | SequenceGeneratorSpec | ConstantGeneratorSpec | CategoricalGeneratorSpec,
    Field(discriminator="kind"),
]


class EntityIdGeneratorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["entity_id"]
    entity_name: str


class EntityAttributeGeneratorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["entity_attribute"]
    entity_name: str
    attribute: str


GeneratorSpec = Annotated[
    DistributionGeneratorSpec
    | ContextualDistributionGeneratorSpec
    | SequenceGeneratorSpec
    | ConstantGeneratorSpec
    | CategoricalGeneratorSpec
    | EntityIdGeneratorSpec
    | EntityAttributeGeneratorSpec,
    Field(discriminator="kind"),
]


class FieldSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    generator: GeneratorSpec
    nullable: bool = False


class EntityAttributeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    generator: PrimitiveGeneratorSpec


class EntityPoolSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    count: int = Field(ge=1, le=5000)
    id_prefix: str | None = None
    attributes: list[EntityAttributeSpec] = Field(default_factory=list)


class IndexSelectionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["index"]
    index: int = Field(ge=0)


class WindowSelectionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["window"]
    start_index: int = Field(ge=0)
    end_index: int | None = Field(default=None, ge=0)


class RateSelectionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["rate"]
    rate: float = Field(gt=0.0, le=1.0)


class CountSelectionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["count"]
    count: int = Field(ge=1)


SelectionSpec = Annotated[
    IndexSelectionSpec | WindowSelectionSpec | RateSelectionSpec | CountSelectionSpec,
    Field(discriminator="kind"),
]


class OffsetMutationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["offset"]
    amount: float | None = None
    min_amount: float | None = None
    max_amount: float | None = None

    @model_validator(mode="after")
    def validate_amount_config(self) -> OffsetMutationSpec:
        has_fixed_amount = self.amount is not None
        has_any_range = self.min_amount is not None or self.max_amount is not None

        if has_fixed_amount and has_any_range:
            raise ValueError("offset mutations must use either amount or min_amount/max_amount, not both")

        if has_fixed_amount:
            return self

        if self.min_amount is None or self.max_amount is None:
            raise ValueError("offset range mutations require both min_amount and max_amount")
        if self.max_amount < self.min_amount:
            raise ValueError("offset range mutations require max_amount >= min_amount")
        return self


class ScaleMutationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["scale"]
    factor: float | None = Field(default=None, gt=0.0)
    min_factor: float | None = Field(default=None, gt=0.0)
    max_factor: float | None = Field(default=None, gt=0.0)

    @model_validator(mode="after")
    def validate_factor_config(self) -> ScaleMutationSpec:
        has_fixed_factor = self.factor is not None
        has_any_range = self.min_factor is not None or self.max_factor is not None

        if has_fixed_factor and has_any_range:
            raise ValueError("scale mutations must use either factor or min_factor/max_factor, not both")

        if has_fixed_factor:
            return self

        if self.min_factor is None or self.max_factor is None:
            raise ValueError("scale range mutations require both min_factor and max_factor")
        if self.max_factor < self.min_factor:
            raise ValueError("scale range mutations require max_factor >= min_factor")
        return self


class SetValueMutationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["set_value"]
    value: Any


class SetMissingMutationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["set_missing"]


MutationSpec = Annotated[
    OffsetMutationSpec | ScaleMutationSpec | SetValueMutationSpec | SetMissingMutationSpec,
    Field(discriminator="kind"),
]


class ProcessModifierSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modifier_id: str
    field: str
    scope: list[FieldMatchSpec] = Field(default_factory=list)
    selection: SelectionSpec
    parameter_modifiers: list[ParameterModifierSpec] = Field(default_factory=list, min_length=1)
    severity: float = Field(default=1.0, ge=0.0)


class RowMutationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mutation_id: str
    field: str
    scope: list[FieldMatchSpec] = Field(default_factory=list)
    selection: SelectionSpec
    mutation: MutationSpec
    severity: float = Field(default=1.0, ge=0.0)


def _validate_entity_reference(
    owner: str,
    entity_name: str,
    entity_attribute: str | None,
    pool_attributes: dict[str, set[str]],
) -> None:
    if entity_name not in pool_attributes:
        raise ValueError(f"{owner} references unknown entity pool: {entity_name}")

    if entity_attribute is not None and entity_attribute not in pool_attributes[entity_name]:
        raise ValueError(f"{owner} references unknown entity attribute: {entity_name}.{entity_attribute}")


def _validate_parameter_modifier_references(
    owner: str,
    parameter_modifiers: list[ParameterModifierSpec],
    pool_attributes: dict[str, set[str]],
    available_fields: set[str],
) -> None:
    for parameter_modifier in parameter_modifiers:
        if parameter_modifier.source_field is not None and parameter_modifier.source_field not in available_fields:
            raise ValueError(f"{owner} references unavailable source field: {parameter_modifier.source_field}")

        if parameter_modifier.entity_name is not None:
            _validate_entity_reference(
                owner,
                parameter_modifier.entity_name,
                parameter_modifier.entity_attribute,
                pool_attributes,
            )

        for condition in parameter_modifier.when:
            if condition.field not in available_fields:
                raise ValueError(f"{owner} references unavailable condition field: {condition.field}")


class ScenarioRequestBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    name: str = "scenario"
    description: str | None = None
    seed: int | None = None
    entity_pools: list[EntityPoolSpec] = Field(default_factory=list)
    fields: list[FieldSpec]
    process_modifiers: list[ProcessModifierSpec] = Field(default_factory=list)
    mutations: list[RowMutationSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> ScenarioRequestBase:
        pool_names = [pool.name for pool in self.entity_pools]
        if len(pool_names) != len(set(pool_names)):
            duplicate_pool_names = ", ".join(_find_duplicates(pool_names))
            raise ValueError(f"entity pool names must be unique; duplicates: {duplicate_pool_names}")

        field_names = [field.name for field in self.fields]
        if len(field_names) != len(set(field_names)):
            duplicate_field_names = ", ".join(_find_duplicates(field_names))
            raise ValueError(f"field names must be unique; duplicates: {duplicate_field_names}")

        process_modifier_ids = [modifier.modifier_id for modifier in self.process_modifiers]
        if len(process_modifier_ids) != len(set(process_modifier_ids)):
            duplicate_modifier_ids = ", ".join(_find_duplicates(process_modifier_ids))
            raise ValueError(f"process modifier ids must be unique; duplicates: {duplicate_modifier_ids}")

        mutation_ids = [mutation.mutation_id for mutation in self.mutations]
        if len(mutation_ids) != len(set(mutation_ids)):
            duplicate_mutation_ids = ", ".join(_find_duplicates(mutation_ids))
            raise ValueError(f"mutation ids must be unique; duplicates: {duplicate_mutation_ids}")

        pool_attributes: dict[str, set[str]] = {}
        for pool in self.entity_pools:
            attribute_names = [attribute.name for attribute in pool.attributes]
            if len(attribute_names) != len(set(attribute_names)):
                duplicate_attribute_names = ", ".join(_find_duplicates(attribute_names))
                raise ValueError(
                    f"entity pool attributes must be unique for pool {pool.name!r}; "
                    f"duplicates: {duplicate_attribute_names}"
                )
            pool_attributes[pool.name] = set(attribute_names)

        field_generators: dict[str, GeneratorSpec] = {}
        for field in self.fields:
            generator = field.generator

            if generator.kind == "entity_id":
                _validate_entity_reference(f"field {field.name}", generator.entity_name, None, pool_attributes)

            if generator.kind == "entity_attribute":
                _validate_entity_reference(
                    f"field {field.name}",
                    generator.entity_name,
                    generator.attribute,
                    pool_attributes,
                )

            field_generators[field.name] = generator

        available_fields: set[str] = set()
        for field in self.fields:
            generator = field.generator

            if generator.kind == "contextual_distribution":
                _validate_parameter_modifier_references(
                    f"field {field.name}",
                    generator.parameter_modifiers,
                    pool_attributes,
                    available_fields,
                )

            field_process_modifiers = [
                process_modifier for process_modifier in self.process_modifiers if process_modifier.field == field.name
            ]
            if field_process_modifiers and generator.kind not in {"distribution", "contextual_distribution"}:
                raise ValueError(
                    "process modifiers can only target distribution or contextual_distribution fields; "
                    f"field {field.name!r} uses generator kind {generator.kind!r}"
                )

            for process_modifier in field_process_modifiers:
                for match in process_modifier.scope:
                    if match.field not in available_fields:
                        raise ValueError(
                            f"process modifier {process_modifier.modifier_id} references unavailable scope field: "
                            f"{match.field}"
                        )

                _validate_parameter_modifier_references(
                    f"process modifier {process_modifier.modifier_id}",
                    process_modifier.parameter_modifiers,
                    pool_attributes,
                    available_fields,
                )

            available_fields.add(field.name)

        all_field_names = set(field_generators)
        for process_modifier in self.process_modifiers:
            if process_modifier.field not in all_field_names:
                raise ValueError(
                    f"process modifier {process_modifier.modifier_id} references unknown field: "
                    f"{process_modifier.field}"
                )

        for mutation in self.mutations:
            if mutation.field not in all_field_names:
                raise ValueError(f"mutation {mutation.mutation_id} references unknown field: {mutation.field}")

            for match in mutation.scope:
                if match.field not in all_field_names:
                    raise ValueError(
                        f"mutation {mutation.mutation_id} references unknown scope field: {match.field}"
                    )

        return self


class ScenarioSampleRequest(ScenarioRequestBase):
    model_config = ConfigDict(extra="forbid")


class ScenarioGenerateRequest(ScenarioRequestBase):
    model_config = ConfigDict(extra="forbid")

    row_count: int = Field(default=100, ge=1, le=5000)


class PresetRequestBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed: int | None = None
    overrides: dict[str, Any] = Field(default_factory=dict)


class PresetSampleRequest(PresetRequestBase):
    model_config = ConfigDict(extra="forbid")


class PresetGenerateRequest(PresetRequestBase):
    model_config = ConfigDict(extra="forbid")

    row_count: int = Field(default=100, ge=1, le=5000)
