import argparse
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

API_BASE = "http://127.0.0.1:8000"

HEALTH_URL = f"{API_BASE}/health"
OPTIMIZE_URL = f"{API_BASE}/optimize-energy"

REQUEST_TIMEOUT = 30


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def percentile(values, percent):
    if not values:
        return 0.0

    values = sorted(values)

    index = max(
        0,
        math.ceil(percent * len(values)) - 1
    )

    return values[index]


def check_health():
    started = time.perf_counter()

    try:
        with urllib.request.urlopen(
            HEALTH_URL,
            timeout=10
        ) as response:

            body = json.loads(
                response.read().decode("utf-8")
            )

            latency = time.perf_counter() - started

            return (
                response.status == 200
                and body.get("status") == "ok",
                latency
            )

    except Exception:
        return False, time.perf_counter() - started


def call_optimize(payload):
    body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        OPTIMIZE_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    started = time.perf_counter()

    try:
        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT
        ) as response:

            raw = response.read().decode("utf-8")
            latency = time.perf_counter() - started

            return (
                response.status,
                json.loads(raw),
                latency
            )

    except urllib.error.HTTPError as error:
        latency = time.perf_counter() - started

        body = error.read().decode(
            "utf-8",
            errors="replace"
        )

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"raw_response": body}

        return error.code, parsed, latency

    except Exception as error:
        latency = time.perf_counter() - started

        return (
            0,
            {"error": str(error)},
            latency
        )


def response_looks_valid(payload, response):
    required_fields = {
        "scenario_id",
        "directive_interpretation",
        "hourly_plan",
        "total_grid_kwh",
        "total_cost_bdt",
        "peak_grid_kwh",
        "plan_summary",
    }

    if not isinstance(response, dict):
        return False

    if not required_fields.issubset(response.keys()):
        return False

    if response["scenario_id"] != payload["scenario_id"]:
        return False

    if len(response["hourly_plan"]) != 24:
        return False

    if len(response["directive_interpretation"]) != len(
        payload["operator_notes"]
    ):
        return False

    return True


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--requests",
        type=int,
        default=20
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=5.0
    )

    args = parser.parse_args()

    cases = load_json(CASES_FILE)["cases"]
    base_request = load_json(SAMPLE_REQUEST_FILE)

    print()
    print("=" * 72)
    print("GRIDWISE PERFORMANCE & RELIABILITY TEST")
    print("=" * 72)

    print(
        f"Requests: {args.requests}"
    )

    print(
        f"Delay:    {args.delay:.1f}s"
    )

    print()

    # -------------------------------------------------
    # Initial health check
    # -------------------------------------------------

    healthy, health_latency = check_health()

    print(
        f"Initial /health: "
        f"{'PASS' if healthy else 'FAIL'} "
        f"({health_latency:.3f}s)"
    )

    if not healthy:
        print("Server is not ready.")
        return

    print()

    latencies = []

    successful = 0
    failed = 0
    schema_failures = 0

    interpretation_failures = 0
    other_failures = 0

    for i in range(args.requests):

        case = cases[i % len(cases)]

        payload = copy.deepcopy(base_request)

        payload["scenario_id"] = (
            f"STRESS-{i + 1:03d}"
        )

        payload["operator_notes"] = (
            case["operator_notes"]
        )

        status, response, latency = call_optimize(
            payload
        )

        latencies.append(latency)

        prefix = (
            f"[{i + 1}/{args.requests}]"
        )

        if status == 200:

            if response_looks_valid(
                payload,
                response
            ):
                print(
                    f"{prefix} PASS "
                    f"{latency:.3f}s"
                )

                successful += 1

            else:
                print(
                    f"{prefix} SCHEMA FAIL "
                    f"{latency:.3f}s"
                )

                failed += 1
                schema_failures += 1

        else:

            failed += 1

            code = None

            if isinstance(response, dict):
                error = response.get("error")

                if isinstance(error, dict):
                    code = error.get("code")

            if code == "interpretation_failed":

                interpretation_failures += 1

                print(
                    f"{prefix} PROVIDER/LLM FAIL "
                    f"HTTP {status} "
                    f"{latency:.3f}s"
                )

            else:

                other_failures += 1

                print(
                    f"{prefix} API FAIL "
                    f"HTTP {status} "
                    f"{latency:.3f}s"
                )

        if (
            i < args.requests - 1
            and args.delay > 0
        ):
            time.sleep(args.delay)

    print()

    # -------------------------------------------------
    # Final health check
    # -------------------------------------------------

    final_healthy, final_health_latency = check_health()

    print(
        f"Final /health: "
        f"{'PASS' if final_healthy else 'FAIL'} "
        f"({final_health_latency:.3f}s)"
    )

    print()

    # -------------------------------------------------
    # Statistics
    # -------------------------------------------------

    p50 = percentile(latencies, 0.50)
    p95 = percentile(latencies, 0.95)

    average = (
        sum(latencies) / len(latencies)
        if latencies
        else 0
    )

    maximum = (
        max(latencies)
        if latencies
        else 0
    )

    success_rate = (
        successful / args.requests * 100
        if args.requests
        else 0
    )

    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)

    print(
        f"Successful:             "
        f"{successful}/{args.requests}"
    )

    print(
        f"Failed:                 "
        f"{failed}/{args.requests}"
    )

    print(
        f"Success rate:           "
        f"{success_rate:.1f}%"
    )

    print(
        f"Provider/LLM failures: "
        f"{interpretation_failures}"
    )

    print(
        f"Schema failures:        "
        f"{schema_failures}"
    )

    print(
        f"Other failures:         "
        f"{other_failures}"
    )

    print()

    print(
        f"Average latency:        "
        f"{average:.3f}s"
    )

    print(
        f"p50 latency:            "
        f"{p50:.3f}s"
    )

    print(
        f"p95 latency:            "
        f"{p95:.3f}s"
    )

    print(
        f"Maximum latency:        "
        f"{maximum:.3f}s"
    )

    print()

    if p95 <= 5:
        print(
            "Latency target:         "
            "PASS (p95 <= 5s)"
        )

    elif p95 <= 15:
        print(
            "Latency target:         "
            "PARTIAL (5s < p95 <= 15s)"
        )

    elif p95 <= 30:
        print(
            "Latency target:         "
            "WEAK (15s < p95 <= 30s)"
        )

    else:
        print(
            "Latency target:         "
            "FAIL (>30s)"
        )

    print("=" * 72)
    print()


if __name__ == "__main__":
    main()