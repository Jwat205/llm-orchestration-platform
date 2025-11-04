# shared/functions/api_integrations.py
import requests

def call_external_api(endpoint: str, payload: dict) -> dict:
    response = requests.post(endpoint, json=payload)
    response.raise_for_status()
    return response.json()
