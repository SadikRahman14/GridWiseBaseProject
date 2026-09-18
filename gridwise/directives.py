"""Turn already-validated directives into hard hourly bounds."""

from dataclasses import dataclass

import numpy as np

from .models import Interpretation, Scenario


@dataclass
class Limits:
    solar: np.ndarray
    reserve: np.ndarray
    charge: np.ndarray
    discharge: np.ndarray
    grid: np.ndarray


def apply_directives(scenario: Scenario, interpretation: Interpretation) -> Limits:
    interpretation.validate_for(scenario)
    battery = scenario.battery
    factors = np.ones(24)
    limits = Limits(
        solar=np.array([h.solar_kwh for h in scenario.hours], dtype=float),
        reserve=np.full(24, battery.minimum_energy_kwh, dtype=float),
        charge=np.full(24, battery.max_charge_kwh_per_hour, dtype=float),
        discharge=np.full(24, battery.max_discharge_kwh_per_hour, dtype=float),
        grid=np.full(24, np.inf),
    )
    for directive in interpretation.directive_interpretation:
        kind = directive.directive_type
        if kind == "no_op":
            continue
        adjustment = directive.structured_adjustment
        hours = adjustment.hours
        if kind == "solar_reduction":
            # Each factor describes availability relative to ORIGINAL solar.
            # Overlapping reductions use the tightest factor, not a compounded
            # percentage. The documents do not explicitly define this overlap;
            # this is the documented assumption in docs/ARCHITECTURE.md.
            factors[hours] = np.minimum(factors[hours], adjustment.factor)
        elif kind == "minimum_battery_reserve":
            limits.reserve[hours] = np.maximum(limits.reserve[hours], adjustment.minimum_energy_kwh)
        elif kind == "no_charge_window":
            limits.charge[hours] = 0
        elif kind == "no_discharge_window":
            limits.discharge[hours] = 0
        elif kind == "max_grid_window":
            limits.grid[hours] = np.minimum(limits.grid[hours], adjustment.max_grid_kwh)
    limits.solar *= factors
    return limits
