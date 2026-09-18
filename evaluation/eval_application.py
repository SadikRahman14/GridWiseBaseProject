import copy
import json
import math
import time
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

CASES_FILE = PROJECT_ROOT / "evaluation" / "multi_note_cases.json"
SAMPLE_REQUEST_FILE = PROJECT_ROOT / "examples" / "sample_request.json"

API_URL = "http://127.0.0.1:8000/optimize-energy"

TOLERANCE = 0.01
REQUEST_TIMEOUT_SECONDS = 30
DELAY_BETWEEN_CASES_SECONDS = 5


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def close_enough(a, b):
    return math.isclose(
        float(a),
        float(b),
        abs_tol=TOLERANCE,
        rel_tol=0
    )


def call_gridwise(payload):
    body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    started = time.perf_counter()

    try:
        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS
        ) as response:

            response_body = response.read().decode("utf-8")
            elapsed = time.perf_counter() - started

            return (
                response.status,
                json.loads(response_body),
                elapsed
            )

    except urllib.error.HTTPError as error:
        elapsed = time.perf_counter() - started

        body = error.read().decode(
            "utf-8",
            errors="replace"
        )

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"raw_response": body}

        return error.code, parsed, elapsed


def build_constraints(base_request, directives):
    battery = base_request["battery"]

    solar_factor = [1.0] * 24

    reserve = [
        battery["minimum_energy_kwh"]
    ] * 24

    no_charge = [False] * 24
    no_discharge = [False] * 24

    grid_cap = [math.inf] * 24

    for directive in directives:

        if not directive["applies"]:
            continue

        dtype = directive["directive_type"]
        adjustment = directive["structured_adjustment"]

        hours = adjustment["hours"]

        if dtype == "solar_reduction":

            factor = adjustment["factor"]

            for hour in hours:
                solar_factor[hour] = min(
                    solar_factor[hour],
                    factor
                )

        elif dtype == "minimum_battery_reserve":

            minimum = adjustment[
                "minimum_energy_kwh"
            ]

            for hour in hours:
                reserve[hour] = max(
                    reserve[hour],
                    minimum
                )

        elif dtype == "no_charge_window":

            for hour in hours:
                no_charge[hour] = True

        elif dtype == "no_discharge_window":

            for hour in hours:
                no_discharge[hour] = True

        elif dtype == "max_grid_window":

            maximum = adjustment["max_grid_kwh"]

            for hour in hours:
                grid_cap[hour] = min(
                    grid_cap[hour],
                    maximum
                )

    return {
        "solar_factor": solar_factor,
        "reserve": reserve,
        "no_charge": no_charge,
        "no_discharge": no_discharge,
        "grid_cap": grid_cap,
    }


def validate_schedule(base_request, directives, response):
    errors = []

    plan = response.get("hourly_plan")

    if not isinstance(plan, list):
        return ["hourly_plan is missing or is not a list"]

    if len(plan) != 24:
        errors.append(
            f"hourly_plan contains {len(plan)} entries instead of 24"
        )
        return errors

    try:
        plan_by_hour = {
            entry["hour"]: entry
            for entry in plan
        }
    except Exception:
        return ["hourly_plan contains an invalid hour entry"]

    if set(plan_by_hour.keys()) != set(range(24)):
        errors.append(
            "hourly_plan does not contain exactly hours 0-23"
        )
        return errors

    input_by_hour = {
        entry["hour"]: entry
        for entry in base_request["hours"]
    }

    constraints = build_constraints(
        base_request,
        directives
    )

    battery = base_request["battery"]

    previous_energy = battery["initial_energy_kwh"]

    recalculated_grid = 0.0
    recalculated_cost = 0.0
    recalculated_peak = 0.0

    for hour in range(24):

        input_hour = input_by_hour[hour]
        output = plan_by_hour[hour]

        grid = output["grid_kwh"]
        solar = output["solar_used_kwh"]
        action = output["battery_action"]
        battery_kwh = output["battery_kwh"]
        energy_after = output["battery_energy_after_kwh"]

        # -----------------------------------------
        # Basic non-negative checks
        # -----------------------------------------

        if grid < -TOLERANCE:
            errors.append(
                f"hour {hour}: negative grid energy"
            )

        if solar < -TOLERANCE:
            errors.append(
                f"hour {hour}: negative solar usage"
            )

        if battery_kwh < -TOLERANCE:
            errors.append(
                f"hour {hour}: negative battery magnitude"
            )

        # -----------------------------------------
        # Effective solar
        # -----------------------------------------

        effective_solar = (
            input_hour["solar_kwh"]
            * constraints["solar_factor"][hour]
        )

        if solar > effective_solar + TOLERANCE:
            errors.append(
                f"hour {hour}: solar_used={solar} "
                f"exceeds effective solar={effective_solar}"
            )

        # -----------------------------------------
        # Grid cap
        # -----------------------------------------

        cap = constraints["grid_cap"][hour]

        if grid > cap + TOLERANCE:
            errors.append(
                f"hour {hour}: grid={grid} exceeds cap={cap}"
            )

        # -----------------------------------------
        # Battery action consistency
        # -----------------------------------------

        if action not in {
            "charge",
            "discharge",
            "idle"
        }:
            errors.append(
                f"hour {hour}: invalid battery action {action}"
            )

        if action == "idle" and battery_kwh > TOLERANCE:
            errors.append(
                f"hour {hour}: idle battery has "
                f"{battery_kwh} kWh movement"
            )

        if action == "charge":

            if constraints["no_charge"][hour]:
                errors.append(
                    f"hour {hour}: charging during no-charge window"
                )

            if (
                battery_kwh
                > battery["max_charge_kwh_per_hour"]
                + TOLERANCE
            ):
                errors.append(
                    f"hour {hour}: charge rate exceeded"
                )

            charge = battery_kwh
            discharge = 0.0

        elif action == "discharge":

            if constraints["no_discharge"][hour]:
                errors.append(
                    f"hour {hour}: discharging during "
                    f"no-discharge window"
                )

            if (
                battery_kwh
                > battery["max_discharge_kwh_per_hour"]
                + TOLERANCE
            ):
                errors.append(
                    f"hour {hour}: discharge rate exceeded"
                )

            charge = 0.0
            discharge = battery_kwh

        else:
            charge = 0.0
            discharge = 0.0

        # -----------------------------------------
        # Energy balance
        # -----------------------------------------

        demand = input_hour["demand_kwh"]

        supply = grid + solar + discharge
        usage = demand + charge

        if not close_enough(supply, usage):
            errors.append(
                f"hour {hour}: energy balance failed "
                f"(supply={supply}, usage={usage})"
            )

        # -----------------------------------------
        # Battery state transition
        # -----------------------------------------

        expected_after = (
            previous_energy
            + charge
            - discharge
        )

        if not close_enough(
            expected_after,
            energy_after
        ):
            errors.append(
                f"hour {hour}: battery transition incorrect "
                f"(expected {expected_after}, got {energy_after})"
            )

        # -----------------------------------------
        # Battery capacity / reserve
        # -----------------------------------------

        required_minimum = constraints["reserve"][hour]

        if energy_after < required_minimum - TOLERANCE:
            errors.append(
                f"hour {hour}: battery energy "
                f"{energy_after} below reserve "
                f"{required_minimum}"
            )

        if (
            energy_after
            > battery["capacity_kwh"]
            + TOLERANCE
        ):
            errors.append(
                f"hour {hour}: battery capacity exceeded"
            )

        previous_energy = energy_after

        # -----------------------------------------
        # Recalculate totals
        # -----------------------------------------

        recalculated_grid += grid

        recalculated_cost += (
            grid
            * input_hour["tariff_bdt_per_kwh"]
        )

        recalculated_peak = max(
            recalculated_peak,
            grid
        )

    # ---------------------------------------------
    # End-of-day battery neutrality
    # ---------------------------------------------

    if not close_enough(
        previous_energy,
        battery["initial_energy_kwh"]
    ):
        errors.append(
            "final battery energy does not equal "
            "initial battery energy"
        )

    # ---------------------------------------------
    # Top-level totals
    # ---------------------------------------------

    if not close_enough(
        recalculated_grid,
        response["total_grid_kwh"]
    ):
        errors.append(
            "total_grid_kwh does not match hourly plan"
        )

    if not close_enough(
        recalculated_cost,
        response["total_cost_bdt"]
    ):
        errors.append(
            "total_cost_bdt does not match hourly plan"
        )

    if not close_enough(
        recalculated_peak,
        response["peak_grid_kwh"]
    ):
        errors.append(
            "peak_grid_kwh does not match hourly plan"
        )

    return errors


def main():
    cases = load_json(CASES_FILE)["cases"]

    base_request = load_json(
        SAMPLE_REQUEST_FILE
    )

    passed = 0
    failed = 0

    print()
    print("=" * 72)
    print("GRIDWISE DIRECTIVE APPLICATION EVALUATOR")
    print("=" * 72)
    print()

    for index, case in enumerate(cases, start=1):

        payload = copy.deepcopy(
            base_request
        )

        payload["scenario_id"] = case["id"]
        payload["operator_notes"] = case["operator_notes"]

        print(
            f"[{index}/{len(cases)}] "
            f"{case['id']} - "
            f"{case['description']}"
        )

        try:
            status, response, latency = call_gridwise(
                payload
            )

        except Exception as error:

            print("  FAIL")
            print(f"  Request error: {error}")
            print()

            failed += 1
            continue

        print(
            f"  HTTP {status} | {latency:.3f}s"
        )

        if status != 200:

            print("  PROVIDER/API FAILURE")
            print(
                json.dumps(
                    response,
                    indent=2
                )
            )
            print()

            failed += 1

        else:

            errors = validate_schedule(
                base_request,
                case["expected"],
                response
            )

            if errors:

                print("  FAIL")

                for error in errors:
                    print(
                        f"    - {error}"
                    )

                failed += 1

            else:

                print(
                    "  PASS - interpretation directives "
                    "were correctly applied to schedule"
                )

                passed += 1

            print()

        if index < len(cases):

            time.sleep(
                DELAY_BETWEEN_CASES_SECONDS
            )

    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)

    print(
        f"Passed: {passed}/{len(cases)}"
    )

    print(
        f"Failed: {failed}/{len(cases)}"
    )

    print("=" * 72)


if __name__ == "__main__":
    main()