"""HTTP client for cross-service calls to Item Service."""

from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException

from .config import ITEM_SERVICE_URL

logger = logging.getLogger(__name__)


class ItemClient:
    def __init__(self, base_url: str = ITEM_SERVICE_URL):
        self.base_url = base_url.rstrip("/")

    def get_item(self, item_id: int) -> dict:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{self.base_url}/items/{item_id}")
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Item not found")
            if response.status_code >= 400:
                detail = response.json().get("detail", response.text)
                raise HTTPException(status_code=response.status_code, detail=detail)
            return response.json()

    def reserve_item(self, item_id: int) -> dict:
        return self._post_workflow(item_id, "reserve")

    def release_item(self, item_id: int) -> dict:
        return self._post_workflow(item_id, "release")

    def recover_item(self, item_id: int) -> dict:
        return self._post_workflow(item_id, "recover")

    def _post_workflow(self, item_id: int, action: str) -> dict:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(f"{self.base_url}/items/{item_id}/{action}")
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Item not found")
            if response.status_code >= 400:
                detail = response.json().get("detail", response.text)
                raise HTTPException(status_code=response.status_code, detail=detail)
            logger.info("Item Service %s succeeded for itemId=%s", action, item_id)
            return response.json()


item_client = ItemClient()
