"""Lightning.ai hosted LTX-Video Generator tool via Gradio client."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any, Optional

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

ENV_KEYS = ("LIGHTNING_LTX_URL", "LIGHTNING_VIDEO_URL", "LTX_GRADIO_URL")


class LightningLTXVideo(BaseTool):
    name = "lightning_ltx_video"
    version = "1.0.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "lightning_ai"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["python:gradio_client"]
    install_instructions = (
        "Set LIGHTNING_LTX_URL in .env to your running Lightning.ai Gradio URL.\n"
        "Example:\n"
        "  LIGHTNING_LTX_URL=https://xxxxxxxx.gradio.live\n"
        "  or LIGHTNING_LTX_URL=https://7860-01hxxxxxx.lightning.ai"
    )
    agent_skills = ["ltx2", "ai-video-gen"]

    capabilities = [
        "text_to_video",
        "image_to_video",
        "reference_conditioned",
    ]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "first_frame": True,
        "last_frame": True,
        "duration_control": True,
        "aspect_ratio_control": True,
        "self_hosted": True,
    }
    best_for = [
        "self-hosted LTX-2.3 22B video generation on Lightning.ai GPU Studios",
        "fast text-to-video and image-to-video rendering with zero local GPU load",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "Text prompt describing the scene and motion"},
            "first_frame": {"type": "string", "description": "Path to reference image for starting frame"},
            "last_frame": {"type": "string", "description": "Path to reference image for ending frame"},
            "input_references": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of reference image paths",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1", "4:3", "3:4"],
                "default": "16:9",
            },
            "resolution": {
                "type": "string",
                "enum": ["1080p", "720p", "540p", "480p"],
                "default": "720p",
            },
            "duration": {
                "type": "string",
                "enum": ["2s (49f)", "3s (73f)", "5s (121f)", "8s (193f)", "10s (241f)"],
                "default": "5s (121f)",
            },
            "duration_seconds": {"type": "number", "description": "Desired duration in seconds"},
            "guide_scale": {"type": "number", "default": 3.0},
            "num_steps": {"type": "integer", "default": 8},
            "seed": {"type": "integer", "default": -1},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["ConnectionError", "TimeoutError"])
    idempotency_key_fields = ["prompt", "seed", "duration", "aspect_ratio"]
    side_effects = ["writes generated mp4 to output_path"]

    def _get_url(self) -> str | None:
        for key in ENV_KEYS:
            val = os.environ.get(key)
            if val and val.strip():
                return val.strip().rstrip("/")
        return None

    def get_status(self) -> ToolStatus:
        if self._get_url():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        url = self._get_url()
        if not url:
            return ToolResult(
                success=False,
                error="Lightning LTX URL not configured. " + self.install_instructions,
            )

        start_time = time.time()
        try:
            from gradio_client import Client, handle_file
        except ImportError:
            return ToolResult(
                success=False,
                error="gradio_client not installed in environment. Run: pip install gradio_client",
            )

        try:
            client = Client(url)

            dur_val = inputs.get("duration", "5s (121f)")
            if "duration_seconds" in inputs:
                secs = float(inputs["duration_seconds"])
                if secs <= 2.5:
                    dur_val = "2s (49f)"
                elif secs <= 4.0:
                    dur_val = "3s (73f)"
                elif secs <= 6.5:
                    dur_val = "5s (121f)"
                elif secs <= 9.0:
                    dur_val = "8s (193f)"
                else:
                    dur_val = "10s (241f)"

            img_start_raw = inputs.get("first_frame")
            if not img_start_raw and inputs.get("input_references"):
                img_start_raw = inputs["input_references"][0]

            img_start_param = handle_file(img_start_raw) if img_start_raw and Path(img_start_raw).exists() else None
            img_end_raw = inputs.get("last_frame")
            img_end_param = handle_file(img_end_raw) if img_end_raw and Path(img_end_raw).exists() else None

            aspect = inputs.get("aspect_ratio", "16:9")
            res = inputs.get("resolution", "720p")
            prompt = inputs["prompt"]
            seed = int(inputs.get("seed", -1))
            guide_scale = float(inputs.get("guide_scale", 3.0))
            num_steps = int(inputs.get("num_steps", 8))

            result = client.predict(
                prompt=prompt,
                img_start=img_start_param,
                img_end=img_end_param,
                seed=seed,
                duration=dur_val,
                resolution=res,
                aspect_ratio=aspect,
                guide_scale=guide_scale,
                num_steps=num_steps,
                api_name="/generate"
            )

            if isinstance(result, (list, tuple)):
                raw_out = result[0]
                status_text = result[1] if len(result) > 1 else "Done"
            else:
                raw_out = result
                status_text = "Done"

            if isinstance(raw_out, dict):
                generated_video_path = raw_out.get("video") or raw_out.get("path")
            else:
                generated_video_path = str(raw_out) if raw_out else None

            if not generated_video_path or not Path(generated_video_path).exists():
                return ToolResult(
                    success=False,
                    error=f"Lightning LTX generation returned no valid video file (got {raw_out}). Status: {status_text}",
                )

            out_target = Path(inputs.get("output_path", "ltx_output.mp4"))
            out_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(generated_video_path, out_target)

            elapsed = round(time.time() - start_time, 2)
            clean_status = str(status_text).encode("ascii", "ignore").decode("ascii").strip()
            return ToolResult(
                success=True,
                data={
                    "provider": "lightning_ai",
                    "model": "ltx2_22B_distilled",
                    "output_path": str(out_target),
                    "aspect_ratio": aspect,
                    "resolution": res,
                    "duration": dur_val,
                    "status_note": clean_status,
                },
                artifacts=[str(out_target)],
                duration_seconds=elapsed,
                cost_usd=0.0,
            )

        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Lightning LTX call failed: {exc}",
            )
