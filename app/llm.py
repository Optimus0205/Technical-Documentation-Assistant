from langchain_groq import ChatGroq

from app.config import settings


def get_llm(temperature: float = 0.0):
    """The one place that builds the chat model. The provider is chosen in .env (LLM_PROVIDER)."""
    if settings.llm_provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        # No temperature here: gemini-3.5-flash-lite uses fixed sampling defaults and ignores it.
        return ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.google_api_key,
            max_retries=6,
        )
    return ChatGroq(
        model=settings.llm_model,
        api_key=settings.groq_api_key,
        temperature=temperature,
        max_retries=6,
    )


def text_of(content) -> str:
    """Return plain text from a model reply. Some providers return a string, others a list of content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content)