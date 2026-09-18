# Finish before submitting

This ZIP supplies the runnable source base. The following items depend on your
chosen model, accounts, deployment and the event's timing rules.

## Core behavior

- [ ] Understand the source and adapt it as needed; credit AI assistance and dependencies.
- [ ] Run `python -m pytest` and the offline public sample checker.
- [ ] Choose and document the actual model/provider identifier in your final README.
- [ ] Run all 10 public cases in **live** mode and review interpretation failures.
- [ ] Test unseen paraphrases and percentage/time expressions with known expected results.
- [ ] Confirm every real API call uses model-produced interpretations in the optimizer.
- [ ] Confirm no secrets, `.env`, personal data or model credentials are committed.
- [ ] Clarify overlapping solar factors with organizers if that combination is relevant.

## Public API and fallback

- [ ] Deploy one public service exposing exactly `/health` and `/optimize-energy`.
- [ ] Test it from a separate machine/network without login, VPN or manual approval.
- [ ] Keep the API, model, credentials, quota and fallback available during evaluation.
- [ ] Check health readiness within 60 seconds and request completion within 30 seconds.
- [ ] Measure p95 latency; <=5 seconds receives the best latency band in the supplied guide.
- [ ] Build and run the Dockerfile with your final provider configuration.
- [ ] Publish a pullable image with a fixed tag or digest and verify a fresh pull/run.
- [ ] Replace README registry placeholders with the actual verified image and command.

The current bundle includes a Dockerfile, not an already published or locally
verified Docker image. The service must bind to `0.0.0.0`; `run.py` already does so.

## Submission package

- [ ] Follow the official rulebook's repository creation and visibility timing:
  created after question reveal, private during the event, public after deadline.
- [ ] Submit the reachable API base URL and repository URL.
- [ ] Supply the self-contained README, environment-variable names and dependencies.
- [ ] Supply the exact Docker registry tag/digest and verified run command.
- [ ] Record an accessible solution video no longer than 3 minutes.

The supplied guide assigns 25 points to interpretation, 25 to directive and energy
correctness, 10 to cost optimization, 10 to API/schema, 10 to performance/reliability,
10 to deployment/Docker and 10 to documentation/reproduction. The video is a
tie-break item, not part of the base 100 points.

## Simple 3-minute video outline

| Time | Show |
|---|---|
| 0:00-0:30 | Campus demand, solar, changing tariffs, battery and natural-language notes |
| 0:30-1:10 | Model interpretation and deterministic guardrails |
| 1:10-1:50 | Signed battery-flow LP, hourly balance and end-of-day neutrality |
| 1:50-2:30 | A live API response and public sample checks |
| 2:30-3:00 | Setup, actual model/provider, deployment and limitations |

Use the latest organizer documents if they amend any rule. No repository,
deployment, registry image or video is created by running the offline demo.
