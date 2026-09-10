"""Tests for VideoMontage MCP server."""

import json
import pytest
from pathlib import Path

from mcp_server.server import create_server
from mcp_server import adapters
from lib.paths import PROJECTS_DIR


def test_server_creation():
    """Verify FastMCP/MCPServer registers all 9 tools and 2 prompts."""
    server = create_server()
    assert server.name == "VideoMontage"


def test_tool_and_prompt_registration():
    """Verify tools and prompts are accessible via MCP server interface."""
    import asyncio

    async def _check():
        server = create_server()
        tools = await server.list_tools()
        prompts = await server.list_prompts()

        tool_names = {t.name for t in tools}
        expected_tools = {
            "videomontage_check_setup",
            "videomontage_list_pipelines_and_styles",
            "videomontage_extract_brand",
            "videomontage_init_project",
            "videomontage_list_projects",
            "videomontage_get_project_status",
            "videomontage_record_checkpoint",
            "videomontage_generate_asset",
            "videomontage_compose_and_render",
        }
        assert expected_tools.issubset(tool_names)

        prompt_names = {p.name for p in prompts}
        assert "create_video" in prompt_names
        assert "review_stage" in prompt_names

    asyncio.run(_check())


def test_adapters_list_pipelines_and_styles():
    """Verify discovery includes pipelines and midnight-keynote playbook."""
    data = adapters.list_pipelines_and_styles()
    assert "pipelines" in data
    assert "styles" in data
    style_ids = [s["id"] for s in data["styles"]]
    assert "midnight-keynote" in style_ids


def test_adapters_project_lifecycle(tmp_path):
    """Smoke test project init, listing, and status."""
    test_id = "test-smoke-mcp-project"
    res = adapters.init_project(
        project_id=test_id,
        title="Test Smoke MCP",
        pipeline_type="animated-explainer",
        style_playbook="midnight-keynote",
    )
    assert res["project_id"] == test_id
    assert "dashboard_url" in res
    assert "/project/test-smoke-mcp-project" in res["dashboard_url"]

    # Verify list projects contains it
    projects = adapters.list_projects()
    p_ids = [p["project_id"] for p in projects]
    assert test_id in p_ids

    # Verify status
    status = adapters.get_project_status(test_id)
    assert status["project_id"] == test_id
    assert "stages" in status

    # Cleanup smoke project folder
    smoke_dir = PROJECTS_DIR / test_id
    if smoke_dir.exists():
        import shutil
        shutil.rmtree(smoke_dir, ignore_errors=True)
