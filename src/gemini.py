import os
from dotenv import load_dotenv
from google import genai


load_dotenv()


DEFAULT_MODEL = "gemini-2.5-flash"

class GeminiClient:
    def __init__(self, model = DEFAULT_MODEL):
        load_dotenv()
        self.model = model
        self.client = genai.Client()

    def ask(self, prompt):

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )

        return response.text.strip()
