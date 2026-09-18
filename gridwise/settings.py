"""Environment-only provider configuration. Never store or log secret values."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    provider: str = "ollama"
    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5:3b"
    api_key: str = field(default="", repr=False)
    llm_timeout: float = 22.0
    retries: int = 1

    def __post_init__(self):
        if self.provider not in {"ollama", "openai-compatible"}:
            raise ValueError("LLM_PROVIDER must be ollama or openai-compatible")
        url = urlsplit(self.base_url)
        if url.scheme not in {"http", "https"} or not url.netloc or url.username or url.password or url.query or url.fragment:
            raise ValueError("LLM_BASE_URL must be an HTTP(S) base URL without credentials, query, or fragment")
        if not self.model.strip():
            raise ValueError("LLM_MODEL must name an installed or provider-supported model")
        if not 0 < self.llm_timeout <= 25:
            raise ValueError("LLM_TIMEOUT_SECONDS must be greater than 0 and at most 25")
        if self.retries not in {0, 1, 2}:
            raise ValueError("LLM_RETRIES must be 0, 1, or 2")

    @classmethod
    def from_env(cls):
        load_dotenv(PROJECT_ROOT / ".env", override=False)
        provider = os.getenv("LLM_PROVIDER", "ollama").strip()
        base_url = os.getenv("LLM_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/")
        return cls(
            provider=provider, base_url=base_url,
            model=os.getenv("LLM_MODEL", "qwen2.5:3b").strip(),
            api_key=os.getenv("LLM_API_KEY", "").strip(),
            llm_timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "22")),
            retries=int(os.getenv("LLM_RETRIES", "1")),
        )
