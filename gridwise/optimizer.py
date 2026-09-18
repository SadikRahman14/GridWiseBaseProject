"""An exact continuous LP for the statement's lossless battery model.

Variables per hour: grid g, solar s, signed battery flow b, stored energy e.
b > 0 means charge; b < 0 means discharge. Thus simultaneous actions are
impossible by construction, and binary/MILP variables are unnecessary.
"""

from math import fsum
from threading import Lock

import numpy as np
from scipy.optimize import linprog

from .directives import apply_directives
from .errors import InfeasibleScenario, OptimizationError
from .models import Interpretation, PlanHour, PlanResponse, Scenario

# Keep HiGHS calls serialized within a worker. The HTTP/LLM path remains async.
_solver_lock = Lock()


def _clean(value: float) -> float:
    # Only remove machine-level noise, never round the schedule to cents.
    return 0.0 if abs(value) < 1e-9 else float(value)


def optimize(scenario: Scenario, interpretation: Interpretation) -> PlanResponse:
    limits = apply_directives(scenario, interpretation)
    battery = scenario.battery
    # x = [g0..g23, s0..s23, b0..b23, e0..e23]
    cost = np.zeros(96)
    cost[:24] = [h.tariff_bdt_per_kwh for h in scenario.hours]
    equalities = np.zeros((49, 96))
    rhs = np.zeros(49)
    for h, data in enumerate(scenario.hours):
        equalities[h, h] = 1
        equalities[h, 24 + h] = 1
        equalities[h, 48 + h] = -1  # g + s - b = demand
        rhs[h] = data.demand_kwh
        equalities[24 + h, 72 + h] = 1
        equalities[24 + h, 48 + h] = -1
        if h:
            equalities[24 + h, 72 + h - 1] = -1
        else:
            rhs[24 + h] = battery.initial_energy_kwh
    equalities[48, 95] = 1
    rhs[48] = battery.initial_energy_kwh

    bounds = (
        [(0, None if np.isinf(limits.grid[h]) else limits.grid[h]) for h in range(24)]
        + [(0, limits.solar[h]) for h in range(24)]
        + [(-limits.discharge[h], limits.charge[h]) for h in range(24)]
        + [(limits.reserve[h], battery.capacity_kwh) for h in range(24)]
    )
    with _solver_lock:
        result = linprog(
            cost, A_eq=equalities, b_eq=rhs, bounds=bounds, method="highs",
            options={"time_limit": 2.0, "primal_feasibility_tolerance": 1e-9,
                     "dual_feasibility_tolerance": 1e-9},
        )
    if result.status == 2:
        raise InfeasibleScenario("The interpreted directives and battery limits have no feasible schedule.")
    if not result.success or result.x is None or not np.isfinite(result.x).all():
        raise OptimizationError("The optimizer did not produce a verified optimal solution.")

    plan = []
    for h in range(24):
        flow = _clean(result.x[48 + h])
        plan.append(PlanHour(
            hour=h, grid_kwh=_clean(result.x[h]), solar_used_kwh=_clean(result.x[24 + h]),
            battery_action="charge" if flow > 0 else "discharge" if flow < 0 else "idle",
            battery_kwh=abs(flow), battery_energy_after_kwh=_clean(result.x[72 + h]),
        ))
    total_cost = fsum(p.grid_kwh * scenario.hours[p.hour].tariff_bdt_per_kwh for p in plan)
    active = sum(d.applies for d in interpretation.directive_interpretation)
    response = PlanResponse(
        scenario_id=scenario.scenario_id,
        directive_interpretation=interpretation.directive_interpretation,
        hourly_plan=plan,
        total_grid_kwh=fsum(p.grid_kwh for p in plan),
        total_cost_bdt=_clean(total_cost),
        peak_grid_kwh=max(p.grid_kwh for p in plan),
        plan_summary=(f"Applied {active} operating directive(s). Minimized 24-hour grid cost "
                      f"to {total_cost:.2f} BDT using available solar and battery flexibility; "
                      f"battery ends at its initial {battery.initial_energy_kwh:g} kWh."),
    )
    # The replay below rebuilds rules independently of this LP and its bounds.
    from .validation import validate_plan
    validate_plan(scenario, response)
    return response
