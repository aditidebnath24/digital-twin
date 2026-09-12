import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


class LLMProvider:
    """
    Base interface for the AQ Digital Twin LLM provider.
    """

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        raise NotImplementedError


class MistralProvider(LLMProvider):
    """
    Mistral-backed LLM provider.
    """

    def __init__(self, model: str = "mistral-large-latest"):
        self.model = model

        api_key = os.getenv("MISTRAL_API_KEY")

        if not api_key:
            raise RuntimeError(
                "MISTRAL_API_KEY is not set. "
                "Please configure it in the .env file."
            )

        # NOTE: import path depends on installed mistralai version.
        # v2.x (current): from mistralai.client import Mistral
        # v1.x           : from mistralai import Mistral
        # v0.x           : from mistralai.client import MistralClient
        from mistralai.client import Mistral

        self.client = Mistral(api_key=api_key)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:

        messages = []

        if system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": system_prompt,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        response = self.client.chat.complete(
            model=self.model,
            messages=messages,
        )

        return response.choices[0].message.content


class GeminiProvider(LLMProvider):
    """
    Google Gemini-backed LLM provider.

    Requires: pip install google-genai
    """

    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model = model

        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. "
                "Please configure it in the .env file."
            )

        from google import genai

        self.client = genai.Client(api_key=api_key)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        from google.genai import types

        config = None
        if system_prompt:
            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
            )

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )

        return response.text


def build_llm_provider() -> LLMProvider:
    """
    Factory for creating the configured LLM provider.
    """

    provider = os.getenv("LLM_PROVIDER", "mistral").lower()

    if provider == "mistral":
        model = os.getenv(
            "LLM_MODEL",
            "mistral-large-latest",
        )
        return MistralProvider(model=model)

    if provider == "gemini":
        model = os.getenv(
            "LLM_MODEL",
            "gemini-2.5-flash",
        )
        return GeminiProvider(model=model)

    raise ValueError(
        f"Unsupported LLM_PROVIDER: {provider}"
    )