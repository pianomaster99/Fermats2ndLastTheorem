from openai import OpenAI
from dotenv import load_dotenv
from src.openrouter_models import get_free_model_ids
import os

print(get_free_model_ids())