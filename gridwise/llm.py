"""Real generative-model interpretation. There is deliberately no regex fallback."""

import asyncio
import json
import logging

import httpx
from pydantic import ValidationError

from .errors import InterpretationError
from .models import Interpretation, Scenario
from .prompts import SYSTEM_PROMPT
from .settings import Settings

logger = logging.getLogger("gridwise")


def _reject_constant(value):
    raise ValueError("JSON must contain only finite numbers")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def parse_interpretation(text: str, scenario: Scenario) -> Interpretation:
    # Formatting cleanup only: no semantic rewrite or guessing missing fields.
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if lines[0].lower() not in {"```json", "```"}:
            raise ValueError("Unsupported fenced format")
        text = "\n".join(lines[1:-1])
    data = json.loads(text, parse_constant=_reject_constant, object_pairs_hook=_unique_object)
    return Interpretation.model_validate(data).validate_for(scenario)


def _retry_delay(response, attempt: int) -> float:
    """Respect provider rate-limit guidance when available."""

    if response.status_code == 429:
        retry_after = response.headers.get("retry-after")

        if retry_after:
            try:
                return min(
                    max(float(retry_after), 0.5),
                    8.0
                )
            except ValueError:
                pass

    # Fallback for temporary 5xx/provider errors.
    return min(
        0.5 * (2 ** attempt),
        2.0
    )


class ModelInterpreter:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings = settings
        self.client = client

    def _headers(self):
        if self.settings.api_key:
            return {"Authorization": f"Bearer {self.settings.api_key}"}
        return {}

    async def ready(self) -> bool:
        """Check reachability and that the configured model is listed, without inference."""
        try:
            path = "/api/tags" if self.settings.provider == "ollama" else "/models"
            async with asyncio.timeout(2):
                response = await self.client.get(
                    self.settings.base_url + path, headers=self._headers(), timeout=2,
                )
                response.raise_for_status()
                data = response.json()
                if self.settings.provider == "ollama":
                    names = {m.get("name") for m in data.get("models", [])}
                    names.update(m.get("model") for m in data.get("models", []))
                    return self.settings.model in names or self.settings.model + ":latest" in names
                return self.settings.model in {m.get("id") for m in data.get("data", [])}
        except (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError, AttributeError):
            return False

    async def _generate(self, messages):
        settings = self.settings
        if settings.provider == "ollama":
            path = "/api/chat"
            payload = {
                "model": settings.model, "messages": messages, "stream": False,
                "format": Interpretation.model_json_schema(), "keep_alive": "30m",
                "options": {"temperature": 0, "num_predict": 1600},
            }
        else:
            path = "/chat/completions"
            payload = {
                "model": settings.model,
                "messages": messages,
                "stream": False,
                "temperature": 0,
                "reasoning_effort": "low",
                "response_format": {"type": "json_object"},
            }
        response = await self.client.post(
            settings.base_url + path, json=payload, headers=self._headers(),
            timeout=httpx.Timeout(settings.llm_timeout, connect=4),
        )

        if response.status_code == 429:
            logger.warning(
                "rate_limit_details retry_after=%s remaining_tokens=%s reset_tokens=%s",
                response.headers.get("retry-after"),
                response.headers.get("x-ratelimit-remaining-tokens"),
                response.headers.get("x-ratelimit-reset-tokens"),
            )
        response.raise_for_status()
        data = response.json()

        usage = data.get("usage", {})

        logger.warning(
            "llm_usage prompt_tokens=%s completion_tokens=%s total_tokens=%s",
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
            usage.get("total_tokens"),
        )
        if settings.provider == "ollama":
            content = data["message"]["content"]
        else:
            content = data["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip() or len(content) > 50_000:
            raise ValueError("Invalid model content")
        return content

    async def interpret(self, scenario: Scenario) -> Interpretation:
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "operator_notes": scenario.operator_notes,
                        "battery_capacity_kwh": scenario.battery.capacity_kwh,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        try:
            # One wall-clock budget covers all attempts; retries cannot multiply it.
            async with asyncio.timeout(self.settings.llm_timeout):
                for attempt in range(self.settings.retries + 1):
                    try:
                        raw = await self._generate(messages)
                        return parse_interpretation(raw, scenario)
                    except (ValidationError, ValueError, KeyError, IndexError, TypeError):
                        logger.warning("model_output_rejected attempt=%d", attempt + 1)
                        messages.append({"role": "user", "content": (
                            "The previous output failed strict validation. Re-read the notes and "
                            "return the full JSON object again. Check exact keys, one entry per "
                            "note in order, booleans, sorted unique integer hours, applies/no_op "
                            "consistency, finite numbers and reserve <= battery capacity."
                        )})
                    except httpx.HTTPStatusError as error:
                        status = error.response.status_code
                        headers = error.response.headers

                        logger.warning(
                            "model_error_body=%s",
                            error.response.text[:1500]
                        )

                        if status == 429:
                            logger.warning(
                                "rate_limit_details "
                                "retry_after=%s "
                                "limit_requests=%s "
                                "remaining_requests=%s "
                                "reset_requests=%s "
                                "limit_tokens=%s "
                                "remaining_tokens=%s "
                                "reset_tokens=%s",
                                headers.get("retry-after"),
                                headers.get("x-ratelimit-limit-requests"),
                                headers.get("x-ratelimit-remaining-requests"),
                                headers.get("x-ratelimit-reset-requests"),
                                headers.get("x-ratelimit-limit-tokens"),
                                headers.get("x-ratelimit-remaining-tokens"),
                                headers.get("x-ratelimit-reset-tokens"),
                            )

                            logger.warning(
                                "rate_limit_body=%s",
                                error.response.text[:1000]
                            )

                        if status not in {429, 500, 502, 503, 504}:
                            break

                        if attempt < self.settings.retries:
                            delay = _retry_delay(
                                error.response,
                                attempt
                            )

                            logger.warning(
                                "model_retry status=%d wait=%.2fs",
                                status,
                                delay
                            )

                            await asyncio.sleep(delay)
                    except httpx.RequestError:
                        logger.warning("model_connection_failure attempt=%d", attempt + 1)
                        if attempt < self.settings.retries:
                            await asyncio.sleep(
                                min(0.5 * (2 ** attempt), 2.0)
                            )
        except TimeoutError:
            logger.warning("model_budget_exceeded")
        raise InterpretationError(
            "The language model could not produce a valid interpretation within its time budget. "
            "Check the configured provider, model, credentials, availability, and quota."
        )
