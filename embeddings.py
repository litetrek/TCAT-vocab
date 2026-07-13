import os

try:
    import voyageai as _voyageai
    _VOYAGE_AVAILABLE = True
except ImportError:
    _VOYAGE_AVAILABLE = False

try:
    import openai as _openai
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False


def get_voyage_embedding(text: str) -> list | None:
    """Return a 1024-dim embedding via Voyage AI voyage-3, or None on any failure/missing key."""
    if not text or not text.strip():
        return None
    key = os.getenv("VOYAGE_API_KEY")
    if not key:
        return None
    if not _VOYAGE_AVAILABLE:
        return None
    try:
        client = _voyageai.Client(api_key=key)
        result = client.embed([text], model="voyage-3", input_type="document")
        return result.embeddings[0]
    except Exception:
        return None


def get_openai_embedding(text: str) -> list | None:
    """Return a 1536-dim embedding via OpenAI text-embedding-3-small, or None on any failure/missing key."""
    if not text or not text.strip():
        return None
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    if not _OPENAI_AVAILABLE:
        return None
    try:
        client = _openai.OpenAI(api_key=key)
        result = client.embeddings.create(input=text, model="text-embedding-3-small")
        return result.data[0].embedding
    except Exception:
        return None


def get_embeddings(text: str) -> dict:
    """Best-effort: call both providers, return {"voyage": [...] | None, "openai": [...] | None}."""
    return {
        "voyage": get_voyage_embedding(text),
        "openai": get_openai_embedding(text),
    }
