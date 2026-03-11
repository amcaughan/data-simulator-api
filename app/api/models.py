from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


DistributionName = Literal[
    "bernoulli",
    "categorical",
    "exponential",
    "lognormal",
    "normal",
    "poisson",
    "uniform",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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

    start: datetime = Field(default_factory=utc_now)
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


GeneratorSpec = Annotated[
    DistributionGeneratorSpec | ConstantGeneratorSpec | CategoricalGeneratorSpec,
    Field(discriminator="kind"),
]


class FieldSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    generator: GeneratorSpec
    nullable: bool = False


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
    amount: float


class ScaleMutationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["scale"]
    factor: float


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
    fields: list[FieldSpec]
    injectors: list[InjectorSpec] = Field(default_factory=list)


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
