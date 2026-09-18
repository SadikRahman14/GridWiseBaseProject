import copy
import json
import math
import time
import urllib.error
import urllib.request
from pathlib import Path


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CASES_FILE = PROJECT_ROOT / "evaluation" / "language_cases.json"

SAMPLE_REQUEST_FILE = PROJECT_ROOT / "examples" / "sample_request.json"

API_URL = "http://127.0.0.1:8000/optimize-energy"

NUMERIC_TOLERANCE = 0.01

REQUEST_TIMEOUT_SECONDS = 30

DELAY_BETWEEN_CASES_SECONDS = 2


# ---------------------------------------------------------
# Utility functions
# ---------------------------------------------------------

def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def numbers_equal(expected, actual):
    return math.isclose(
        float(expected),
        float(actual),
        abs_tol=NUMERIC_TOLERANCE,
        rel_tol=0
    )


def compare_values(expected, actual, path=""):
    """
    Recursively compare JSON-compatible values.

    Numbers are compared using the competition tolerance.
    """

    errors = []

    # Numeric comparison
    if (
        isinstance(expected, (int, float))
        and not isinstance(expected, bool)
    ):
        if not isinstance(actual, (int, float)) or isinstance(actual, bool):
            errors.append(
                f"{path}: expected number {expected}, got {actual!r}"
            )
            return errors

        if not numbers_equal(expected, actual):
            errors.append(
                f"{path}: expected {expected}, got {actual}"
            )

        return errors

    # Dictionary comparison
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            errors.append(
                f"{path}: expected object, got {type(actual).__name__}"
            )
            return errors

        for key, expected_value in expected.items():

            child_path = f"{path}.{key}" if path else key

            if key not in actual:
                errors.append(
                    f"{child_path}: missing"
                )
                continue

            errors.extend(
                compare_values(
                    expected_value,
                    actual[key],
                    child_path
                )
            )

        return errors

    # List comparison
    if isinstance(expected, list):
        if not isinstance(actual, list):
            errors.append(
                f"{path}: expected list, got {type(actual).__name__}"
            )
            return errors

        if len(expected) != len(actual):
            errors.append(
                f"{path}: expected length {len(expected)}, "
                f"got {len(actual)}"
            )
            return errors

        for index, expected_value in enumerate(expected):

            errors.extend(
                compare_values(
                    expected_value,
                    actual[index],
                    f"{path}[{index}]"
                )
            )

        return errors

    # Everything else
    if expected != actual:
        errors.append(
            f"{path}: expected {expected!r}, got {actual!r}"
        )

    return errors


# ---------------------------------------------------------
# API call
# ---------------------------------------------------------

def call_gridwise(payload):

    body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Content-Type": "application/json"
        },
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
            parsed = {
                "raw_response": body
            }

        return (
            error.code,
            parsed,
            elapsed
        )


# ---------------------------------------------------------
# Main evaluator
# ---------------------------------------------------------

def main():

    cases_data = load_json(CASES_FILE)

    base_request = load_json(SAMPLE_REQUEST_FILE)

    cases = cases_data["cases"]

    passed = 0

    failed = 0

    latencies = []

    print()
    print("=" * 70)
    print("GRIDWISE LANGUAGE INTERPRETATION EVALUATOR")
    print("=" * 70)
    print()

    for case_number, case in enumerate(cases, start=1):

        payload = copy.deepcopy(base_request)

        payload["scenario_id"] = case["id"]

        payload["operator_notes"] = case["operator_notes"]

        print(
            f"[{case_number}/{len(cases)}] "
            f"{case['id']} - {case['description']}"
        )

        try:

            status_code, response, latency = call_gridwise(
                payload
            )

            latencies.append(latency)

        except Exception as error:

            print("  FAIL")
            print(f"  Request error: {error}")
            print()

            failed += 1
            continue

        print(
            f"  HTTP {status_code} | "
            f"{latency:.3f}s"
        )

        if status_code != 200:

            print("  FAIL")
            print(
                "  API response:",
                json.dumps(
                    response,
                    indent=2
                )
            )

            print()

            failed += 1
            continue

        actual = response.get(
            "directive_interpretation"
        )

        expected = case["expected"]

        errors = compare_values(
            expected,
            actual,
            "directive_interpretation"
        )

        if not errors:

            print("  PASS")

            passed += 1

        else:

            print("  FAIL")

            failed += 1

            print()

            print("  Expected:")

            print(
                json.dumps(
                    expected,
                    indent=2
                )
            )

            print()

            print("  Received:")

            print(
                json.dumps(
                    actual,
                    indent=2
                )
            )

            print()

            print("  Differences:")

            for error in errors:
                print(
                    f"    - {error}"
                )

        print()

        # Small pause so we do not hammer the model provider.
        if case_number < len(cases):
            time.sleep(
                DELAY_BETWEEN_CASES_SECONDS
            )

    # -----------------------------------------------------
    # Final summary
    # -----------------------------------------------------

    total = len(cases)

    accuracy = (
        passed / total * 100
        if total
        else 0
    )

    print("=" * 70)

    print("SUMMARY")

    print("=" * 70)

    print(
        f"Passed:   {passed}/{total}"
    )

    print(
        f"Failed:   {failed}/{total}"
    )

    print(
        f"Accuracy: {accuracy:.1f}%"
    )

    if latencies:

        sorted_latencies = sorted(
            latencies
        )

        average_latency = (
            sum(sorted_latencies)
            / len(sorted_latencies)
        )

        p95_index = max(
            0,
            math.ceil(
                0.95 * len(sorted_latencies)
            ) - 1
        )

        p95_latency = sorted_latencies[
            p95_index
        ]

        print(
            f"Average latency: "
            f"{average_latency:.3f}s"
        )

        print(
            f"p95 latency:     "
            f"{p95_latency:.3f}s"
        )

    print("=" * 70)

    print()


if __name__ == "__main__":
    main()