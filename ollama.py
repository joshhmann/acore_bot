import base64
import os
from typing import Optional

import requests


def _ensure_http(url: str) -> str:
    if not url.lower().startswith(("http://", "https://")):
        return f"http://{url}"
    return url


class OllamaClient:
    def __init__(self, host: str, model: str, num_predict: int = 256, temperature: float = 0.7):
        self.host = host
        self.model = model
        self.num_predict = num_predict
        self.temperature = temperature

    @property
    def available(self) -> bool:
        return bool(self.host) and bool(self.model)

    def chat(self, prompt: str, timeout: float = 15.0, system: Optional[str] = None, history: Optional[list[dict]] = None, images: Optional[list[bytes]] = None) -> str:
        base = _ensure_http(self.host).rstrip('/')
        url = f"{base}/api/chat"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        if history:
            for m in history:
                role = m.get("role")
                content = m.get("content", "")
                if role in {"user", "assistant", "system"} and content:
                    messages.append({"role": role, "content": content})
        user_msg: dict = {"role": "user", "content": prompt}
        if images:
            try:
                b64s = [base64.b64encode(b).decode("ascii") for b in images if isinstance(b, (bytes, bytearray))]
                if b64s:
                    user_msg["images"] = b64s
            except Exception:
                pass
        messages.append(user_msg)
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        opts = {}
        if isinstance(self.num_predict, int) and self.num_predict > 0:
            opts["num_predict"] = self.num_predict
        try:
            t = float(self.temperature)
            if t >= 0:
                opts["temperature"] = t
        except Exception:
            pass
        if opts:
            body["options"] = opts
        r = requests.post(url, json=body, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        msg = data.get("message") or {}
        text = msg.get("content") or data.get("response") or ""
        return str(text).strip()

    def format_error(self, e: Exception) -> str:
        import requests as _req
        if isinstance(e, _req.Timeout):
            return "Ollama request timed out. Is the model loaded?"
        if isinstance(e, _req.ConnectionError):
            return f"Cannot reach Ollama at {self.host}. Is it running (ollama serve)?"
        if isinstance(e, _req.HTTPError):
            resp = e.response
            code = resp.status_code if resp is not None else 'HTTP'
            if code == 404:
                return f"Model or endpoint not found. Check OLLAMA_MODEL='{self.model}'."
            if code >= 500:
                return f"Ollama server error {code}. Check Ollama logs."
            return f"HTTP error {code} from Ollama."
        if isinstance(e, (_req.exceptions.MissingSchema, _req.exceptions.InvalidSchema, _req.exceptions.InvalidURL)):
            return f"Invalid Ollama host URL '{self.host}'. Include scheme, e.g. http://{self.host}"
        return f"Unexpected error: {e}"

