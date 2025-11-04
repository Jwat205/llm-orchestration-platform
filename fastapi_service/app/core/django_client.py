import httpx
import asyncio
from typing import Optional
from app.shared.schemas.internal import UserValidationRequest, UserValidationResponse

class DjangoClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=10.0)

    async def validate_token(self, token: str) -> Optional[UserValidationResponse]:
        payload = {"token": token}
        try:
            resp = await self.client.post("/internal/validate-token/", json=payload)
            resp.raise_for_status()
            return UserValidationResponse(**resp.json())
        except (httpx.HTTPError, httpx.RequestError):
            # handle logging or retries here
            return None

    async def log_usage(self, usage_data: dict):
        try:
            await self.client.post("/internal/log-usage/", json=usage_data)
        except Exception:
            # handle errors, logging, retries
            pass

    async def check_rate_limit(self, user_id: int, api_key: Optional[str] = None):
        params = {"user_id": user_id}
        if api_key:
            params["api_key"] = api_key
        try:
            resp = await self.client.get("/internal/check-rate-limit", params=params)
            resp.raise_for_status()
            return resp.json().get("allowed", False)
        except Exception:
            return False

django_client = DjangoClient(base_url="http://localhost:8000/api/auth/")