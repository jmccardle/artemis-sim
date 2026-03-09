from abc import ABC, abstractmethod

from artemis.config import Settings


class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Send a completion request and return the response text."""
        ...


def get_llm_provider(settings: Settings) -> LLMProvider:
    """Factory: create the configured LLM provider. Raises ValueError for unknown providers."""
    from artemis.llm.anthropic_provider import AnthropicProvider
    from artemis.llm.local_provider import LocalProvider
    from artemis.llm.openai_provider import OpenAIProvider

    match settings.llm_provider:
        case "openai":
            return OpenAIProvider(
                api_key=settings.llm_api_key,
                model=settings.llm_model,
                base_url=settings.llm_base_url or None,
            )
        case "anthropic":
            return AnthropicProvider(
                api_key=settings.llm_api_key,
                model=settings.llm_model,
            )
        case "local":
            return LocalProvider(
                base_url=settings.llm_base_url,
                model=settings.llm_model,
            )
        case _:
            raise ValueError(
                f"Unknown LLM provider: '{settings.llm_provider}'. "
                "Valid providers: openai, anthropic, local"
            )
