import os
import uuid

import httpx
import pytest

ITEM_URL = os.getenv("ITEM_URL", "http://localhost:8001")
CLAIM_URL = os.getenv("CLAIM_URL", "http://localhost:8002")
NOTIF_URL = os.getenv("NOTIF_URL", "http://localhost:8003")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def services_available() -> bool:
    try:
        with httpx.Client(timeout=2.0) as client:
            for url in (ITEM_URL, CLAIM_URL, NOTIF_URL):
                if client.get(f"{url}/health").status_code != 200:
                    return False
        return True
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


requires_services = pytest.mark.skipif(
    not services_available(),
    reason="Docker Compose stack not running (start with: docker compose up -d)",
)


@pytest.fixture
def uid():
    return uuid.uuid4().hex[:8]


@pytest.fixture
def client():
    with httpx.Client(timeout=10.0) as c:
        yield c


@pytest.fixture
def two_users(client, uid):
    """Register and login two users; return tokens and usernames."""
    user_a = f"test_a_{uid}"
    user_b = f"test_b_{uid}"
    password = "secret123"

    for email, username in [
        (f"{user_a}@test.edu", user_a),
        (f"{user_b}@test.edu", user_b),
    ]:
        r = client.post(
            f"{ITEM_URL}/register",
            json={"email": email, "username": username, "password": password},
        )
        assert r.status_code in (201, 400), r.text

    token_a = client.post(
        f"{ITEM_URL}/login",
        json={"username": user_a, "password": password},
    ).json()["access_token"]
    token_b = client.post(
        f"{ITEM_URL}/login",
        json={"username": user_b, "password": password},
    ).json()["access_token"]

    return {
        "a": {"username": user_a, "token": token_a},
        "b": {"username": user_b, "token": token_b},
    }
