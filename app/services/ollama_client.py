from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import requests


class OllamaClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL", "qwen3:30b")
        self.timeout = int(os.getenv("OLLAMA_TIMEOUT", "30"))  # Reduced from 120 to 30 seconds

    def is_available(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.ok
        except requests.RequestException:
            return False

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "model": model or self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "format": schema,
            "options": {
                "temperature": 0
            }
        }

        r = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=self.timeout,
        )
        r.raise_for_status()
        data = r.json()

        content = data["message"]["content"]
        if isinstance(content, dict):
            return content
        return json.loads(content)
