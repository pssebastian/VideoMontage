"""Shared OpenRouter API client for video, image, and multimodal generation tools.

OpenRouter (https://openrouter.ai) provides access to LLMs, text-to-image models,
and a dedicated asynchronous video generation API (POST /api/v1/videos).

`requests` is imported lazily inside functions so tool discovery and startup stay fast.
"""

from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Any, Optional

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_VIDEO_MODEL = "google/veo-3.1"
DEFAULT_IMAGE_MODEL = "black-forest-labs/flux-1-schnell"

TERMINAL_SUCCESS = {"completed"}
TERMINAL_FAILURE = {"failed", "cancelled", "expired"}

ENV_KEYS = ("OPENROUTER_API_KEY", "OPENROUTER_KEY")

INSTALL_INSTRUCTIONS = (
    "Set OPENROUTER_API_KEY to your OpenRouter API key.\n"
    "  Get one at https://openrouter.ai/keys"
)


class OpenRouterError(RuntimeError):
    """Raised for any OpenRouter API or transport failure."""


def get_api_key() -> str | None:
    """Return the first configured OpenRouter API key."""
    for key in ENV_KEYS:
        val = os.environ.get(key)
        if val:
            return val.strip()
    return None


def get_base_url() -> str:
    """Return configured OpenRouter base URL or default."""
    url = os.environ.get("OPENROUTER_BASE_URL") or os.environ.get("OPENROUTER_API_BASE")
    if url:
        return url.strip().rstrip("/")
    return DEFAULT_BASE_URL


def _headers(api_key: str, json_body: bool = True) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://openmontage.video",
        "X-Title": "OpenMontage",
    }
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def submit_video_generation(
    prompt: str,
    *,
    model: str = DEFAULT_VIDEO_MODEL,
    duration: Optional[int] = None,
    resolution: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
    size: Optional[str] = None,
    frame_images: Optional[list[dict[str, Any]]] = None,
    input_references: Optional[list[dict[str, Any]]] = None,
    generate_audio: Optional[bool] = None,
    seed: Optional[int] = None,
    callback_url: Optional[str] = None,
    provider: Optional[dict[str, Any]] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Submit an asynchronous video generation job to OpenRouter.

    Returns the initial job envelope containing `id`, `polling_url`, and `status`.
    """
    import requests

    key = api_key or get_api_key()
    if not key:
        raise OpenRouterError("No OpenRouter API key configured. " + INSTALL_INSTRUCTIONS)

    root = (base_url or get_base_url()).rstrip("/")
    endpoint = f"{root}/videos"

    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
    }
    if duration is not None:
        payload["duration"] = int(duration)
    if resolution:
        payload["resolution"] = resolution
    if aspect_ratio:
        payload["aspect_ratio"] = aspect_ratio
    if size:
        payload["size"] = size
    if frame_images:
        payload["frame_images"] = frame_images
    if input_references:
        payload["input_references"] = input_references
    if generate_audio is not None:
        payload["generate_audio"] = bool(generate_audio)
    if seed is not None:
        payload["seed"] = int(seed)
    if callback_url:
        payload["callback_url"] = callback_url
    if provider:
        payload["provider"] = provider

    try:
        resp = requests.post(endpoint, headers=_headers(key), json=payload, timeout=timeout)
    except Exception as exc:
        raise OpenRouterError(f"Network error submitting video job to OpenRouter: {exc}") from exc

    if resp.status_code not in (200, 201, 202):
        text = resp.text[:500]
        raise OpenRouterError(f"OpenRouter video submission failed ({resp.status_code}): {text}")

    try:
        data = resp.json()
    except Exception as exc:
        raise OpenRouterError(f"OpenRouter returned non-JSON response: {resp.text[:500]}") from exc

    if not isinstance(data, dict) or "id" not in data:
        raise OpenRouterError(f"OpenRouter returned unexpected job payload: {data}")

    return data


def poll_video_generation(
    job_id: str,
    *,
    polling_url: Optional[str] = None,
    poll_interval: float = 10.0,
    poll_timeout: float = 600.0,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict[str, Any]:
    """Poll an OpenRouter video generation job until completion, failure, or timeout."""
    import requests

    key = api_key or get_api_key()
    if not key:
        raise OpenRouterError("No OpenRouter API key configured. " + INSTALL_INSTRUCTIONS)

    root = (base_url or get_base_url()).rstrip("/")
    url = polling_url or f"{root}/videos/{job_id}"

    deadline = time.time() + max(10.0, float(poll_timeout))
    interval = max(2.0, float(poll_interval))

    last_status = "pending"
    while time.time() < deadline:
        try:
            resp = requests.get(url, headers=_headers(key, json_body=False), timeout=30.0)
        except Exception as exc:
            # Network hiccup during polling is retryable until deadline
            time.sleep(interval)
            continue

        if resp.status_code >= 400:
            raise OpenRouterError(f"Failed to poll OpenRouter video job {job_id} ({resp.status_code}): {resp.text[:500]}")

        try:
            body = resp.json()
        except Exception as exc:
            raise OpenRouterError(f"OpenRouter returned non-JSON poll response: {resp.text[:500]}") from exc

        status = body.get("status", "").lower()
        last_status = status

        if status in TERMINAL_SUCCESS:
            return body
        if status in TERMINAL_FAILURE:
            err = body.get("error") or "Job failed or was cancelled"
            raise OpenRouterError(f"OpenRouter video generation failed with status '{status}': {err}")

        time.sleep(interval)

    raise OpenRouterError(f"Timed out after {poll_timeout}s waiting for video job {job_id} (last status: {last_status})")


def download_media(
    url: str,
    output_path: str | Path,
    *,
    api_key: Optional[str] = None,
) -> Path:
    """Download video or image binary content from an OpenRouter unsigned URL or content endpoint."""
    import requests

    dest = Path(output_path).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with requests.get(url, headers=headers, stream=True, timeout=120.0) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
    except Exception as exc:
        raise OpenRouterError(f"Failed to download generated media from {url}: {exc}") from exc

    return dest


def list_video_models(
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 30.0,
) -> list[dict[str, Any]]:
    """List available video generation models from OpenRouter."""
    import requests

    key = api_key or get_api_key()
    headers = _headers(key, json_body=False) if key else {}

    root = (base_url or get_base_url()).rstrip("/")
    endpoint = f"{root}/videos/models"

    try:
        resp = requests.get(endpoint, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                return data["data"]
    except Exception:
        pass

    # Fallback to general models endpoint with output_modalities filter
    try:
        endpoint_alt = f"{root}/models?output_modalities=video"
        resp = requests.get(endpoint_alt, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                return data["data"]
    except Exception:
        pass

    return []


def generate_image(
    prompt: str,
    *,
    model: str = DEFAULT_IMAGE_MODEL,
    width: Optional[int] = None,
    height: Optional[int] = None,
    aspect_ratio: Optional[str] = None,
    negative_prompt: Optional[str] = None,
    seed: Optional[int] = None,
    image_url: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Generate an image via OpenRouter using multimodal chat/completions or image generations."""
    import requests

    key = api_key or get_api_key()
    if not key:
        raise OpenRouterError("No OpenRouter API key configured. " + INSTALL_INSTRUCTIONS)

    root = (base_url or get_base_url()).rstrip("/")
    chat_endpoint = f"{root}/chat/completions"

    full_prompt = prompt
    if negative_prompt:
        full_prompt = f"{prompt} [Avoid: {negative_prompt}]"
    if aspect_ratio:
        full_prompt = f"{full_prompt} (Aspect ratio: {aspect_ratio})"

    content: list[dict[str, Any]] | str
    if image_url:
        content = [
            {"type": "text", "text": full_prompt},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
    else:
        content = full_prompt

    messages = [{"role": "user", "content": content}]

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    if seed is not None:
        payload["seed"] = seed

    try:
        resp = requests.post(chat_endpoint, headers=_headers(key), json=payload, timeout=timeout)
    except Exception as exc:
        raise OpenRouterError(f"Network error calling OpenRouter image generation: {exc}") from exc

    if resp.status_code != 200:
        raise OpenRouterError(f"OpenRouter image generation failed ({resp.status_code}): {resp.text[:500]}")

    try:
        data = resp.json()
    except Exception as exc:
        raise OpenRouterError(f"Non-JSON response from OpenRouter: {resp.text[:500]}") from exc

    return data
