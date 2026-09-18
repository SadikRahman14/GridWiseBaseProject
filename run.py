"""Start with: python run.py. Uses PORT when a hosting platform supplies it."""

import logging
import os

from dotenv import load_dotenv
import uvicorn

from gridwise.settings import PROJECT_ROOT

if __name__ == "__main__":
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    uvicorn.run("gridwise.api:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), access_log=False)
