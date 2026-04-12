"""Azure OpenAI provider using Entra ID (OAuth2/OIDC) authentication.

No API keys — uses DefaultAzureCredential for token-based auth.
Supports Azure CLI, managed identity, workload identity, and environment credentials.
"""

from typing import Any

from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from openai import AsyncAzureOpenAI

from src.application.llm.types import LLMMessage, LLMProvider, LLMResponse

AZURE_COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"


class AzureOpenAIProvider:
    """LLM provider using Azure OpenAI with Entra ID authentication."""

    def __init__(
        self,
        endpoint: str,
        deployment: str,
        api_version: str = "2024-10-21",
    ) -> None:
        if not endpoint:
            msg = "Azure OpenAI endpoint is required (set azure_openai_endpoint in config)"
            raise ValueError(msg)
        if not deployment:
            msg = "Azure OpenAI deployment is required (set azure_openai_deployment in config)"
            raise ValueError(msg)

        self._deployment = deployment
        self._credential = DefaultAzureCredential()
        self._token_provider = get_bearer_token_provider(
            self._credential, AZURE_COGNITIVE_SCOPE
        )
        self._client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=self._token_provider,
            api_version=api_version,
        )

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Complete via Azure OpenAI with Entra ID auth."""
        deployment = model or self._deployment
        oai_messages: list[dict[str, str]] = [
            {"role": m.role, "content": m.content} for m in messages
        ]

        call_kwargs: dict[str, Any] = {
            "model": deployment,
            "messages": oai_messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            call_kwargs["max_tokens"] = max_tokens

        response = await self._client.chat.completions.create(**call_kwargs)

        content = response.choices[0].message.content or ""
        usage: dict[str, int] = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=content,
            model=deployment,
            usage=usage,
        )

    async def close(self) -> None:
        """Clean up async resources."""
        await self._client.close()
        await self._credential.close()


# Verify protocol conformance
assert isinstance(AzureOpenAIProvider, type)
_: type[LLMProvider] = AzureOpenAIProvider  # type: ignore[assignment]
