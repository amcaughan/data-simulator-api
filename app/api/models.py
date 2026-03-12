from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class TimeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: datetime | None = None
    frequency_seconds: int = Field(default=60, ge=1)


class DistributionGeneratorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["distribution"]
    distribution: DistributionName
    parameters: dict[str, Any] = Field(default_factory=dict)


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
    DistributionGeneratorSpec | ConstantGeneratorSpec | CategoricalGeneratorSpec,
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
            raise ValueError("offset mutations must use either amount or min_amount/max_amount")

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
            raise ValueError("scale mutations must use either factor or min_factor/max_factor")

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


class InjectorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    injector_id: str
    field: str
    selection: SelectionSpec
    mutation: MutationSpec
    severity: float = Field(default=1.0, ge=0.0)


class ScenarioRequestBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    name: str = "scenario"
    description: str | None = None
    seed: int | None = None
    time: TimeSpec = Field(default_factory=TimeSpec)
    entity_pools: list[EntityPoolSpec] = Field(default_factory=list)
    fields: list[FieldSpec]
    injectors: list[InjectorSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_entity_references(self) -> ScenarioRequestBase:
        pool_names = [pool.name for pool in self.entity_pools]
        if len(pool_names) != len(set(pool_names)):
            raise ValueError("entity pool names must be unique")

        pool_attributes: dict[str, set[str]] = {}
        for pool in self.entity_pools:
            attribute_names = [attribute.name for attribute in pool.attributes]
            if len(attribute_names) != len(set(attribute_names)):
                raise ValueError(f"entity pool attributes must be unique: {pool.name}")
            pool_attributes[pool.name] = set(attribute_names)

        for field in self.fields:
            generator = field.generator

            if generator.kind == "entity_id":
                if generator.entity_name not in pool_attributes:
                    raise ValueError(f"field {field.name} references unknown entity pool: {generator.entity_name}")

            if generator.kind == "entity_attribute":
                if generator.entity_name not in pool_attributes:
                    raise ValueError(f"field {field.name} references unknown entity pool: {generator.entity_name}")
                if generator.attribute not in pool_attributes[generator.entity_name]:
                    raise ValueError(
                        f"field {field.name} references unknown entity attribute: "
                        f"{generator.entity_name}.{generator.attribute}"
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
