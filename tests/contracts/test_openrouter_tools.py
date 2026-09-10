"""Contract tests for OpenRouter provider tools (video and image generation).

These tests verify that OpenRouterVideo and OpenRouterImage satisfy the
OpenMontage BaseTool contract, register with ToolRegistry, and integrate
with VideoSelector and ImageSelector.
"""

import json
from pathlib import Path

import pytest

from tools.base_tool import (
    BaseTool,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)
from tools.graphics.image_selector import ImageSelector
from tools.graphics.openrouter_image import OpenRouterImage
from tools.tool_registry import ToolRegistry
from tools.video.openrouter_video import OpenRouterVideo
from tools.video.video_selector import VideoSelector

TOOLS = [OpenRouterVideo, OpenRouterImage]


@pytest.mark.parametrize("cls", TOOLS, ids=lambda c: c.name)
class TestOpenRouterContract:

    def test_inherits_base_tool(self, cls):
        assert issubclass(cls, BaseTool)

    def test_has_required_identity(self, cls):
        tool = cls()
        assert tool.name in ("openrouter_video", "openrouter_image")
        assert tool.version
        assert tool.capability in ("video_generation", "image_generation")
        assert tool.provider == "openrouter"
        assert tool.tier == ToolTier.GENERATE
        assert tool.stability == ToolStability.BETA
        assert tool.runtime == ToolRuntime.API

    def test_has_input_schema(self, cls):
        tool = cls()
        schema = tool.input_schema
        assert schema.get("type") == "object"
        assert "prompt" in schema.get("properties", {})
        assert "prompt" in schema.get("required", [])

    def test_has_capabilities(self, cls):
        tool = cls()
        assert len(tool.capabilities) > 0

    def test_get_status_without_key(self, cls, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_KEY", raising=False)
        tool = cls()
        assert tool.get_status() == ToolStatus.UNAVAILABLE

    def test_get_status_with_key(self, cls, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-testkey123")
        tool = cls()
        assert tool.get_status() == ToolStatus.AVAILABLE

    def test_get_info_returns_dict(self, cls):
        tool = cls()
        info = tool.get_info()
        assert isinstance(info, dict)
        assert info["name"] == tool.name
        assert info["provider"] == "openrouter"
        assert "input_schema" in info

    def test_estimate_cost_positive(self, cls):
        tool = cls()
        cost = tool.estimate_cost({"prompt": "A sunset over mountains", "duration": 5})
        assert isinstance(cost, float)
        assert cost >= 0.0

    def test_estimate_runtime_positive(self, cls):
        tool = cls()
        runtime = tool.estimate_runtime({"prompt": "test"})
        assert isinstance(runtime, float)
        assert runtime > 0.0


class TestOpenRouterVideoTool:

    def test_dry_run_execution(self):
        tool = OpenRouterVideo()
        result = tool.execute(
            {
                "prompt": "A neon glowing city on a rainy night",
                "model": "google/veo-3.1",
                "duration": 6,
                "resolution": "1080p",
                "aspect_ratio": "16:9",
            },
            dry_run=True,
        )
        assert result.success is True
        assert result.data["dry_run"] is True
        assert result.data["provider"] == "openrouter"
        assert result.data["model"] == "google/veo-3.1"
        assert result.data["duration"] == 6

    def test_missing_prompt_fails(self):
        tool = OpenRouterVideo()
        result = tool.execute({"prompt": ""}, dry_run=False)
        assert result.success is False
        assert "prompt" in result.error.lower()

    def test_frame_preparation_with_data_uri(self, tmp_path):
        img_file = tmp_path / "frame.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01")

        tool = OpenRouterVideo()
        frames, refs = tool._prepare_frames_and_refs({
            "image_path": str(img_file),
            "reference_image_urls": ["https://example.com/ref.png"],
        })
        assert frames is not None
        assert len(frames) == 1
        assert frames[0]["frame_type"] == "first_frame"
        assert frames[0]["image_url"]["url"].startswith("data:image/png;base64,")

        assert refs is not None
        assert len(refs) == 1
        assert refs[0]["image_url"]["url"] == "https://example.com/ref.png"


class TestOpenRouterImageTool:

    def test_dry_run_execution(self):
        tool = OpenRouterImage()
        result = tool.execute(
            {
                "prompt": "A futuristic architectural pavilion in a forest",
                "model": "black-forest-labs/flux-1-schnell",
                "aspect_ratio": "16:9",
            },
            dry_run=True,
        )
        assert result.success is True
        assert result.data["dry_run"] is True
        assert result.data["provider"] == "openrouter"
        assert result.data["model"] == "black-forest-labs/flux-1-schnell"

    def test_missing_prompt_fails(self):
        tool = OpenRouterImage()
        result = tool.execute({"prompt": "   "}, dry_run=False)
        assert result.success is False
        assert "prompt" in result.error.lower()


class TestRegistryAndSelectorIntegration:

    def test_tools_discovered_in_registry(self):
        registry = ToolRegistry()
        registry.discover()
        assert registry.get("openrouter_video") is not None
        assert registry.get("openrouter_image") is not None

    def test_video_selector_discovers_openrouter(self):
        video_selector = VideoSelector()
        providers = video_selector._providers()
        provider_names = [p.name for p in providers]
        assert "openrouter_video" in provider_names

    def test_image_selector_discovers_openrouter(self):
        image_selector = ImageSelector()
        providers = image_selector._providers()
        provider_names = [p.name for p in providers]
        assert "openrouter_image" in provider_names

    def test_provider_menu_contains_openrouter(self):
        registry = ToolRegistry()
        registry.discover()
        menu = registry.provider_menu()
        assert "video_generation" in menu
        assert "image_generation" in menu

        video_providers = [
            item["provider"]
            for item in menu["video_generation"]["available"] + menu["video_generation"]["unavailable"]
        ]
        assert "openrouter" in video_providers

        image_providers = [
            item["provider"]
            for item in menu["image_generation"]["available"] + menu["image_generation"]["unavailable"]
        ]
        assert "openrouter" in image_providers
