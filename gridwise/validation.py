"""Independent replay: does not use the optimizer or its compiled bounds."""

from math import fsum, isclose, isfinite

from .errors import ReplayError
from .models import Interpretation, PlanResponse, Scenario


def validate_plan(
    scenario: Scenario, plan: PlanResponse,
    ground_truth: Interpretation | None = None, tolerance: float = 1e-6,
) -> None:
    """Optionally validate against organizer truth rather than claimed directives."""
    claimed = Interpretation(directive_interpretation=plan.directive_interpretation)
    claimed.validate_for(scenario)
    interpretation = ground_truth or claimed
    interpretation.validate_for(scenario)

    def require(condition, message):
        if not condition:
            raise ReplayError(message)

    def close(a, b):
        return isclose(a, b, rel_tol=0, abs_tol=tolerance)

    require(plan.scenario_id == scenario.scenario_id, "scenario_id does not match")
    require([p.hour for p in plan.hourly_plan] == list(range(24)), "Plan hours must be 0..23 in order")
    state = scenario.battery.initial_energy_kwh
    for data, row in zip(scenario.hours, plan.hourly_plan):
        h = data.hour
        values = [row.grid_kwh, row.solar_used_kwh, row.battery_kwh, row.battery_energy_after_kwh]
        require(all(isfinite(x) and x >= 0 for x in values), f"Non-finite/negative energy at hour {h}")
        solar_factor = 1.0
        reserve = scenario.battery.minimum_energy_kwh
        grid_cap = float("inf")
        no_charge = no_discharge = False
        for d in interpretation.directive_interpretation:
            if d.directive_type == "no_op" or h not in d.structured_adjustment.hours:
                continue
            a = d.structured_adjustment
            if d.directive_type == "solar_reduction":
                solar_factor = min(solar_factor, a.factor)
            elif d.directive_type == "minimum_battery_reserve":
                reserve = max(reserve, a.minimum_energy_kwh)
            elif d.directive_type == "max_grid_window":
                grid_cap = min(grid_cap, a.max_grid_kwh)
            elif d.directive_type == "no_charge_window":
                no_charge = True
            elif d.directive_type == "no_discharge_window":
                no_discharge = True
        charge = row.battery_kwh if row.battery_action == "charge" else 0.0
        discharge = row.battery_kwh if row.battery_action == "discharge" else 0.0
        require(row.battery_action != "idle" or row.battery_kwh == 0, f"Nonzero idle action at hour {h}")
        require(not no_charge or charge <= tolerance, f"Charging prohibited at hour {h}")
        require(not no_discharge or discharge <= tolerance, f"Discharging prohibited at hour {h}")
        require(charge <= scenario.battery.max_charge_kwh_per_hour + tolerance, f"Charge rate at hour {h}")
        require(discharge <= scenario.battery.max_discharge_kwh_per_hour + tolerance, f"Discharge rate at hour {h}")
        require(row.grid_kwh <= grid_cap + tolerance, f"Grid cap at hour {h}")
        require(row.solar_used_kwh <= data.solar_kwh * solar_factor + tolerance, f"Solar overuse at hour {h}")
        require(close(row.grid_kwh + row.solar_used_kwh + discharge, data.demand_kwh + charge),
                f"Energy balance at hour {h}")
        state += charge - discharge
        require(close(state, row.battery_energy_after_kwh), f"Battery transition at hour {h}")
        require(reserve - tolerance <= state <= scenario.battery.capacity_kwh + tolerance,
                f"Battery bound at hour {h}")
    require(close(state, scenario.battery.initial_energy_kwh), "End-of-day neutrality failed")
    require(close(plan.total_grid_kwh, fsum(p.grid_kwh for p in plan.hourly_plan)), "Grid total mismatch")
    require(close(plan.total_cost_bdt, fsum(p.grid_kwh * scenario.hours[p.hour].tariff_bdt_per_kwh
                                         for p in plan.hourly_plan)), "Cost total mismatch")
    require(close(plan.peak_grid_kwh, max(p.grid_kwh for p in plan.hourly_plan)), "Peak mismatch")
