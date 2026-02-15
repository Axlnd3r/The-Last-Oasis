from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import httpx


@dataclass(frozen=True)
class EntryQuote:
    asset: str
    amount: str
    protocol: str
    instructions: dict[str, Any]


@dataclass(frozen=True)
class EntryConfirm:
    agent_id: str
    api_key: str


class LastOasisClient:
    def __init__(self, base_url: str, api_key: Optional[str] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {}
        if self.api_key:
            h["X-AGENT-TOKEN"] = self.api_key
        return h

    async def entry_quote(self) -> EntryQuote:
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{self.base_url}/entry/quote")
            r.raise_for_status()
            data = r.json()
            return EntryQuote(
                asset=str(data["asset"]),
                amount=str(data["amount"]),
                protocol=str(data.get("protocol", "x402")),
                instructions=dict(data.get("instructions", {})),
            )

    async def entry_confirm(self, tx_ref: str, name: Optional[str] = None) -> EntryConfirm:
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{self.base_url}/entry/confirm", json={"tx_ref": tx_ref, "name": name})
            r.raise_for_status()
            data = r.json()
            return EntryConfirm(agent_id=str(data["agent_id"]), api_key=str(data["api_key"]))

    async def status(self) -> dict[str, Any]:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self.base_url}/world/status")
            r.raise_for_status()
            return r.json()

    async def observation(self) -> dict[str, Any]:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self.base_url}/world/observation", headers=self._headers())
            r.raise_for_status()
            return r.json()

    async def submit_action(self, action: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{self.base_url}/world/action", json=action, headers=self._headers())
            r.raise_for_status()
            return r.json()

