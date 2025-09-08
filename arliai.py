import base64
from typing import Optional, List, Dict, Any

import requests


class ArliaiClient:
    def __init__(self, api_key: str = "", base_url: str = "https://api.arliai.com", *, text_api_key: str | None = None, image_api_key: str | None = None):
        self.api_key = api_key or ""
        self.text_api_key = text_api_key or api_key or ""
        self.image_api_key = image_api_key or api_key or ""
        self.base_url = base_url.rstrip("/")

    def _headers(self, key: str) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        }

    def chat(self, model: str, messages: List[Dict[str, str]], *, repetition_penalty: float = 1.1,
             temperature: float = 0.7, top_p: float = 0.9, top_k: int = 40, max_tokens: int = 512,
             stream: bool = False, timeout: float = 20.0) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "repetition_penalty": repetition_penalty,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        r = requests.post(url, json=payload, headers=self._headers(self.text_api_key), timeout=timeout)
        r.raise_for_status()
        return r.json()

    def completions(self, model: str, prompt: str, *, repetition_penalty: float = 1.1, temperature: float = 0.7,
                    top_p: float = 0.9, top_k: int = 40, max_tokens: int = 512, stream: bool = False,
                    timeout: float = 20.0) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/completions"
        payload = {
            "model": model,
            "prompt": prompt,
            "repetition_penalty": repetition_penalty,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        r = requests.post(url, json=payload, headers=self._headers(self.text_api_key), timeout=timeout)
        r.raise_for_status()
        return r.json()

    def txt2img(self, model: str, prompt: str, *, negative_prompt: str = "", steps: int = 30,
                sampler_name: str = "DPM++ 2M Karras", width: int = 1024, height: int = 1024,
                seed: int = -1, cfg_scale: int = 7, timeout: float = 60.0) -> Dict[str, Any]:
        url = f"{self.base_url}/sdapi/v1/txt2img"
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "steps": steps,
            "sampler_name": sampler_name,
            "width": width,
            "height": height,
            "sd_model_checkpoint": model,
            "seed": seed,
            "cfg_scale": cfg_scale,
        }
        r = requests.post(url, json=payload, headers=self._headers(self.image_api_key), timeout=timeout)
        r.raise_for_status()
        return r.json()

    def img2img(self, model: str, init_images_b64: List[str], prompt: str, *, negative_prompt: str = "",
                steps: int = 30, sampler_name: str = "DPM++ 2M Karras", width: int = 1024, height: int = 1024,
                seed: int = -1, cfg_scale: int = 7, denoising_strength: float = 0.75, timeout: float = 60.0) -> Dict[str, Any]:
        url = f"{self.base_url}/sdapi/v1/img2img"
        payload = {
            "init_images": init_images_b64,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "steps": steps,
            "sampler_name": sampler_name,
            "width": width,
            "height": height,
            "sd_model_checkpoint": model,
            "seed": seed,
            "cfg_scale": cfg_scale,
            "denoising_strength": denoising_strength,
        }
        r = requests.post(url, json=payload, headers=self._headers(self.image_api_key), timeout=timeout)
        r.raise_for_status()
        return r.json()

    def upscale(self, image_b64: str, *, upscaler_1: str = "R-ESRGAN 4x+", upscaling_resize: int = 2,
                timeout: float = 60.0) -> Dict[str, Any]:
        url = f"{self.base_url}/sdapi/v1/extra-single-image"
        payload = {
            "image": image_b64,
            "upscaler_1": upscaler_1,
            "upscaling_resize": upscaling_resize,
        }
        r = requests.post(url, json=payload, headers=self._headers(self.image_api_key), timeout=timeout)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def format_error(e: Exception) -> str:
        import requests as _req
        if isinstance(e, _req.Timeout):
            return "Arliai request timed out."
        if isinstance(e, _req.ConnectionError):
            return "Cannot reach Arliai API. Check network and ARLIAI_BASE_URL."
        if isinstance(e, _req.HTTPError):
            resp = e.response
            code = resp.status_code if resp is not None else 'HTTP'
            try:
                detail = resp.text[:200] if resp is not None else ''
            except Exception:
                detail = ''
            return f"HTTP error {code} from Arliai. {detail}"
        return f"Unexpected error: {e}"

    def model_info(self, model: str, *, timeout: float = 10.0) -> Dict[str, Any]:
        """Best-effort model metadata fetch.
        Tries /v1/models then /v1/models/{model}. Returns {} on failure.
        """
        try:
            url = f"{self.base_url}/v1/models"
            r = requests.get(url, headers=self._headers(self.text_api_key), timeout=timeout)
            r.raise_for_status()
            data = r.json()
            items = data.get("data") if isinstance(data, dict) else data
            if isinstance(items, list):
                for it in items:
                    if str(it.get("id", "")).lower() == str(model).lower():
                        return it
        except Exception:
            pass
        try:
            url = f"{self.base_url}/v1/models/{model}"
            r = requests.get(url, headers=self._headers(self.text_api_key), timeout=timeout)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}
