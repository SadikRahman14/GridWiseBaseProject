import copy
import random

import pytest

from gridwise.errors import InfeasibleScenario, ReplayError
from gridwise.models import Interpretation, PlanResponse, Scenario
from gridwise.optimizer import optimize
from gridwise.validation import validate_plan


def interpretation(case):
    return Interpretation(directive_interpretation=case["expected_output"]["directive_interpretation"])


@pytest.mark.parametrize("index", range(10))
def test_public_optima_and_replay(cases, index):
    case = cases[index]
    scenario = Scenario.model_validate(case["input"])
    result = optimize(scenario, interpretation(case))
    validate_plan(scenario, result, ground_truth=interpretation(case))
    assert result.total_cost_bdt == pytest.approx(case["expected_output"]["total_cost_bdt"], abs=0.01)


@pytest.mark.parametrize("index", range(10))
def test_organizer_reference_passes_independent_replay(cases, index):
    case = cases[index]
    validate_plan(Scenario.model_validate(case["input"]), PlanResponse.model_validate(case["expected_output"]))


def small_scenario(seed, capacity=4):
    rng = random.Random(seed)
    return Scenario.model_validate({
        "scenario_id": f"SYNTHETIC-{seed}", "operator_notes": ["An unrelated office notice."],
        "battery": {"capacity_kwh": capacity, "initial_energy_kwh": min(2, capacity),
                    "minimum_energy_kwh": 0, "max_charge_kwh_per_hour": 2, "max_discharge_kwh_per_hour": 2},
        "hours": [{"hour": h, "demand_kwh": rng.randint(0, 6), "solar_kwh": rng.randint(0, 6),
                   "tariff_bdt_per_kwh": rng.randint(0, 15)} for h in range(24)],
    })


def noop():
    return Interpretation(directive_interpretation=[{
        "note_index": 0, "applies": False, "directive_type": "no_op",
        "structured_adjustment": None, "explanation": "Unrelated notice.",
    }])


def discrete_oracle(scenario, truth):
    """Enumerate all integer energy states with dynamic programming.

    Integer inputs give an integral optimum for this flow LP. This oracle uses
    no SciPy, LP matrices, compiled bounds, or optimized schedule.
    """
    battery = scenario.battery
    costs = {int(battery.initial_energy_kwh): 0.0}
    for data in scenario.hours:
        h, new = data.hour, {}
        solar = data.solar_kwh
        reserve, grid_cap = battery.minimum_energy_kwh, float("inf")
        charge_limit, discharge_limit = battery.max_charge_kwh_per_hour, battery.max_discharge_kwh_per_hour
        for d in truth.directive_interpretation:
            if d.directive_type == "no_op" or h not in d.structured_adjustment.hours:
                continue
            a = d.structured_adjustment
            if d.directive_type == "solar_reduction":
                solar = min(solar, data.solar_kwh * a.factor)
            elif d.directive_type == "minimum_battery_reserve":
                reserve = max(reserve, a.minimum_energy_kwh)
            elif d.directive_type == "no_charge_window":
                charge_limit = 0
            elif d.directive_type == "no_discharge_window":
                discharge_limit = 0
            elif d.directive_type == "max_grid_window":
                grid_cap = min(grid_cap, a.max_grid_kwh)
        for before, previous_cost in costs.items():
            for after in range(int(battery.capacity_kwh) + 1):
                flow = after - before
                load = data.demand_kwh + flow
                if after < reserve or not -discharge_limit <= flow <= charge_limit or load < 0:
                    continue
                grid = max(0, load - solar)
                if grid > grid_cap:
                    continue
                candidate = previous_cost + grid * data.tariff_bdt_per_kwh
                new[after] = min(new.get(after, float("inf")), candidate)
        costs = new
    return costs.get(int(battery.initial_energy_kwh), float("inf"))


@pytest.mark.parametrize("seed", range(24))
def test_solver_matches_independent_dynamic_program(seed):
    scenario = small_scenario(seed)
    # Include directive combinations, zero tariffs, curtailment, and infeasibility.
    variants = [
        ("minimum_battery_reserve", {"hours": [17, 18, 19], "minimum_energy_kwh": 3}),
        ("no_charge_window", {"hours": [2, 3, 4]}),
        ("no_discharge_window", {"hours": [18, 19, 20]}),
        ("max_grid_window", {"hours": [18, 19], "max_grid_kwh": 2}),
        ("solar_reduction", {"hours": [10, 11, 12], "factor": 0}),
    ]
    chosen = [variants[seed % 5], variants[(seed + 2) % 5]]
    data = scenario.model_dump()
    data["operator_notes"] = ["Synthetic directive A", "Synthetic directive B"]
    scenario = Scenario.model_validate(data)
    truth = Interpretation(directive_interpretation=[{
        "note_index": i, "applies": True, "directive_type": kind,
        "structured_adjustment": adjustment, "explanation": "Synthetic solver test.",
    } for i, (kind, adjustment) in enumerate(chosen)])
    expected = discrete_oracle(scenario, truth)
    if expected == float("inf"):
        with pytest.raises(InfeasibleScenario):
            optimize(scenario, truth)
    else:
        result = optimize(scenario, truth)
        assert result.total_cost_bdt == pytest.approx(expected, abs=1e-6)
        validate_plan(scenario, result, truth)


def test_zero_capacity_and_surplus_solar():
    scenario = small_scenario(8, capacity=0)
    result = optimize(scenario, noop())
    expected = sum(max(0, h.demand_kwh - h.solar_kwh) * h.tariff_bdt_per_kwh for h in scenario.hours)
    assert result.total_cost_bdt == expected
    assert all(p.battery_action == "idle" for p in result.hourly_plan)


def test_shuffled_input_is_sorted(cases):
    raw = copy.deepcopy(cases[0]["input"])
    raw["hours"].reverse()
    scenario = Scenario.model_validate(raw)
    result = optimize(scenario, interpretation(cases[0]))
    assert [p.hour for p in result.hourly_plan] == list(range(24))
    assert result.total_cost_bdt == 38365


def test_scenario_id_is_echoed_verbatim(cases):
    raw = copy.deepcopy(cases[0]["input"])
    raw["scenario_id"] = "  original-id  "
    result = optimize(Scenario.model_validate(raw), interpretation(cases[0]))
    assert result.scenario_id == raw["scenario_id"]


def test_infeasible_cap_fails_cleanly():
    scenario = small_scenario(6, capacity=0)
    truth = Interpretation(directive_interpretation=[{
        "note_index": 0, "applies": True, "directive_type": "max_grid_window",
        "structured_adjustment": {"hours": list(range(24)), "max_grid_kwh": 0},
        "explanation": "Grid is unavailable.",
    }])
    with pytest.raises(InfeasibleScenario):
        optimize(scenario, truth)


@pytest.mark.parametrize("fault", ["grid", "cost", "battery", "solar", "hours", "id"])
def test_replay_detects_tampering(cases, fault):
    scenario = Scenario.model_validate(cases[0]["input"])
    response = optimize(scenario, interpretation(cases[0]))
    if fault == "grid":
        response.hourly_plan[0].grid_kwh += 1
    elif fault == "cost":
        response.total_cost_bdt += 1
    elif fault == "battery":
        response.hourly_plan[-1].battery_energy_after_kwh += 1
    elif fault == "solar":
        response.hourly_plan[0].solar_used_kwh += 1
    elif fault == "hours":
        response.hourly_plan.reverse()
    elif fault == "id":
        response.scenario_id = "WRONG"
    with pytest.raises(ReplayError):
        validate_plan(scenario, response)


def test_ground_truth_catches_ignored_directive(cases):
    scenario = Scenario.model_validate(cases[4]["input"])
    unconstrained = optimize(scenario, noop())
    # Inject a more restrictive feasible cap at an hour where this plan imports.
    h = max(range(24), key=lambda k: unconstrained.hourly_plan[k].grid_kwh)
    truth = Interpretation(directive_interpretation=[{
        "note_index": 0, "applies": True, "directive_type": "max_grid_window",
        "structured_adjustment": {"hours": [h], "max_grid_kwh": 0},
        "explanation": "Ground-truth cap for replay test.",
    }])
    with pytest.raises(ReplayError):
        validate_plan(scenario, unconstrained, ground_truth=truth)
