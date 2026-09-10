"""OpenRouter video generation tool supporting Text-to-Video, Image-to-Video, and Reference-to-Video.

Interacts with OpenRouter's asynchronous Video Generation API (POST /api/v1/videos)
for models including Google Veo 3.1, MiniMax Hailuo 3, Alibaba Wan 2.7, etc.
"""

from __future__ import annotations

import base64
import mimetypes
import os
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

_DEFAULT_MODEL = "google/veo-3.1"
_KNOWN_MODELS = {
    "google/veo-3.1": {"cost_per_sec": 0.50, "default_duration": 6, "audio": True},
    "google/veo-2.0": {"cost_per_sec": 0.35, "default_duration": 5, "audio": False},
    "minimax/hailuo-3": {"cost_per_sec": 0.15, "default_duration": 5, "audio": True},
    "alibaba/wan-2.7": {"cost_per_sec": 0.12, "default_duration": 5, "audio": False},
    "bytedance/seedance-2.5": {"cost_per_sec": 0.20, "default_duration": 5, "audio": True},
}
_OPERATIONS = ("text_to_video", "image_to_video", "reference_to_video")


def _to_data_uri(path_str: str) -> str:
    """Read a local image file and return a base64 data URI."""
    p = Path(path_str).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"Reference image not found: {path_str}")
    mime, _ = mimetypes.guess_type(str(p))
    mime = mime or "image/png"
    with open(p, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


class OpenRouterVideo(BaseTool):
    name = "openrouter_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "openrouter"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:OPENROUTER_API_KEY"]
    install_instructions = openrouter_client.INSTALL_INSTRUCTIONS
    agent_skills = ["ai-video-gen"]

    capabilities = list(_OPERATIONS)
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "custom_duration": True,
        "aspect_ratio": True,
        "native_audio": True,
        "multi_model_gateway": True,
    }
    best_for = [
        "generating video via OpenRouter API with Veo 3.1, Hailuo 3, or Wan 2.7",
        "single API key covering video, images, and LLM orchestration",
        "reference-to-video and start/end frame image-to-video",
    ]
    quality_score = 0.88
    fallback_tools = ["atlas_video", "veo_video", "minimax_video", "kling_video"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Text prompt describing motion, scene, camera angle, and style.",
            },
            "model": {
                "type": "string",
                "default": _DEFAULT_MODEL,
                "description": "OpenRouter video model id (e.g., google/veo-3.1, minimax/hailuo-3, alibaba/wan-2.7).",
            },
            "operation": {
                "type": "string",
                "enum": list(_OPERATIONS),
                "default": "text_to_video",
                "description": "Generation mode.",
            },
            "duration": {
                "type": "integer",
                "default": 5,
                "description": "Duration in seconds (supported durations vary by model).",
            },
            "resolution": {
                "type": "string",
                "enum": ["480p", "720p", "1080p", "1K", "2K", "4K"],
                "default": "720p",
                "description": "Output video resolution.",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"],
                "default": "16:9",
                "description": "Aspect ratio of the generated clip.",
            },
            "generate_audio": {
                "type": "boolean",
                "default": True,
                "description": "Whether to generate synchronized audio alongside the video if supported.",
            },
            "seed": {"type": "integer", "description": "Optional random seed."},
            "image_url": {"type": "string", "description": "URL of first frame for image-to-video."},
            "image_path": {"type": "string", "description": "Local path of first frame for image-to-video."},
            "last_frame_url": {"type": "string", "description": "URL of last frame for image-to-video."},
            "last_frame_path": {"type": "string", "description": "Local path of last frame for image-to-video."},
            "reference_image_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of reference image URLs for style/character guidance.",
            },
            "reference_image_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of local reference image paths for style guidance.",
            },
            "callback_url": {"type": "string", "description": "Optional webhook callback URL."},
            "provider_options": {"type": "object", "description": "Provider-specific passthrough parameters."},
            "poll_interval": {"type": "number", "default": 10.0},
            "poll_timeout": {"type": "number", "default": 600.0},
            "output_path": {"type": "string", "description": "Where to write the downloaded MP4."},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, disk_mb=500, network_required=True)
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "operation", "duration", "aspect_ratio"]
    side_effects = ["writes video file to output_path", "calls OpenRouter API"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if openrouter_client.get_api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        model = str(inputs.get("model", _DEFAULT_MODEL))
        duration = int(inputs.get("duration", 5))
        rate = _KNOWN_MODELS.get(model, {}).get("cost_per_sec", 0.25)
        return round(rate * max(duration, 1), 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 120.0

    def is_operation_available(self, operation: str) -> bool:
        return operation in _OPERATIONS

    def _prepare_frames_and_refs(
        self, inputs: dict[str, Any]
    ) -> tuple[Optional[list[dict[str, Any]]], Optional[list[dict[str, Any]]]]:
        frame_images: list[dict[str, Any]] = []
        input_references: list[dict[str, Any]] = []

        # First frame
        first_url = inputs.get("image_url") or inputs.get("reference_image_url")
        if not first_url and (inputs.get("image_path") or inputs.get("reference_image_path")):
            first_url = _to_data_uri(inputs.get("image_path") or inputs["reference_image_path"])

        if first_url:
            frame_images.append({
                "type": "image_url",
                "image_url": {"url": first_url},
                "frame_type": "first_frame",
            })

        # Last frame
        last_url = inputs.get("last_frame_url") or inputs.get("end_image_url")
        if not last_url and (inputs.get("last_frame_path") or inputs.get("end_image_path")):
            last_url = _to_data_uri(inputs.get("last_frame_path") or inputs["end_image_path"])

        if last_url:
            frame_images.append({
                "type": "image_url",
                "image_url": {"url": last_url},
                "frame_type": "last_frame",
            })

        # Style / Character References
        for url in inputs.get("reference_image_urls") or []:
            input_references.append({"type": "image_url", "image_url": {"url": url}})

        for path in inputs.get("reference_image_paths") or []:
            input_references.append({"type": "image_url", "image_url": {"url": _to_data_uri(path)}})

        return (frame_images or None, input_references or None)

    def execute(self, inputs: dict[str, Any], dry_run: bool = False) -> ToolResult:
        prompt = inputs.get("prompt", "").strip()
        if not prompt:
            return ToolResult(success=False, error="Missing required parameter: prompt")

        model = str(inputs.get("model", _DEFAULT_MODEL))
        duration = int(inputs.get("duration", 5))
        resolution = inputs.get("resolution", "720p")
        aspect_ratio = inputs.get("aspect_ratio", "16:9")
        generate_audio = inputs.get("generate_audio", True)
        seed = inputs.get("seed")
        callback_url = inputs.get("callback_url")
        provider_options = inputs.get("provider_options")
        poll_interval = float(inputs.get("poll_interval", 10.0))
        poll_timeout = float(inputs.get("poll_timeout", 600.0))

        cost_est = self.estimate_cost(inputs)
        frame_images, input_references = self._prepare_frames_and_refs(inputs)

        if dry_run:
            return ToolResult(
                success=True,
                data={
                    "dry_run": True,
                    "provider": "openrouter",
                    "model": model,
                    "duration": duration,
                    "resolution": resolution,
                    "aspect_ratio": aspect_ratio,
                    "frame_images_count": len(frame_images or []),
                    "input_references_count": len(input_references or []),
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
            submission = openrouter_client.submit_video_generation(
                prompt=prompt,
                model=model,
                duration=duration,
                resolution=resolution,
                aspect_ratio=aspect_ratio,
                frame_images=frame_images,
                input_references=input_references,
                generate_audio=generate_audio,
                seed=seed,
                callback_url=callback_url,
                provider=provider_options,
            )
            job_id = submission["id"]
            polling_url = submission.get("polling_url")

            # Poll for completion
            result = openrouter_client.poll_video_generation(
                job_id=job_id,
                polling_url=polling_url,
                poll_interval=poll_interval,
                poll_timeout=poll_timeout,
            )

            # Determine download URL
            urls = result.get("unsigned_urls") or []
            content_url = urls[0] if urls else f"{openrouter_client.get_base_url()}/videos/{job_id}/content"

            # Determine destination output path
            output_path = inputs.get("output_path")
            if not output_path:
                stem = f"openrouter_video_{job_id}_{int(time.time())}"
                output_path = str(Path("output") / f"{stem}.mp4")

            saved_path = openrouter_client.download_media(
                url=content_url,
                output_path=output_path,
                api_key=openrouter_client.get_api_key(),
            )

            actual_cost = cost_est
            if "usage" in result and isinstance(result["usage"], dict) and "cost" in result["usage"]:
                actual_cost = float(result["usage"]["cost"])

            return ToolResult(
                success=True,
                data={
                    "job_id": job_id,
                    "model": model,
                    "video_path": str(saved_path),
                    "duration": duration,
                    "resolution": resolution,
                    "aspect_ratio": aspect_ratio,
                    "elapsed_seconds": round(time.time() - start_time, 2),
                    "unsigned_urls": urls,
                },
                cost_usd=actual_cost,
                artifact_paths=[str(saved_path)],
            )

        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"OpenRouter video generation failed: {exc}",
                cost_usd=0.0,
            )
