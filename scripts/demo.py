"""Offline optimizer demonstration: no LLM evaluation or server required."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gridwise.models import Interpretation, Scenario
from gridwise.optimizer import optimize


def main():
    case = json.loads((ROOT / "examples/public_samples.json").read_text(encoding="utf-8"))["cases"][0]
    scenario = Scenario.model_validate(case["input"])
    interpretation = Interpretation(directive_interpretation=case["expected_output"]["directive_interpretation"])
    response = optimize(scenario, interpretation)
    output = ROOT / "output"
    output.mkdir(exist_ok=True)
    path = output / "demo_response.json"
    path.write_text(response.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print("OFFLINE DEMO: organizer interpretations supplied directly to the optimizer.")
    print("This does not test language understanding. The API always uses a real model.")
    print(f"Scenario: {response.scenario_id}")
    print(f"Optimal cost: {response.total_cost_bdt:.2f} BDT")
    print(f"Grid energy: {response.total_grid_kwh:.2f} kWh")
    print(f"Peak grid import: {response.peak_grid_kwh:.2f} kWh")
    print(f"Final battery: {response.hourly_plan[-1].battery_energy_after_kwh:.2f} kWh")
    print(f"Full 24-hour JSON written to: {path}")


if __name__ == "__main__":
    main()
