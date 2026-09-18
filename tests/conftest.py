import json
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def cases():
    path = Path(__file__).resolve().parents[1] / "examples/public_samples.json"
    return json.loads(path.read_text(encoding="utf-8"))["cases"]
