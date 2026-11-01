from groq import Groq
from app.config import settings

client = Groq(api_key=settings.groq_api_key)
for m in client.models.list().data:
    print(m.id)