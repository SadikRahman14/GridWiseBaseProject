"""Warm the actual model using a sample request before latency testing."""

import asyncio
import json
from pathlib import Path
import sys

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gridwise.llm import ModelInterpreter
from gridwise.models import Scenario
from gridwise.settings import Settings


async def main():
    settings = Settings.from_env()
    scenario = Scenario.model_validate_json((ROOT / "examples/sample_request.json").read_text(encoding="utf-8"))
    async with httpx.AsyncClient() as client:
        interpreter = ModelInterpreter(settings, client)
        if not await interpreter.ready():
            print("Model unavailable. Check .env and install/pull your model or configure your provider.")
            return 1
        if settings.provider == "ollama":
            # Cold-loading is an operator setup action, outside the judged API.
            try:
                response = await client.post(settings.base_url + "/api/generate", json={
                    "model": settings.model, "prompt": "", "stream": False, "keep_alive": "30m",
                }, timeout=120, headers=interpreter._headers())
                response.raise_for_status()
            except httpx.HTTPError:
                print("Model warmup failed. Check Ollama status and available memory.")
                return 1
        try:
            result = await interpreter.interpret(scenario)
        except Exception:
            print("Model loaded but interpretation failed or exceeded its budget. Check model speed/configuration.")
            return 1
    print("Real model interpretation succeeded:")
    print(json.dumps(result.model_dump(), indent=2))
    print("Run scripts/check_samples.py --mode live to check interpretation accuracy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
