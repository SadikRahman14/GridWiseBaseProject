# Verification record

Verified on 2026-09-18 with Python 3.12.14 on Linux, including a newly created
virtual environment installed from the included requirements files.

## Completed checks

| Check | Result |
|---|---|
| Clean dependency installation | Passed |
| Automated suite | **95 passed** |
| Public sample optimizer checks | **10/10**, every published optimal cost matched |
| Independent replay of all supplied reference schedules | Passed |
| Small synthetic scenarios vs an independent dynamic-programming oracle | 24 cases passed, including infeasible cases |
| Strict input/model guardrails | Passed |
| Deliberately corrupted schedule detection | Passed |
| Ollama and compatible-provider request/response formats | Passed with mocked HTTP transports |
| Model retry, timeout and error-redaction behavior | Passed with simulated failures |
| Real Uvicorn process and HTTP requests | Health, 10 optimization calls, malformed input and OpenAPI passed with a local fixture provider |
| Offline demo | Passed; writes the complete calculated JSON |

Two upstream test-client deprecation warnings were emitted by the installed
Starlette/AnyIO stack. They did not affect passing tests or the HTTP smoke check.

Public cost comparison with supplied structured interpretations:

| Case | Published optimum (BDT) | Calculated optimum (BDT) |
|---|---:|---:|
| SAMPLE-01 | 38365 | 38365 |
| SAMPLE-02 | 42885 | 42885 |
| SAMPLE-03 | 35480 | 35480 |
| SAMPLE-04 | 40495 | 40495 |
| SAMPLE-05 | 33950 | 33950 |
| SAMPLE-06 | 34090 | 34090 |
| SAMPLE-07 | 38550 | 38550 |
| SAMPLE-08 | 37665 | 37665 |
| SAMPLE-09 | 34873 | 34873 |
| SAMPLE-10 | 41620 | 41620 |

The clean-environment offline sample run observed a p95 of approximately 0.006
seconds per optimizer/check call. This excludes LLM inference, network latency
and hosted concurrency, and is not a prediction of judged API latency.

## Still to verify on your final configuration

- **Actual generative-model accuracy and speed.** No running Ollama model or
  hosted model credentials were available for this build. Mocked model responses
  test integration and failures, not language understanding. Run warmup and
  `scripts/check_samples.py --mode live`, then test additional paraphrases.
- **Windows/macOS execution.** Launch scripts and instructions are included, but
  execution was verified on Linux only.
- **Docker build/run and registry pull.** Docker was unavailable in the build
  environment. The Dockerfile is supplied; no tested or published image is claimed.
- **Public deployment, hidden judge cases and evaluation-scale load.** These
  depend on the final hosting/model setup and have not been run here.
- **Overlapping solar reductions.** The current minimum-factor assumption needs
  organizer clarification if such combinations are in scope.

The starter is a tested implementation base with an implemented real-model path,
not an already deployed or fully evaluated competition submission.

## Reproduce

From the project root after installation:

```bash
python -m pytest
python scripts/check_samples.py --mode offline
python scripts/demo.py
```

With a real model configured and `python run.py` active in another terminal:

```bash
python scripts/warmup.py
python scripts/check_samples.py --mode live
```

Use your virtual environment's Python executable as shown in the README.
