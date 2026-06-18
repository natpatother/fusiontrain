"""Thin facade over the configured LLM provider (Azure OpenAI or Azure AI Foundry)."""
from .providers import get_provider


def embed(text: str) -> list[float]:
    """Return the embedding vector for a single string (3072-dim by default)."""
    return get_provider().embed(text)


def chat(question: str, context: str) -> str:
    return get_provider().chat(question, context)
