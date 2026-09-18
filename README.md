
# GridWise --- LLM-Assisted Smart Campus Energy Optimization

  



```{=html}

<h1>

```

GridWise

```{=html}

</h1>

```

```{=html}

<p>

```

`<strong>`{=html}LLM-Assisted Smart Campus Energy

Optimization`</strong>`{=html}

```{=html}

</p>

```

```{=html}

<p>

```

`<img src="https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python&logoColor=white" alt="Python" />`{=html}

`<img src="https://img.shields.io/badge/FastAPI-API-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />`{=html}

`<img src="https://img.shields.io/badge/SciPy-Optimization-8CAAE6?style=flat-square&logo=scipy&logoColor=white" alt="SciPy" />`{=html}

`<img src="https://img.shields.io/badge/Docker-Container-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker" />`{=html}

`<img src="https://img.shields.io/badge/Render-Deployed-46E3B7?style=flat-square&logo=render&logoColor=black" alt="Render" />`{=html}

```{=html}

</p>

```

:::

  

------------------------------------------------------------------------

  

### Table of Contents

  

[Project Description](#project-description) - [Features](#features) -

[Objectives](#objectives) - [Target Scenario](#target-scenario) -

[Architecture](#architecture) - [Supported

Directives](#supported-directives) - [API Endpoints](#api-endpoints) -

[Technologies Used](#technologies-used) -

[Installation](#installation) - [Testing](#testing) -

[Deployment](#deployment) - [Project Structure](#project-structure) -

[Team Members](#team-members) - [References](#references)

  

------------------------------------------------------------------------

  

## 📝 Project Description `<a id="project-description">`{=html}`</a>`{=html}

  

**GridWise** is an LLM-assisted smart campus energy optimization service

developed for the **BUP CSE Fest 2026 Hackathon**.

  

The system receives a 24-hour energy scenario containing campus

electricity demand, rooftop solar availability, time-varying grid

tariffs, battery parameters, and short natural-language operator notes.

  

The main challenge is to transform human-written operating instructions

into reliable, machine-checkable constraints. GridWise uses a

language-capable generative model to interpret the operator notes,

deterministic guardrails to validate the interpretation, and a

mathematical optimizer to generate a valid low-cost 24-hour energy

schedule.

  

The LLM is therefore part of the actual operator-note interpretation

path. It does not directly generate the final energy schedule.

  

The official challenge requires the service to accept a 24-hour scenario

and return both a machine-checkable interpretation of the operator notes

and the final 24-hour schedule.

  

## 💡 Project Features `<a id="features">`{=html}`</a>`{=html}

  

i. **LLM-Based Operator Note Interpretation**

- Interprets natural-language energy instructions.

- Handles different ways of expressing the same directive.

- Produces structured directive information for downstream

processing.

ii. **Deterministic Guardrails**

  

- Validates the LLM output before it reaches the optimizer.

- Checks directive type, note mapping, hours, numeric ranges, and

`applies` semantics.

- Rejects malformed or unsupported interpretations instead of silently

modifying them.

  

iii. **24-Hour Energy Optimization**

  

- Optimizes grid electricity usage over exactly 24 hourly intervals.

- Minimizes total grid electricity cost after all applicable

constraints are satisfied.

- Uses linear programming with SciPy/HiGHS.

  

iv. **Battery Energy Management**

  

- Supports battery charging and discharging.

- Enforces battery capacity and minimum reserve constraints.

- Enforces hourly charge/discharge limits.

- Maintains end-of-day battery neutrality.

  

v. **Solar Energy Management**

- Uses available rooftop solar to reduce grid purchases.

- Supports temporary solar-reduction directives.

- Allows solar curtailment when generation exceeds useful demand/storage capacity.

- Does not model grid export.



vi. **Independent Schedule Validation**

  

- Replays the final schedule after optimization.

- Verifies energy balance, battery state transitions, solar limits,

grid caps, directive constraints, and reported metrics.

- Returns the final result only after validation succeeds.

  

vii. **Public HTTP API**

  

-  `GET /health` for service readiness.

-  `POST /optimize-energy` for the complete optimization workflow.

- FastAPI Swagger documentation available through `/docs`.

  

## 🎯 Objectives `<a id="objectives">`{=html}`</a>`{=html}

  

-  **Understand Operator Instructions:** Convert natural-language

operator notes into structured energy directives.

-  **Ensure Correctness:** Validate model-generated directives using

deterministic guardrails.

-  **Optimize Energy Cost:** Minimize total grid electricity cost while

satisfying all applicable constraints.

-  **Maintain Feasibility:** Produce schedules that satisfy energy,

battery, solar, and operator-directive rules.

-  **Verify the Final Plan:** Independently replay and validate the

generated schedule before returning it.

-  **Provide a Reproducible API:** Offer a simple HTTP interface that

can be run locally, through Docker, or as a public deployment.

  

## 🏫 Target Scenario `<a id="target-scenario">`{=html}`</a>`{=html}

  

BUP operates a smart campus using:

  

- Grid electricity

- Rooftop solar generation

- Battery energy storage

- Time-varying electricity tariffs

- A 24-hour forecast of campus demand

  

Campus operators may also provide **1--3 natural-language notes**

describing temporary conditions affecting the same 24-hour schedule.

  

For example:

  

> "Solar output will drop to about 20% from 1 PM to 3 PM."

  

The system should interpret this as a `solar_reduction` directive.

  

Another example:

  

> "Do not charge the battery between 2 PM and 4 PM."

  

The system should interpret this as a `no_charge_window` directive.

  

An irrelevant note should be classified as:

  

``` text

no_op

```

  

rather than being converted into an invented energy constraint.

  

## 🏗️ Architecture 

  

``` mermaid

flowchart LR

A[24-Hour JSON Scenario] --> B[FastAPI / Pydantic]

B --> C[LLM Operator-Note Interpretation]

C --> D[Deterministic Guardrails]

D --> E[Directive Constraints]

E --> F[SciPy / HiGHS Optimizer]

F --> G[Independent Schedule Replay]

G --> H[Verified JSON Response]

```

  

### End-to-End Flow

  

``` text

Client

|

| POST /optimize-energy

v

Request Validation

|

v

LLM Interpretation

|

v

Deterministic Guardrails

|

v

Directive Application

|

v

24-Hour Linear Optimization

|

v

Independent Schedule Replay

|

v

Structured JSON Response

```

  

The core design principle is:

  

``` text

Human language

↓

LLM interpretation

↓

Deterministic validation

↓

Mathematical optimization

↓

Independent verification

```

  

The LLM is not trusted to directly produce the final schedule.

  

## 📌 Supported Directives 

  

-----------------------------------------------------------------------

Directive Description

----------------------------------- -----------------------------------

`solar_reduction` Reduces usable solar during

specified hours.

  

`minimum_battery_reserve` Keeps battery energy at or above a

required level.

  

`no_charge_window` Prevents battery charging during

specified hours.

  

`no_discharge_window` Prevents battery discharging during

specified hours.

  

`max_grid_window` Limits grid import during specified

hours.

  

`no_op` Indicates that a note does not

affect the current schedule.

-----------------------------------------------------------------------

  

### Directive Examples

  

``` text

"Solar output will drop to about 20% from 1 PM to 3 PM."

→ solar_reduction

→ hours: [13, 14]

→ factor: 0.2

```

  

``` text

"Do not charge the battery between 2 PM and 4 PM."

→ no_charge_window

→ hours: [14, 15]

```

  

``` text

"Keep at least 120 kWh in reserve from 6 PM until 9 PM."

→ minimum_battery_reserve

→ hours: [18, 19, 20]

→ minimum_energy_kwh: 120

```

  

Time intervals use a start-inclusive, end-exclusive convention.

  

``` text

1 PM to 3 PM → [13, 14]

10 PM to midnight → [22, 23]

```

  

For `solar_reduction`, the factor represents the usable fraction that

remains:

  

``` text

80% reduction → factor = 0.20

60% reduction → factor = 0.40

```

  

## 📜 API Endpoints `<a id="api-endpoints">`{=html}`</a>`{=html}

  

### Health

  

-  **GET `/health`**: Returns service readiness status.

  

Expected response:

  

``` json

{

"status": "ok"

}

```

  

### Energy Optimization

  

-  **POST `/optimize-energy`**: Accepts one 24-hour energy scenario and

returns the interpreted directives and optimized schedule.

  

The request contains:

  

``` text

scenario_id

operator_notes

hours

battery

```

  

The `hours` array must contain exactly 24 entries for hours `0` through

`23`.

  

### API Documentation

  

FastAPI automatically provides interactive Swagger documentation:

  

``` text

/docs

```

  

Local:

  

``` text

http://127.0.0.1:8000/docs

```

  

Production:

  

``` text

https://gridwisebaseproject.onrender.com/docs

```

  

## ⚙️ Optimization Model

  

For every hour, GridWise manages:

  

- Grid electricity

- Solar energy

- Battery charge/discharge

- Battery state of charge

  

The primary objective is:

  

``` text

Minimize:

  

Σ(grid_kwh[h] × tariff_bdt_per_kwh[h])

```

  

subject to all energy and operator constraints.

  

### Energy Balance

  

``` text

grid_kwh

+ solar_used_kwh

+ battery_discharge_kwh

=

demand_kwh

+ battery_charge_kwh

```

  

### Battery

  

``` text

minimum_energy_kwh

≤

battery_energy_after_kwh

≤

capacity_kwh

```

  

The battery must also respect hourly charging and discharging limits.

  

### End-of-Day Neutrality

  

``` text

battery_energy_after_hour_23

=

initial_energy_kwh

```

  

This ensures the initial battery energy cannot be treated as free energy

by ending the day with a lower battery state.

  

## 🛡️ Validation & Guardrails

  

The LLM output is treated as untrusted structured data.

  

GridWise validates:

  

- One interpretation for every operator note.

- Correct `note_index` mapping.

- Supported directive types.

- Correct `applies` semantics.

- Unique hours.

- Hours within `0–23`.

- Ascending hour ordering.

- Valid solar reduction factors.

- Valid battery reserve values.

- Valid grid-cap values.

- Required `structured_adjustment` shapes.

- No unauthorized changes to demand, tariffs, or battery parameters.

  

Only `no_op` may use:

  

``` text

applies = false

```

  

All other supported directives must use:

  

``` text

applies = true

```

  

## 🔍 Independent Schedule Verification

  

After optimization, the final schedule is independently replayed.

  

The validator checks:

  

- Hourly energy balance.

- Solar availability.

- Battery state transitions.

- Battery capacity.

- Minimum battery reserve.

- Charge/discharge limits.

- No-charge windows.

- No-discharge windows.

- Maximum grid limits.

- Non-negative values.

- End-of-day battery neutrality.

- Total grid energy.

- Total cost.

- Peak grid usage.

  

A low-cost schedule is not accepted if it violates any hard constraint.

  

## 💻 Technologies Used `<a id="technologies-used">`{=html}`</a>`{=html}

  

-  **Programming Language:**

`<img alt="Python" src="https://img.shields.io/badge/-Python-3776AB?style=flat-square&logo=python&logoColor=white" />`{=html}

-  **Backend API:**

`<img alt="FastAPI" src="https://img.shields.io/badge/-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" />`{=html}

-  **Data Validation:**

`<img alt="Pydantic" src="https://img.shields.io/badge/-Pydantic-E92063?style=flat-square&logo=pydantic&logoColor=white" />`{=html}

-  **Optimization:**

`<img alt="SciPy" src="https://img.shields.io/badge/-SciPy-8CAAE6?style=flat-square&logo=scipy&logoColor=white" />`{=html}

-  **LP Solver:**

`<img alt="HiGHS" src="https://img.shields.io/badge/-HiGHS-Optimization-blue?style=flat-square" />`{=html}

-  **LLM:** Ollama / OpenAI-compatible Chat Completions API

-  **ASGI Server:**

`<img alt="Uvicorn" src="https://img.shields.io/badge/-Uvicorn-499848?style=flat-square" />`{=html}

-  **Containerization:**

`<img alt="Docker" src="https://img.shields.io/badge/-Docker-2496ED?style=flat-square&logo=docker&logoColor=white" />`{=html}

-  **Deployment:**

`<img alt="Render" src="https://img.shields.io/badge/-Render-46E3B7?style=flat-square&logo=render&logoColor=black" />`{=html}

-  **Version Control:**

`<img alt="Git" src="https://img.shields.io/badge/-Git-F05032?style=flat-square&logo=git&logoColor=white" />`{=html}

-  **Repository:**

`<img alt="GitHub" src="https://img.shields.io/badge/-GitHub-181717?style=flat-square&logo=github&logoColor=white" />`{=html}

  

## 🚧 Installation 

  

### Prerequisites

  

- Python 3.12 recommended

- Git

- pip

- Ollama for local LLM execution, or a compatible hosted LLM provider

- Docker (optional)

  

### Clone the Repository

  

``` bash

git  clone  YOUR_GITHUB_REPOSITORY_URL

cd  GridWiseBaseProject

```

  

### Create a Virtual Environment

  

#### Windows

  

``` powershell

py -3.12  -m venv .venv

.venv\Scripts\python.exe  -m pip install -r requirements-dev.txt

```

  

#### Linux / macOS

  

``` bash

python3.12  -m  venv  .venv

.venv/bin/python  -m  pip  install  -r  requirements-dev.txt

```

  

### Configure Environment Variables

  

Copy the example environment file:

  

#### Windows

  

``` powershell

Copy-Item .env.example .env

```

  

#### Linux / macOS

  

``` bash

cp  .env.example  .env

```

  

Example local Ollama configuration:

  

``` dotenv

LLM_PROVIDER=ollama

LLM_BASE_URL=http://127.0.0.1:11434

LLM_MODEL=qwen2.5:3b

LLM_API_KEY=

LLM_TIMEOUT_SECONDS=22

LLM_RETRIES=1

PORT=8000

```

  

Pull the model:

  

``` bash

ollama  pull  qwen2.5:3b

```

  

**Do not commit `.env` or API keys to GitHub.**

  

### Run the Application

  

``` bash

python  run.py

```

  

The local service will be available at:

  

``` text

http://127.0.0.1:8000

```

  

## 🧪 Testing `<a id="testing">`{=html}`</a>`{=html}

  

### Run the Demo

  

Windows:

  

``` powershell

.venv\Scripts\python.exe scripts\demo.py

```

  

Linux/macOS:

  

``` bash

.venv/bin/python  scripts/demo.py

```

  

### Public Sample Verification

  

``` bash

python  scripts/check_samples.py  --mode  offline

```

  

### Automated Tests

  

``` bash

python  -m  pytest

```

  

### Live Model Verification

  

``` bash

python  scripts/check_samples.py  --mode  live

```

  

### Language Evaluation

  

``` bash

python  evaluation/eval_language.py

```

  

The language evaluation covers directive interpretation, paraphrased

operator notes, time expressions, solar reductions, battery reserves,

charge/discharge windows, grid limits, and irrelevant notes.

  

## 🌐 Deployment 

  

GridWise is deployed as a public HTTP service.

  

### Live Project

  

**Live API:** <https://gridwisebaseproject.onrender.com/>

  

### Health Check

  

``` text

GET https://gridwisebaseproject.onrender.com/health

```

  

Expected:

  

``` json

{

"status": "ok"

}

```

  

### Main API

  

``` text

POST https://gridwisebaseproject.onrender.com/optimize-energy

```

  

### Swagger UI

  

``` text

https://gridwisebaseproject.onrender.com/docs

```

  

### Thunder Client

  

Use the following request in Thunder Client:

  

``` text

Method: GET

URL: https://gridwisebaseproject.onrender.com/health

```

  

For optimization:

  

``` text

Method: POST

URL: https://gridwisebaseproject.onrender.com/optimize-energy

Content-Type: application/json

```

  

Use the complete JSON from:

  

``` text

examples/sample_request.json

```

  

### Render Configuration

  

The service uses the project's Dockerfile for deployment.

  

The deployed application must:

  

- Bind to `0.0.0.0`.

- Use the platform-provided `PORT`.

- Expose `/health`.

- Expose `/optimize-energy`.

- Keep the configured LLM provider available during evaluation.

  

For hosted LLM deployment, configure the following through Render

environment variables:

  

``` text

LLM_PROVIDER

LLM_BASE_URL

LLM_MODEL

LLM_API_KEY

LLM_TIMEOUT_SECONDS

LLM_RETRIES

PORT

```

  

Never place secret values in the README, Dockerfile, source code, or

GitHub repository.

  

## 📁 Project Structure 

  

``` text

GridWiseBaseProject/

│

├── gridwise/

│ ├── api.py

│ ├── directives.py

│ ├── llm.py

│ ├── models.py

│ ├── optimizer.py

│ ├── prompts.py

│ ├── settings.py

│ └── validation.py

│

├── evaluation/

│ ├── language_cases.json

│ └── eval_language.py

│

├── examples/

│ ├── sample_request.json

│ └── sample_reference_response.json

│

├── scripts/

│ ├── demo.py

│ ├── check_samples.py

│ └── warmup.py

│

├── tests/

│

├── docs/

│

├── run.py

├── Dockerfile

├── requirements.txt

├── requirements-dev.txt

├── .env.example

└── README.md

```

  

## 🐳 Docker

  

### Build

  

``` bash

docker  build  -t  gridwise:1.0.0  .

```

  

### Run

  

``` bash

docker  run  --rm  \

-p 8000:8000 \

--env-file  .env  \

gridwise:1.0.0

```

  

### Test

  

``` bash

curl  http://127.0.0.1:8000/health

```

  

The Docker image must not contain:

  

- API keys

- Access tokens

- Passwords

-  `.env`

- Private credentials

- Secret provider configuration

  

## ⚠️ Known Limitations

  

- LLM interpretation quality depends on the selected model/provider.

- Hosted LLM providers introduce latency, quota, rate-limit, and availability dependencies.

- Grid export is not modeled.

- The optimizer is designed for the challenge's 24-hour planning horizon.

- There is no automatic non-LLM fallback interpreter.

- Peak grid usage is reported but is not a secondary optimization objective.

  

## 👷 Team Members 

  

**ID**  **Name**  **Email**  **GitHub**  **Role**

-------- ------------------- ----------- ------------ -----------

--- **Team Member 1** --- KM Hasibur Rahman --- Lead

--- **Team Member 2** --- Sadik Rahman --- Developer

--- **Team Member 3** --- Kazi Kamruddin Ahmed --- Tester


  

## 📚 References 

  

1. **BUP CSE Fest 2026 Hackathon --- Preliminary Problem Statement:

GridWise LLM**

2.  **BUP CSE Fest 2026 --- Participant Guide & Evaluation Rubric**

3. FastAPI

4. Pydantic

5. SciPy / HiGHS

6. Uvicorn

7. Docker

8. Render

  

## ✔️ Live Project 

  

**Live API:** [GRIDWISE](https://gridwisebaseproject.onrender.com/)

  

**API Documentation:** [SWAGGERUI](https://gridwisebaseproject.onrender.com/docs)

  

**API Docs Check:**[Docs](https://gridwisebaseproject.onrender.com/docs)

  

------------------------------------------------------------------------
