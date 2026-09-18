"""The competition contract, with strict types and no implicit string coercion."""

from typing import Annotated, Literal, Union

from pydantic import (
    BaseModel, ConfigDict, Field, StrictBool, StrictInt, StringConstraints,
    field_validator, model_validator,
)

Number = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
Hour = Annotated[StrictInt, Field(ge=0, le=23)]
Text = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]
Identifier = Annotated[str, StringConstraints(strict=True, min_length=1)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HourInput(Model):
    hour: Hour
    demand_kwh: Number
    solar_kwh: Number
    tariff_bdt_per_kwh: Number


class Battery(Model):
    capacity_kwh: Number
    initial_energy_kwh: Number
    minimum_energy_kwh: Number
    max_charge_kwh_per_hour: Number
    max_discharge_kwh_per_hour: Number

    @model_validator(mode="after")
    def valid_bounds(self):
        if not self.minimum_energy_kwh <= self.initial_energy_kwh <= self.capacity_kwh:
            raise ValueError("Require minimum_energy_kwh <= initial_energy_kwh <= capacity_kwh")
        return self


class Scenario(Model):
    scenario_id: Identifier
    operator_notes: list[Text] = Field(min_length=1, max_length=3)
    hours: list[HourInput] = Field(min_length=24, max_length=24)
    battery: Battery

    @field_validator("hours")
    @classmethod
    def unique_hours(cls, value):
        if sorted(h.hour for h in value) != list(range(24)):
            raise ValueError("hours must contain every integer 0 through 23 exactly once")
        # Input order is not constrained by the statement. Output is chronological.
        return sorted(value, key=lambda h: h.hour)


class Window(Model):
    hours: list[Hour] = Field(min_length=1, max_length=24)

    @field_validator("hours")
    @classmethod
    def sorted_unique_hours(cls, value):
        if value != sorted(set(value)):
            raise ValueError("directive hours must be unique and in ascending order")
        return value


class SolarAdjustment(Window):
    factor: Annotated[Number, Field(le=1)]


class ReserveAdjustment(Window):
    minimum_energy_kwh: Number


class GridAdjustment(Window):
    max_grid_kwh: Number


class DirectiveBase(Model):
    note_index: Annotated[StrictInt, Field(ge=0)]
    applies: StrictBool
    explanation: Text

    @model_validator(mode="after")
    def check_applies(self):
        expected = self.directive_type != "no_op"
        if self.applies != expected:
            raise ValueError("applies must be false only for no_op and true for all other types")
        return self


class SolarDirective(DirectiveBase):
    directive_type: Literal["solar_reduction"]
    structured_adjustment: SolarAdjustment


class ReserveDirective(DirectiveBase):
    directive_type: Literal["minimum_battery_reserve"]
    structured_adjustment: ReserveAdjustment


class NoChargeDirective(DirectiveBase):
    directive_type: Literal["no_charge_window"]
    structured_adjustment: Window


class NoDischargeDirective(DirectiveBase):
    directive_type: Literal["no_discharge_window"]
    structured_adjustment: Window


class GridDirective(DirectiveBase):
    directive_type: Literal["max_grid_window"]
    structured_adjustment: GridAdjustment


class NoOpDirective(DirectiveBase):
    directive_type: Literal["no_op"]
    structured_adjustment: None


Directive = Annotated[
    Union[SolarDirective, ReserveDirective, NoChargeDirective,
          NoDischargeDirective, GridDirective, NoOpDirective],
    Field(discriminator="directive_type"),
]


class Interpretation(Model):
    directive_interpretation: list[Directive] = Field(min_length=1, max_length=3)

    def validate_for(self, scenario: Scenario):
        actual = [d.note_index for d in self.directive_interpretation]
        if actual != list(range(len(scenario.operator_notes))):
            raise ValueError("Return exactly one entry per note in note_index order")
        for directive in self.directive_interpretation:
            if directive.directive_type == "minimum_battery_reserve":
                if directive.structured_adjustment.minimum_energy_kwh > scenario.battery.capacity_kwh:
                    raise ValueError("A requested reserve cannot exceed battery capacity")
        return self


class PlanHour(Model):
    hour: Hour
    grid_kwh: Number
    solar_used_kwh: Number
    battery_action: Literal["charge", "discharge", "idle"]
    battery_kwh: Number
    battery_energy_after_kwh: Number

    @model_validator(mode="after")
    def idle_is_zero(self):
        if self.battery_action == "idle" and self.battery_kwh != 0:
            raise ValueError("An idle battery must have battery_kwh = 0")
        return self


class PlanResponse(Model):
    scenario_id: Identifier
    directive_interpretation: list[Directive] = Field(min_length=1, max_length=3)
    hourly_plan: list[PlanHour] = Field(min_length=24, max_length=24)
    total_grid_kwh: Number
    total_cost_bdt: Number
    peak_grid_kwh: Number
    plan_summary: Text
