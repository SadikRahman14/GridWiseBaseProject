"""Public sample harness. Live mode verifies the real API against organizer truth."""

import argparse
from contextlib import nullcontext
import json
import math
from pathlib import Path
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gridwise.models import Interpretation, PlanResponse, Scenario
from gridwise.optimizer import optimize
from gridwise.validation import validate_plan


def compare_interpretations(actual, expected):
    if len(actual) != len(expected):
        raise AssertionError("Interpretation count differs")
    for got, wanted in zip(actual, expected):
        for key in ("note_index", "applies", "directive_type"):
            if getattr(got, key) != wanted[key]:
                raise AssertionError(f"Note {wanted['note_index']}: incorrect {key}")
        ga = got.structured_adjustment.model_dump() if got.structured_adjustment else None
        wa = wanted["structured_adjustment"]
        if wa is None:
            if ga is not None:
                raise AssertionError("no_op adjustment must be null")
            continue
        if ga is None or set(ga) != set(wa) or ga["hours"] != wa["hours"]:
            raise AssertionError(f"Note {wanted['note_index']}: wrong hours or adjustment shape")
        for key in wa.keys() - {"hours"}:
            if abs(ga[key] - wa[key]) > 0.01:
                raise AssertionError(f"Note {wanted['note_index']}: incorrect {key}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["offline", "live"], default="offline")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--repeat", type=int, default=1, help="Repeat cases for a latency/stability check")
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be positive")
    cases = json.loads((ROOT / "examples/public_samples.json").read_text(encoding="utf-8"))["cases"]
    if args.mode == "offline":
        print("OFFLINE: tests optimization with organizer interpretations; LLM is not tested.")
    else:
        print("LIVE: calls the configured API; evaluates interpretation and scheduling.")
    failures, durations = [], []
    with (httpx.Client(timeout=30) if args.mode == "live" else nullcontext(None)) as client:
        if args.mode == "live":
            try:
                health = client.get(args.url.rstrip("/") + "/health")
                health.raise_for_status()
                if health.json() != {"status": "ok"}:
                    raise ValueError("Unexpected health payload")
            except (httpx.HTTPError, ValueError):
                print("Health check failed. Start the API and verify that the configured model is available.")
                return 1
        for repetition in range(args.repeat):
            for case in cases:
                if args.mode == "live":
                    time.sleep(30)
                started = time.perf_counter()
                try:
                    scenario = Scenario.model_validate(case["input"])
                    expected = case["expected_output"]
                    truth = Interpretation(directive_interpretation=expected["directive_interpretation"])
                    if args.mode == "offline":
                        plan = optimize(scenario, truth)
                    else:
                        result = client.post(args.url.rstrip("/") + "/optimize-energy", json=case["input"])
                        if result.status_code != 200:
                            raise AssertionError(f"API HTTP {result.status_code}; check local service logs/configuration")
                        plan = PlanResponse.model_validate(result.json())
                    elapsed = time.perf_counter() - started
                    durations.append(elapsed)
                    compare_interpretations(plan.directive_interpretation, expected["directive_interpretation"])
                    validate_plan(scenario, plan, ground_truth=truth, tolerance=0.01)
                    if abs(plan.total_cost_bdt - expected["total_cost_bdt"]) > 0.01:
                        raise AssertionError("Cost differs from the published optimum")
                    if args.mode == "live" and elapsed >= 30:
                        raise AssertionError("Judge's 30-second request limit exceeded")
                    print(f"PASS {case['id']} cost={plan.total_cost_bdt:.2f} BDT time={elapsed:.3f}s")
                except Exception as error:
                    failures.append(case["id"])
                    # Do not print HTTP exception messages: URLs can contain credentials.
                    detail = str(error) if isinstance(error, AssertionError) else type(error).__name__
                    print(f"FAIL {case['id']}: {detail}")
    total = len(cases) * args.repeat
    print(f"\n{total-len(failures)}/{total} checks passed.")
    if durations:
        p95 = sorted(durations)[max(0, math.ceil(0.95 * len(durations)) - 1)]
        print(f"Observed p95: {p95:.3f}s (this run only; not a hosted performance guarantee)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
