import logging
import os
import sys

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "lostify-dev-secret-change-in-production")
ALGORITHM = "HS256"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./item.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
STEP_FUNCTIONS_STATE_MACHINE_ARN = os.getenv("STEP_FUNCTIONS_STATE_MACHINE_ARN", "")
AWS_REGION = os.getenv("AWS_REGION", "eu-central-1")

# Allow importing shared package from repo root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
