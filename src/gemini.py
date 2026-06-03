import os
import json
from dotenv import load_dotenv
from google import genai


load_dotenv()


DEFAULT_MODEL = "gemini-2.5-flash"


class GeminiClient:
    def __init__(self, model=DEFAULT_MODEL):
        load_dotenv()
        self.model = model
        self.client = genai.Client()

    def ask(self, prompt):
<<<<<<< HEAD
        #Ask gemini model
        response = self.client.models.generate_content(model=self.model, contents=prompt)
=======
        # Ask Gemini model
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )
>>>>>>> 535bd31964e4967a9f936a44d273368beabc13ae

        return response.text.strip()

    def parse_json_object(self, raw_text):
        text = raw_text.strip()

        if text.startswith("```"):
            lines = text.splitlines()

            if lines and lines[0].startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]

            text = "\n".join(lines).strip()

        if text.startswith("json"):
            text = text[len("json"):].strip()

        return json.loads(text)
