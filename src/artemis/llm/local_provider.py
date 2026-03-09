from openai import AsyncOpenAI

from artemis.llm.base import LLMProvider


class LocalProvider(LLMProvider):
    """Provider for local LLM servers (ollama, llama.cpp, vLLM) via OpenAI-compatible API."""

    def __init__(self, base_url: str, model: str) -> None:
        if not base_url:
            raise ValueError(
                "LocalProvider requires a base_url "
                "(e.g., http://localhost:11434/v1 for ollama, "
                "http://localhost:8080/v1 for llama.cpp)"
            )
        self._client = AsyncOpenAI(api_key="not-needed", base_url=base_url)
        self._model = model

    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content
