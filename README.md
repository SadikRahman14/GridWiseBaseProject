# GridWise: LLM-Assisted Smart Campus Energy Optimization

![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?style=flat-square&logo=fastapi&logoColor=white)
![SciPy](https://img.shields.io/badge/SciPy-Optimization-8CAAE6?style=flat-square&logo=scipy&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Container-2496ED?style=flat-square&logo=docker&logoColor=white)
![Render](https://img.shields.io/badge/Render-Deployed-46E3B7?style=flat-square&logo=render&logoColor=black)

---

## Executive Summary

**GridWise** is an LLM-assisted smart campus energy optimization system engineered for the **BUP CSE Fest 2026 Hackathon**. 

The system evaluates a 24-hour campus energy profile comprising electricity demand, rooftop solar availability, time-of-use tariffs, battery constraints, and short, natural-language operator notes. By interpreting operator instructions using a Large Language Model (LLM) constrained by deterministic validation guardrails, GridWise constructs a linear programming model to compute an optimal, lowest-cost 24-hour energy dispatch schedule.

---

## Table of Contents

- [Project Description](#-project-description)
- [Key Features](#-key-features)
- [Objectives](#-objectives)
- [Target Scenario](#-target-scenario)
- [System Architecture](#-system-architecture)
- [Supported Directives](#-supported-directives)
- [API Endpoints](#-api-endpoints)
- [Optimization Model](#-optimization-model)
- [Validation & Guardrails](#-validation--guardrails)
- [Independent Verification](#-independent-schedule-verification)
- [Tech Stack](#-technologies-used)
- [Installation & Local Setup](#-installation)
- [Testing & Quality Assurance](#-testing)
- [Deployment](#-deployment)
- [Project Structure](#-project-structure)
- [Docker Deployment](#-docker)
- [Known Limitations](#-known-limitations)
- [Team Members](#-team-members)
- [References](#-references)

---

## 📝 Project Description

In smart campus microgrids, human operators frequently introduce real-time operational constraints using informal natural language (e.g., maintaining battery reserves for maintenance or adjusting solar output due to weather events). Translating these unstructured notes into machine-executable parameters is prone to interpretation errors.

**GridWise** solves this challenge by integrating an LLM directly into the operator-note interpretation pipeline. The LLM parses natural language notes into structured energy directives. These directives are then verified through deterministic guardrails before being passed to a deterministic solver (SciPy HiGHS LP solver). The LLM is strictly used for linguistic interpretation and does not directly calculate energy quantities or schedules.

---

## 💡 Key Features

1. **LLM-Based Directive Interpretation:** Translates varied natural-language operational notes into structured JSON constraints.
2. **Deterministic Guardrails:** Validates LLM outputs against strict schemas, numeric bounds, and logic rules prior to optimization, rejecting malformed data.
3. **24-Hour Energy Cost Minimization:** Formulates and solves a 24-interval Linear Programming (LP) model to minimize electricity costs using SciPy/HiGHS.
4. **Battery Energy Storage Management:** Optimizes charge/discharge cycles while respecting state-of-charge (SoC) bounds, rate limits, and end-of-day neutrality constraints.
5. **Solar Yield Optimization:** Integrates rooftop solar availability with support for solar curtailment and directive-based temporary reductions.
6. **Post-Optimization Verification Replay:** Independently simulates and validates the generated schedule against physical and directive constraints prior to client delivery.
7. **Production REST API:** High-performance FastAPI application featuring automated OpenAPI/Swagger documentation, health checks, and structured error handling.

---

## 🎯 Objectives

- **Natural Language Parsing:** Convert unstructured human operational notes into standardized JSON energy directives.
- **Guaranteed System Safety:** Eliminate LLM hallucinations or improper directives through rigid validation guardrails.
- **Cost Minimization:** Solve for minimal grid electricity expenditure while honoring all physical and operational constraints.
- **Physical Feasibility:** Ensure energy conservation, battery conservation laws, solar generation caps, and tariff schedules are met.
- **Independent Verification:** Perform continuous post-optimization sanity checking on all response payloads.

---

## 🏫 Target Scenario

Consider a smart campus equipped with:
- Grid connection subject to dynamic time-of-use tariffs.
- Rooftop photovoltaic solar array.
- Battery Energy Storage System (BESS).
- Predicted 24-hour load/demand profile.

Campus engineers provide 1 to 3 natural-language notes to describe temporary real-time conditions.

### Examples:
- *"Solar output will drop to about 20% from 1 PM to 3 PM."*  
  $\rightarrow$ **Directive:** `solar_reduction` | **Hours:** $[13, 14]$ | **Factor:** $0.20$
- *"Do not charge the battery between 2 PM and 4 PM."*  
  $\rightarrow$ **Directive:** `no_charge_window` | **Hours:** $[14, 15]$
- *"Please keep at least 120 kWh in reserve from 6 PM to 9 PM."*  
  $\rightarrow$ **Directive:** `minimum_battery_reserve` | **Hours:** $[18, 19, 20]$ | **Reserve:** $120\text{ kWh}$
- *"Note: Standard operations today."*  
  $\rightarrow$ **Directive:** `no_op` | **Applies:** `false`

---

## 🏗️ System Architecture

```mermaid
flowchart LR
    A[24-Hour Scenario JSON] --> B[FastAPI / Pydantic]
    B --> C[LLM Operator-Note Parser]
    C --> D[Deterministic Guardrails]
    D --> E[Structured Directives]
    E --> F[SciPy / HiGHS LP Solver]
    F --> G[Independent Schedule Verifier]
    G --> H[Validated Response JSON]
```

### Processing Pipeline

```
[ Client Request ]
       │
       ▼
[ Schema Validation (Pydantic) ]
       │
       ▼
[ LLM Natural Language Parser ]
       │
       ▼
[ Deterministic Guardrail Check ]
       │
       ▼
[ LP Problem Formulation ]
       │
       ▼
[ SciPy HiGHS Execution ]
       │
       ▼
[ Independent Feasibility Replay ]
       │
       ▼
[ Client JSON Response ]
```

---

## 📌 Supported Directives

| Directive Type | Description | Key Parameters |
| :--- | :--- | :--- |
| `solar_reduction` | Scales usable solar generation during specified hours. | `hours`, `factor` ($0.0 - 1.0$) |
| `minimum_battery_reserve` | Enforces a higher minimum battery state-of-charge. | `hours`, `minimum_energy_kwh` |
| `no_charge_window` | Prohibits battery charging during specified hours. | `hours` |
| `no_discharge_window` | Prohibits battery discharging during specified hours. | `hours` |
| `max_grid_window` | Caps grid import power/energy during specified hours. | `hours`, `max_grid_kw` |
| `no_op` | Denotes operational notes with no energy impact. | `applies = false` |

> **Interval Convention:** Time bounds follow a start-inclusive, end-exclusive rule ($[\text{start}, \text{end})$).  
> *Example:* 1 PM to 3 PM maps to hours $[13, 14]$.

---

## 📜 API Endpoints

### Health Check
- **`GET /health`**
  - **Description:** Verifies service readiness and backend functionality.
  - **Response:** `{"status": "ok"}`

### Energy Optimization
- **`POST /optimize-energy`**
  - **Description:** Receives a complete 24-hour scenario payload, executes note interpretation, runs optimization, verifies results, and returns the final schedule.

### Documentation
- **Swagger UI:** `/docs` (Interactive testing interface)
- **ReDoc:** `/redoc`

---

## ⚙️ Optimization Model

The system solves a bounded Linear Program over discrete hourly intervals $h \in \{0, 1, \dots, 23\}$.

### Objective Function
Minimize total energy cost across the 24-hour horizon:

$$\min \sum_{h=0}^{23} \left( \text{grid\_kwh}[h] \times \text{tariff\_bdt\_per\_kwh}[h] \right)$$

### Constraints

1. **Power Balance (Hourly):**
   $$\text{grid\_kwh}[h] + \text{solar\_used\_kwh}[h] + \text{battery\_discharge\_kwh}[h] = \text{demand\_kwh}[h] + \text{battery\_charge\_kwh}[h]$$

2. **Solar Availability:**
   $$0 \le \text{solar\_used\_kwh}[h] \le \text{solar\_available\_kwh}[h] \times \text{reduction\_factor}[h]$$

3. **Battery Dynamics & Capacity:**
   $$\text{SoC}[h] = \text{SoC}[h-1] + \text{battery\_charge\_kwh}[h] - \text{battery\_discharge\_kwh}[h]$$
   $$\text{minimum\_energy\_kwh}[h] \le \text{SoC}[h] \le \text{capacity\_kwh}$$

4. **Rate Limits:**
   $$0 \le \text{battery\_charge\_kwh}[h] \le \text{max\_charge\_rate\_kw}$$
   $$0 \le \text{battery\_discharge\_kwh}[h] \le \text{max\_discharge\_rate\_kw}$$

5. **End-of-Day Neutrality:**
   $$\text{SoC}[23] = \text{initial\_energy\_kwh}$$

---

## 🛡️ Validation & Guardrails

To eliminate non-deterministic LLM behavior, outputs must pass validation rules before entering the LP solver:

- Strict mapping of response elements to original `note_index` references.
- Structural checking of `structured_adjustment` metadata payload.
- Hour array sanity checks ($h \in [0, 23]$, strictly ascending, no duplicates).
- Bounds verification: $0.0 \le \text{factor} \le 1.0$ for solar reductions; non-negative energy thresholds for battery/grid caps.
- Enforced boolean flag alignment: `applies = false` permitted only for `no_op`.

---

## 🔍 Independent Schedule Verification

Before sending the JSON response to the user, a separate validator replays the generated schedule hour by hour to verify that:

1. Hourly energy conservation balances precisely.
2. Battery state transitions obey SoC limits and rate bounds.
3. No directive constraints (e.g., charge blocks, grid caps) are breached.
4. Total grid energy usage, peak power demand, and total financial cost match the calculated optimization output.

---

## 💻 Technologies Used

- **Language:** Python 3.12
- **Framework:** FastAPI, Uvicorn
- **Data Validation:** Pydantic v2
- **Optimization:** SciPy (`scipy.optimize.linprog` HiGHS solver)
- **LLM Integration:** Ollama / OpenAI-compatible Chat Completions API
- **Containerization:** Docker
- **Deployment:** Render Platform

---

## 🚧 Installation

### Prerequisites
- Python 3.12+
- Git
- Ollama (for local LLM inference) or API keys for a hosted provider

### Setup Instructions

```bash
# 1. Clone the repository
git clone https://github.com/YourRepo/GridWiseBaseProject.git
cd GridWiseBaseProject

# 2. Create and activate a virtual environment
# Linux/macOS:
python3.12 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell):
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements-dev.txt

# 4. Environment Configuration
cp .env.example .env
```

### Sample `.env` Configuration
```dotenv
LLM_PROVIDER=ollama
LLM_BASE_URL=http://127.0.0.1:11434
LLM_MODEL=qwen2.5:3b
LLM_API_KEY=
LLM_TIMEOUT_SECONDS=22
LLM_RETRIES=1
PORT=8000
```

---

## 🧪 Testing

```bash
# Run unit tests and system tests
pytest

# Execute demo simulation
python scripts/demo.py

# Run offline schema checks
python scripts/check_samples.py --mode offline

# Run full evaluation suite against live LLM model
python evaluation/eval_language.py
```

---

## 🌐 Deployment

- **Live Service URL:** [https://gridwisebaseproject.onrender.com/](https://gridwisebaseproject.onrender.com/)
- **Interactive Documentation:** [https://gridwisebaseproject.onrender.com/docs](https://gridwisebaseproject.onrender.com/docs)

---

## 📁 Project Structure

```text
GridWiseBaseProject/
├── gridwise/
│   ├── api.py           # FastAPI application & route definitions
│   ├── directives.py    # Directives data structures & logic
│   ├── llm.py           # LLM connector interface
│   ├── models.py        # Pydantic schemas & payload models
│   ├── optimizer.py     # Linear Programming formulation (SciPy/HiGHS)
│   ├── prompts.py       # Prompt engineering & system instruction sets
│   ├── settings.py      # Environment configuration setup
│   └── validation.py   # Guardrails & schedule verification module
├── evaluation/          # LLM benchmarking test suites
├── examples/            # Sample requests and standard schema templates
├── scripts/             # Demonstration and evaluation tools
├── tests/               # Pytest test suite
├── Dockerfile           # Production build container definition
├── requirements.txt     # Production dependencies
├── run.py               # Application entry point
└── README.md            # System documentation
```

---

## 🐳 Docker

```bash
# Build Docker image
docker build -t gridwise:1.0.0 .

# Run container locally
docker run --rm -p 8000:8000 --env-file .env gridwise:1.0.0
```

---

## ⚠️ Known Limitations

- **Model Dependency:** Natural language directive extraction quality relies on the underlying LLM's reasoning performance.
- **Microgrid Scope:** Grid export (feed-in tariff) modeling is currently excluded based on competition specifications.
- **Fixed Horizon:** Optimized strictly for single 24-hour planning cycles without multi-day lookahead.

---

## 👷 Team Members

| Name | Role | Email | GitHub |
| :--- | :--- | :--- | :--- |
| **KM Hasibur Rahman** | Team Lead / System Architect | srijond57@gmail.com | https://github.com/srijon57 |
| **Sadik Rahman** | Core Developer | sadik.nai.008@gmail.com | https://github.com/SadikRahman14 |
| **Kazi Kamruddin Ahmed** | Quality Assurance / Tester | kazikamruddinahmed@gmail.com | https://github.com/kazi-kamruddin |

---

## 📚 References

1. **BUP CSE Fest 2026 Hackathon** — Problem Statement & Evaluation Matrix.
2. **FastAPI Framework** — High-performance web API framework.
3. **SciPy Optimization Documentation** — HiGHS linear programming solver.