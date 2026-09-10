"""OpenRouter image generation and editing tool.

Provides access to text-to-image and image-to-image models via OpenRouter
(e.g., FLUX.1 schnell/dev, Recraft, GPT Image models).
"""

from __future__ import annotations

import base64
import mimetypes
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

from tools import openrouter_client
from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

_DEFAULT_MODEL = "black-forest-labs/flux-1-schnell"
_KNOWN_IMAGE_MODELS = {
    "black-forest-labs/flux-1-schnell": {"cost": 0.003, "desc": "Fast 4-step FLUX generator"},
    "black-forest-labs/flux-1-dev": {"cost": 0.025, "desc": "High quality FLUX development model"},
    "recraft/recraft-20b": {"cost": 0.04, "desc": "Design, vector, and photoreal rendering"},
    "openai/gpt-5-image": {"cost": 0.05, "desc": "OpenAI multimodal visual generation"},
}


def _to_data_uri(path_str: str) -> str:
    p = Path(path_str).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"Source image not found: {path_str}")
    mime, _ = mimetypes.guess_type(str(p))
    mime = mime or "image/png"
    with open(p, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


class OpenRouterImage(BaseTool):
    name = "openrouter_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "openrouter"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:OPENROUTER_API_KEY"]
    install_instructions = openrouter_client.INSTALL_INSTRUCTIONS
    agent_skills = ["flux-best-practices"]

    capabilities = ["generate_image", "text_to_image", "image_edit"]
    supports = {
        "custom_size": True,
        "aspect_ratio": True,
        "image_edit": True,
        "multi_model_gateway": True,
    }
    best_for = [
        "generating images with FLUX, Recraft, or GPT Image models via OpenRouter",
        "single unified key covering image generation, video, and text orchestration",
    ]
    quality_score = 0.88
    fallback_tools = ["flux_image", "atlas_image", "google_imagen", "openai_image"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Text prompt describing visual style, subject, composition, and lighting.",
            },
            "model": {
                "type": "string",
                "default": _DEFAULT_MODEL,
                "description": "OpenRouter image model id (e.g. black-forest-labs/flux-1-schnell, recraft/recraft-20b).",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "21:9"],
                "default": "16:9",
                "description": "Aspect ratio of the generated image.",
            },
            "width": {"type": "integer", "description": "Explicit width in pixels."},
            "height": {"type": "integer", "description": "Explicit height in pixels."},
            "negative_prompt": {"type": "string", "description": "Concepts or artifacts to avoid."},
            "seed": {"type": "integer", "description": "Optional random seed."},
            "image_url": {"type": "string", "description": "URL of reference/input image for editing."},
            "image_path": {"type": "string", "description": "Local file path of input image for editing."},
            "output_path": {"type": "string", "description": "Where to save the resulting image file."},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, disk_mb=250, network_required=True)
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "aspect_ratio", "width", "height"]
    side_effects = ["writes image file to output_path", "calls OpenRouter API"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if openrouter_client.get_api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        model = str(inputs.get("model", _DEFAULT_MODEL))
        return _KNOWN_IMAGE_MODELS.get(model, {}).get("cost", 0.03)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 20.0

    def is_operation_available(self, operation: str) -> bool:
        return operation in self.capabilities

    def execute(self, inputs: dict[str, Any], dry_run: bool = False) -> ToolResult:
        prompt = inputs.get("prompt", "").strip()
        if not prompt:
            return ToolResult(success=False, error="Missing required parameter: prompt")

        model = str(inputs.get("model", _DEFAULT_MODEL))
        aspect_ratio = inputs.get("aspect_ratio", "16:9")
        width = inputs.get("width")
        height = inputs.get("height")
        negative_prompt = inputs.get("negative_prompt")
        seed = inputs.get("seed")

        image_url = inputs.get("image_url")
        if not image_url and inputs.get("image_path"):
            image_url = _to_data_uri(inputs["image_path"])

        cost_est = self.estimate_cost(inputs)

        if dry_run:
            return ToolResult(
                success=True,
                data={
                    "dry_run": True,
                    "provider": "openrouter",
                    "model": model,
                    "aspect_ratio": aspect_ratio,
                    "width": width,
                    "height": height,
                    "estimated_cost_usd": cost_est,
                },
                cost_usd=0.0,
            )

        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(
                success=False,
                error="OpenRouter API key is not configured. " + self.install_instructions,
            )

        start_time = time.time()
        try:
            resp_data = openrouter_client.generate_image(
                prompt=prompt,
                model=model,
                width=width,
                height=height,
                aspect_ratio=aspect_ratio,
                negative_prompt=negative_prompt,
                seed=seed,
                image_url=image_url,
            )

            # Extract image content: check choices[0].message.content or choices[0].message.image
            # or standard URL / data URI embedded in response
            output_path = inputs.get("output_path")
            if not output_path:
                stem = f"openrouter_img_{int(time.time())}"
                output_path = str(Path("output") / f"{stem}.png")

            dest = Path(output_path).resolve()
            dest.parent.mkdir(parents=True, exist_ok=True)

            image_saved = False
            # Check message format
            choices = resp_data.get("choices") or []
            if choices:
                msg = choices[0].get("message", {})
                content = msg.get("content") or ""
                # Check for base64 data URI in content: data:image/...;base64,...
                match = re.search(r"data:image/[a-zA-Z]+;base64,([A-Za-z0-9+/=]+)", str(content))
                if match:
                    img_bytes = base64.b64decode(match.group(1))
                    with open(dest, "wb") as f:
                        f.write(img_bytes)
                    image_saved = True
                else:
                    # Check for image URL in content: https://...
                    url_match = re.search(r"https?://[^\s)\]\"']+\.(?:png|jpg|jpeg|webp)", str(content))
                    if url_match:
                        openrouter_client.download_media(url_match.group(0), dest)
                        image_saved = True

            # If not in choices, check top-level data array (standard OpenAI image format)
            if not image_saved and "data" in resp_data and isinstance(resp_data["data"], list) and resp_data["data"]:
                item = resp_data["data"][0]
                if "b64_json" in item:
                    img_bytes = base64.b64decode(item["b64_json"])
                    with open(dest, "wb") as f:
                        f.write(img_bytes)
                    image_saved = True
                elif "url" in item:
                    openrouter_client.download_media(item["url"], dest)
                    image_saved = True

            if not image_saved:
                # If content is text, save output description and return data
                return ToolResult(
                    success=True,
                    data={
                        "model": model,
                        "raw_response": resp_data,
                        "elapsed_seconds": round(time.time() - start_time, 2),
                    },
                    cost_usd=cost_est,
                )

            return ToolResult(
                success=True,
                data={
                    "model": model,
                    "image_path": str(dest),
                    "aspect_ratio": aspect_ratio,
                    "elapsed_seconds": round(time.time() - start_time, 2),
                },
                cost_usd=cost_est,
                artifact_paths=[str(dest)],
            )

        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"OpenRouter image generation failed: {exc}",
                cost_usd=0.0,
            )
