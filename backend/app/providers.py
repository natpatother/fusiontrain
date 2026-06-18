"""LLM provider abstraction.

Two interchangeable backends, selected by LLM_PROVIDER:
  - "azure_openai" : Azure OpenAI Service (openai SDK, AzureOpenAI client)
  - "foundry"      : Azure AI Foundry model inference (azure-ai-inference SDK)

Both expose the same interface: embed(text) -> list[float], chat(question, context) -> str.
"""
from abc import ABC, abstractmethod
from functools import lru_cache

from .config import get_settings

SYSTEM_PROMPT = (
    "You are a helpful assistant for the company knowledge base. "
    "Answer the user's question using ONLY the context below. "
    "If the context does not contain the answer, say you don't have that "
    "information. Reply in the same language as the question."
)


def _user_prompt(question: str, context: str) -> str:
    return f"Context:\n{context}\n\nQuestion: {question}"


class LLMProvider(ABC):
    @abstractmethod
    def embed(self, text: str) -> list[float]: ...

    @abstractmethod
    def chat(self, question: str, context: str) -> str: ...


class AzureOpenAIProvider(LLMProvider):
    def __init__(self) -> None:
        from openai import AzureOpenAI

        s = get_settings()
        self._s = s
        self._client = AzureOpenAI(
            azure_endpoint=s.azure_openai_endpoint,
            api_key=s.azure_openai_api_key,
            api_version=s.azure_openai_api_version,
        )

    def embed(self, text: str) -> list[float]:
        resp = self._client.embeddings.create(
            model=self._s.embedding_deployment, input=text
        )
        return resp.data[0].embedding

    def chat(self, question: str, context: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._s.chat_deployment,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _user_prompt(question, context)},
            ],
            temperature=0.2,
        )
        return resp.choices[0].message.content or ""


class FoundryProvider(LLMProvider):
    """Azure AI Foundry via the unified model-inference endpoint."""

    def __init__(self) -> None:
        from azure.ai.inference import ChatCompletionsClient, EmbeddingsClient
        from azure.core.credentials import AzureKeyCredential

        s = get_settings()
        self._s = s
        cred = AzureKeyCredential(s.foundry_api_key)
        self._embed_client = EmbeddingsClient(
            endpoint=s.foundry_endpoint,
            credential=cred,
            api_version=s.foundry_api_version,
        )
        self._chat_client = ChatCompletionsClient(
            endpoint=s.foundry_endpoint,
            credential=cred,
            api_version=s.foundry_api_version,
        )

    def embed(self, text: str) -> list[float]:
        resp = self._embed_client.embed(
            input=[text], model=self._s.foundry_embedding_model
        )
        return list(resp.data[0].embedding)

    def chat(self, question: str, context: str) -> str:
        from azure.ai.inference.models import SystemMessage, UserMessage

        resp = self._chat_client.complete(
            model=self._s.foundry_chat_model,
            messages=[
                SystemMessage(content=SYSTEM_PROMPT),
                UserMessage(content=_user_prompt(question, context)),
            ],
            temperature=0.2,
        )
        return resp.choices[0].message.content or ""


@lru_cache
def get_provider() -> LLMProvider:
    name = get_settings().llm_provider.lower().strip()
    if name == "foundry":
        return FoundryProvider()
    if name in ("azure_openai", "azure", "openai"):
        return AzureOpenAIProvider()
    raise ValueError(f"Unknown LLM_PROVIDER: {name!r} (use 'azure_openai' or 'foundry')")
