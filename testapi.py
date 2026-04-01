import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))

response = client.models.generate_content(
    model="models/gemini-2.0-flash",
    contents="Diga apenas 'OK'"
)
print(response.text)