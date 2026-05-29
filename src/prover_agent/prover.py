from openai import OpenAI
from src.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL

class ProverAgent():
    """LLM prover that proposes Lean tactics through OpenRouter."""

    def __init__(self, model: str, name: str = "openrouter") -> None:

        #Setting up the model
        self.name = name
        self.model = model
        self.client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)
