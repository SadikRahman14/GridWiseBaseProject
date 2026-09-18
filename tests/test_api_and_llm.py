import asyncio
import copy
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from gridwise.api import create_app
from gridwise.errors import InterpretationError
from gridwise.llm import ModelInterpreter, parse_interpretation
from gridwise.models import Interpretation, PlanResponse, Scenario
from gridwise.settings import Settings
from gridwise.validation import validate_plan


class TestInterpreter:
    __test__ = False

    def __init__(self, directives=None, error=None, ready=True):
        self.directives, self.error, self.is_ready = directives, error, ready

    async def ready(self):
        return self.is_ready

    async def interpret(self, scenario):
        if self.error:
            raise self.error
        return Interpretation(directive_interpretation=self.directives).validate_for(scenario)


@pytest.mark.parametrize("index", range(10))
def test_api_pipeline_with_injected_interpretation(cases, index):
    case = cases[index]
    interpreter = TestInterpreter(case["expected_output"]["directive_interpretation"])
    with TestClient(create_app(interpreter=interpreter)) as client:
        assert client.get("/health").json() == {"status": "ok"}
        response = client.post("/optimize-energy", json=case["input"])
        assert response.status_code == 200
        result = PlanResponse.model_validate(response.json())
        validate_plan(Scenario.model_validate(case["input"]), result)
        assert result.total_cost_bdt == case["expected_output"]["total_cost_bdt"]


@pytest.mark.parametrize("fault", ["missing", "duplicate_hour", "string_number", "boolean_number",
                                  "negative", "too_many_notes", "empty_note", "bad_battery", "extra"])
def test_invalid_requests_return_400(cases, fault):
    raw = copy.deepcopy(cases[0]["input"])
    if fault == "missing": del raw["battery"]
    elif fault == "duplicate_hour": raw["hours"][1]["hour"] = 0
    elif fault == "string_number": raw["hours"][0]["demand_kwh"] = "10"
    elif fault == "boolean_number": raw["hours"][0]["demand_kwh"] = True
    elif fault == "negative": raw["hours"][0]["solar_kwh"] = -1
    elif fault == "too_many_notes": raw["operator_notes"] = ["note"] * 4
    elif fault == "empty_note": raw["operator_notes"] = ["  "]
    elif fault == "bad_battery": raw["battery"]["initial_energy_kwh"] = 9999
    elif fault == "extra": raw["not_in_contract"] = "value"
    with TestClient(create_app(interpreter=TestInterpreter())) as client:
        response = client.post("/optimize-energy", json=raw)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_request"


def test_malformed_and_nonfinite_json(cases):
    with TestClient(create_app(interpreter=TestInterpreter())) as client:
        for body in ['{"bad":', json.dumps(cases[0]["input"]).replace('"solar_kwh": 0', '"solar_kwh": NaN', 1)]:
            result = client.post("/optimize-energy", content=body, headers={"Content-Type": "application/json"})
            assert result.status_code == 400


def test_unready_health():
    with TestClient(create_app(interpreter=TestInterpreter(ready=False))) as client:
        assert client.get("/health").status_code == 503


def test_provider_error_and_unexpected_errors_do_not_expose_secret(cases):
    for error in [InterpretationError("Model unavailable."), RuntimeError("SECRET_TEST_KEY")]:
        with TestClient(create_app(interpreter=TestInterpreter(error=error)), raise_server_exceptions=False) as client:
            result = client.post("/optimize-energy", json=cases[0]["input"])
            assert result.status_code == 500
            assert "SECRET_TEST_KEY" not in result.text
            assert "Traceback" not in result.text


@pytest.mark.parametrize("fault", ["false_applies", "unknown", "missing_note", "duplicate_note",
                                  "reordered", "unsorted_hours", "duplicate_hours", "hour_24",
                                  "factor", "wrong_shape", "excess_reserve", "numeric_string"])
def test_llm_guardrails(cases, fault):
    scenario = Scenario.model_validate(cases[0]["input"])
    raw = copy.deepcopy(cases[0]["expected_output"]["directive_interpretation"])
    a = raw[0]["structured_adjustment"]
    if fault == "false_applies": raw[0]["applies"] = False
    elif fault == "unknown": raw[0]["directive_type"] = "reduce_demand"
    elif fault == "missing_note": raw.pop()
    elif fault == "duplicate_note": raw[1]["note_index"] = 0
    elif fault == "reordered": raw.reverse()
    elif fault == "unsorted_hours": a["hours"] = [13, 12]
    elif fault == "duplicate_hours": a["hours"] = [12, 12]
    elif fault == "hour_24": a["hours"] = [24]
    elif fault == "factor": a["factor"] = 1.1
    elif fault == "wrong_shape": a["unsupported"] = 4
    elif fault == "numeric_string": a["factor"] = "0.25"
    elif fault == "excess_reserve":
        raw[0]["directive_type"] = "minimum_battery_reserve"
        raw[0]["structured_adjustment"] = {"hours": [12], "minimum_energy_kwh": 9999}
    with pytest.raises(ValueError):
        parse_interpretation(json.dumps({"directive_interpretation": raw}), scenario)


def test_duplicate_json_keys_and_nan_rejected(cases):
    scenario = Scenario.model_validate(cases[0]["input"])
    with pytest.raises(ValueError):
        parse_interpretation('{"directive_interpretation":[],"directive_interpretation":[]}', scenario)
    raw = {"directive_interpretation": copy.deepcopy(cases[0]["expected_output"]["directive_interpretation"])}
    raw["directive_interpretation"][0]["structured_adjustment"]["factor"] = float("nan")
    with pytest.raises(ValueError):
        parse_interpretation(json.dumps(raw), scenario)


@pytest.mark.parametrize("provider", ["ollama", "openai-compatible"])
def test_real_adapter_contract_with_mock_http_transport(cases, provider):
    """Tests request formatting + parsing, not live model accuracy."""
    case = cases[0]
    calls = []

    def handler(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"models": [{"name": "test-model"}]} if provider == "ollama"
                                  else {"data": [{"id": "test-model"}]})
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        assert payload["stream"] is False
        assert "operator_notes" in payload["messages"][1]["content"]
        assert "hours" not in json.loads(payload["messages"][1]["content"])
        content = json.dumps({"directive_interpretation": case["expected_output"]["directive_interpretation"]})
        return httpx.Response(200, json={"message": {"content": content}} if provider == "ollama"
                              else {"choices": [{"message": {"content": content}}]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = ModelInterpreter(Settings(provider=provider, base_url="http://model.test", model="test-model"), client)
            assert await adapter.ready()
            return await adapter.interpret(Scenario.model_validate(case["input"]))
    result = asyncio.run(run())
    assert len(result.directive_interpretation) == 2
    assert len(calls) == 2


def test_malformed_model_output_is_retried(cases):
    calls = []
    raw = {"directive_interpretation": cases[0]["expected_output"]["directive_interpretation"]}

    def handler(request):
        calls.append(request)
        content = "broken JSON" if len(calls) == 1 else json.dumps(raw)
        return httpx.Response(200, json={"message": {"content": content}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await ModelInterpreter(Settings(), client).interpret(Scenario.model_validate(cases[0]["input"]))
    assert len(asyncio.run(run()).directive_interpretation) == 2
    assert len(calls) == 2


def test_model_timeout_has_one_total_budget(cases):
    async def handler(request):
        await asyncio.sleep(0.2)
        return httpx.Response(500)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = ModelInterpreter(Settings(llm_timeout=0.02, retries=2), client)
            with pytest.raises(InterpretationError):
                await adapter.interpret(Scenario.model_validate(cases[0]["input"]))
    asyncio.run(run())


def test_unauthorized_provider_is_not_retried_and_body_is_not_exposed(cases):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(401, text="SECRET_TEST_KEY")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = ModelInterpreter(Settings(api_key="SECRET_TEST_KEY"), client)
            with pytest.raises(InterpretationError) as caught:
                await adapter.interpret(Scenario.model_validate(cases[0]["input"]))
            assert "SECRET_TEST_KEY" not in str(caught.value)
    asyncio.run(run())
    assert len(calls) == 1
