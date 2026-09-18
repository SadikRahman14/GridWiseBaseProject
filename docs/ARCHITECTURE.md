# How the solution works

## Request to response

1. FastAPI receives one scenario. Pydantic validates finite numeric values, the
   battery bounds, 24 unique hours and 1-3 non-empty notes. Input hours may arrive
   unordered; they are sorted. `scenario_id` is preserved exactly.
2. The configured generative model receives the operator notes and battery data.
   `prompts.py` defines the six allowed directive types and time/number conventions.
3. Its JSON is validated against a discriminated union of exact directive shapes.
   Hours must already be sorted unique integers. Note mapping, applies/no_op
   semantics, finite values and reserve <= capacity are checked. Malformed output
   gets a bounded retry; it is never silently converted to `no_op`.
4. `directives.py` compiles the validated directives into per-hour bounds.
5. `optimizer.py` solves the whole day as one linear program.
6. `validation.py` independently replays every hour and recalculates totals.
   It does not reuse the LP constraint matrix or compiled limits.
7. Only a verified plan is returned as HTTP 200. The summary is deterministic
   text based on the actual plan; the LLM's required role is interpretation.

The production code does not read public sample outputs. The offline sample
checker and demo supply ground-truth interpretations to test scheduling alone.

## Why this LP is enough

For each hour h, use four real-valued variables:

| Symbol | Meaning | Bounds |
|---|---|---|
| g[h] | Grid energy purchased | 0 to active grid cap, or no upper cap |
| s[h] | Solar energy actually used | 0 to effective solar |
| b[h] | Signed battery flow: positive charge, negative discharge | -active discharge limit to active charge limit |
| e[h] | Battery energy after the hour | Active minimum reserve to battery capacity |

The objective is:

`min sum(g[h] * tariff[h])`

Hourly energy balance:

`g[h] + s[h] - b[h] = demand[h]`

Battery state:

`e[0] - b[0] = initial_energy`

`e[h] - e[h-1] - b[h] = 0` for h > 0

End-of-day neutrality:

`e[23] = initial_energy`

This is **96 continuous variables and 49 equality constraints**, plus variable
bounds. HiGHS is called through `scipy.optimize.linprog(method="highs")`.
It minimizes the specified objective, rather than a greedy charging heuristic.
The implementation accepts only a solver result reporting success; a timeout or
infeasible result is not described as an optimal schedule.

The statement uses a lossless battery and exactly one net action per hour.
Therefore, one signed variable directly expresses every permitted action:

- b > 0: `charge`, magnitude b.
- b < 0: `discharge`, magnitude -b.
- b = 0: `idle`, magnitude 0.

There are no separate simultaneous charge and discharge decisions to reconcile.
Binary action variables are not required under these particular rules. If you
add realistic efficiencies, charging costs or other behavior, this formulation
must be revisited; keep the judged problem unchanged.

Solar is bounded above rather than forced into use, allowing curtailment.
There is no export variable and g cannot be negative. The objective minimizes
grid cost only; peak import is reported but is not an extra optimization goal.

## Translating directives

| Directive | Constraint change |
|---|---|
| solar_reduction | Effective solar = original solar times remaining fraction |
| minimum_battery_reserve | Raise the lower bound on e[h], never below the base reserve |
| no_charge_window | Set the upper bound of b[h] to 0 |
| no_discharge_window | Set the lower bound of b[h] to 0 |
| max_grid_window | Apply an upper bound on g[h] |
| no_op | No mathematical change |

Both no-charge and no-discharge active together force b[h] = 0. Repeated grid caps
combine using the minimum cap. Repeated reserves combine using the maximum reserve.
Reserve limits apply to energy AFTER each listed hour, as defined in the statement.

### One unresolved specification detail: overlapping solar reductions

The supplied documents explain a single factor relative to original solar, but
do not explicitly specify how two solar directives covering the same hour combine.
This starter treats them as restrictions on original availability and chooses the
smallest remaining fraction. Two identical notes do not halve solar twice.

For example, factors 0.8 and 0.5 yield 0.5 times original solar, not 0.4.
This is an implementation assumption, not a quoted organizer rule. No supplied
public case depends on it. Ask organizers if their hidden cases include overlapping
solar reductions. If clarified differently, update both `directives.py` and the
independent replay in `validation.py`, with a regression test.

## Numerical behavior

- Computation and returned energy values retain floating-point precision.
- Only values within 1e-9 of zero are normalized to zero.
- Returned totals are recalculated from the returned schedule using `math.fsum`.
- Internal replay uses absolute tolerance 1e-6; the public harness uses the supplied
  statement's 0.01 tolerance.
- Do not round every energy row to 2 decimals before replay; that can accumulate
  state-of-charge or balance errors. Round only for display when desired.

## Failures and timing

| Situation | Behavior |
|---|---|
| Malformed JSON or invalid request shape | HTTP 400 with sanitized validation details |
| Model output malformed, unsupported or outside bounds | Retry inside one total time budget; then HTTP 500 |
| Provider unavailable, unauthorized or too slow | Controlled HTTP 500 without provider response body |
| Interpreted constraints infeasible | HTTP 422; no constraints are silently removed |
| Solver failure or failed final replay | Controlled HTTP 500 |
| Model unavailable at readiness check | HTTP 503 from /health |

The default model budget is 22 seconds; the overall API budget is 28 seconds,
inside the guide's 30-second deadline. The LP gets at most 2 seconds. Small
sample LPs are much faster; real inference normally dominates request time.
Repeated requests each go through the model. There is no persistent cache,
phrase table, sample-ID lookup or model-free endpoint fallback.

The provider adapters request temperature 0 and structured JSON. That improves
repeatability and formatting but cannot guarantee semantic correctness. Test live
paraphrases, half/quarter wording, reduction-by vs reduction-to, noon/midnight,
AM/PM boundaries, capacity percentages, and realistic distractors.

## Suggested finalization order

1. Run the offline demo and read one full response.
2. Run the actual model and live public cases.
3. Improve the prompt/model until interpretations are accurate and fast.
4. Test extra paraphrases using known expected directives.
5. Deploy the service and test from a different machine/network.
6. Build, run, publish and independently pull the exact Docker image.
7. Finish the repository, README and short video according to the guide.

The detailed submission checklist is in `SUBMISSION_CHECKLIST.md`.
