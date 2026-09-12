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

    raise ValueError(
        f"Unsupported LLM_PROVIDER: {provider}"
    )