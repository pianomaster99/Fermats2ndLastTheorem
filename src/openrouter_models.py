from src.config import OPENROUTER_BASE_URL
import requests
import json

MODELS_URL = OPENROUTER_BASE_URL + "/models"


def is_free_model(model: dict) -> bool:
    model_id = model.get("id", "")
    pricing = model.get("pricing", {})

    prompt_price = float(pricing.get("prompt", "1"))
    completion_price = float(pricing.get("completion", "1"))
    request_price = float(pricing.get("request", "0"))

    return (
        model_id.endswith(":free")
        or (prompt_price == 0 and completion_price == 0 and request_price == 0)
    )


def get_models() -> list[dict]:
    response = requests.get(MODELS_URL, timeout=30)
    response.raise_for_status()

    return response.json()["data"]


def get_free_models() -> list[dict]:
    models = get_models()

    free_models = [
        {
            "id": model["id"],
            "name": model.get("name"),
            "context_length": model.get("context_length"),
            "pricing": model.get("pricing"),
        }
        for model in models
        if is_free_model(model)
    ]

    free_models.sort(key=lambda m: m["id"])

    return free_models


def get_free_model_ids() -> list[str]:
    free_models = get_free_models()
    return [model["id"] for model in free_models]