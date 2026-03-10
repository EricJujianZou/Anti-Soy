"""
Shared Gemini client factory for the Anti-Soy server.

Usage:
    from v2.gemini_client import get_gemini_client

    client = get_gemini_client()
    response = client.models.generate_content(...)            # sync
    response = await client.aio.models.generate_content(...)  # async
"""
import os
import logging

from google import genai

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def get_gemini_client() -> genai.Client:
    """
    Return a shared genai.Client singleton.
    Raises RuntimeError if GEMINI_API_KEY is not set.
    """
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable is not set")
        _client = genai.Client(api_key=api_key)
        logger.debug("Gemini client initialized")
    return _client
