import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))

print("Modelos disponíveis:")
for model in client.models.list():
    # Filtra apenas modelos que suportam generateContent
    if 'generateContent' in model.supported_actions:
        print(f"- {model.name}")