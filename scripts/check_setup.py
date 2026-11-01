from app.config import settings
from app.llm import get_llm, text_of

print(f"provider={settings.llm_provider}  model={settings.llm_model}")
print(text_of(get_llm().invoke("Say hello in 5 words").content))