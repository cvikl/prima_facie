"""Client for the local LLM server."""

import httpx

import os

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:8000")
TIMEOUT = 300.0


async def parse_intent(system_prompt: str, user_message: str) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            f"{LLM_BASE_URL}/parse_intent",
            json={"system_prompt": system_prompt, "user_message": user_message},
        )
        resp.raise_for_status()
        return resp.json()


async def summarize(system_prompt: str, user_message: str) -> str:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            f"{LLM_BASE_URL}/summarize",
            json={"system_prompt": system_prompt, "user_message": user_message},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("summary", "")
