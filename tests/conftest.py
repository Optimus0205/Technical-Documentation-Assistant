import os

# app.config needs a key at import time. The tests never call the real LLM, so a
# placeholder is enough (and lets someone run them without a .env file).
os.environ.setdefault("GROQ_API_KEY", "test-key-not-used")