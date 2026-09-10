"""VideoMontage MCP Server implementation.

Registers tools and prompts for AI agents over Model Context Protocol (MCP).
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any, Optional

try:
    from mcp.server.mcpserver import MCPServer
    ServerClass = MCPServer
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
        ServerClass = FastMCP
    except ImportError as e:
        raise RuntimeError("Neither mcp.server.mcpserver nor mcp.server.fastmcp is available. Run: pip install mcp>=1.2.0") from e

from mcp_server import adapters

logger = logging.getLogger("videomontage.server")


def create_server() -> Any:
    """Instantiate and configure the VideoMontage MCP Server with tools and prompts."""
    server = ServerClass("VideoMontage")

    # =========================================================================
    # MCP TOOLS
    # =========================================================================

    @server.tool(
        description=(
            "Inspect the current AI video production setup, check available providers "
            "(video, image, text-to-speech, music), detect missing API keys, and view 1-minute quick setup offers. "
            "Triggers: 'check setup', 'check keys', 'api keys', 'capabilities', 'doctor', 'status'."
        )
    )
    def videomontage_check_setup() -> str:
        """Inspect environment, configured tools, and quick setup offers."""
        data = adapters.check_setup()
        return json.dumps(data, indent=2)

    @server.tool(
        description=(
            "List all available video production pipelines and visual style playbooks (including 'midnight-keynote'). "
            "Triggers: 'list styles', 'list templates', 'pipelines', 'themes', 'playbooks', 'available styles'."
        )
    )
    def videomontage_list_pipelines_and_styles() -> str:
        """List pipelines and style playbooks."""
        data = adapters.list_pipelines_and_styles()
        return json.dumps(data, indent=2)

    @server.tool(
        description=(
            "Create a custom client style playbook from brand colors, typography, and mood for consistent video styling. "
            "Triggers: 'brand', 'branding', 'custom style', 'brand colors', 'client brand', 'custom theme'."
        )
    )
    def videomontage_extract_brand(
        name: str,
        primary_color: str,
        accent_color: str,
        background_color: str = "#0B0B0E",
        text_color: str = "#F5F5F7",
        font_heading: str = "Inter",
        font_body: str = "Inter",
        mood: str = "authoritative, sleek, visionary",
    ) -> str:
        """Create a client-specific style playbook YAML."""
        data = adapters.extract_brand(
            name=name,
            primary_color=primary_color,
            accent_color=accent_color,
            background_color=background_color,
            text_color=text_color,
            font_heading=font_heading,
            font_body=font_body,
            mood=mood,
        )
        return json.dumps(data, indent=2)

    @server.tool(
        description=(
            "Initialize a new video production project workspace, setting up directory layout, project marker, "
            "and generating the live web dashboard URL for Telegram/browser review. "
            "Triggers: 'new video', 'start video', 'create video project', 'init project', 'make a video'."
        )
    )
    def videomontage_init_project(
        project_id: str,
        title: str,
        pipeline_type: str = "animated-explainer",
        style_playbook: str = "midnight-keynote",
    ) -> str:
        """Initialize a new video project workspace."""
        data = adapters.init_project(
            project_id=project_id,
            title=title,
            pipeline_type=pipeline_type,
            style_playbook=style_playbook,
        )
        return json.dumps(data, indent=2)

    @server.tool(
        description=(
            "List existing video projects on disk to resume chat sessions, inspect their status, active stages, "
            "and check if human approval is pending. "
            "Triggers: 'list projects', 'resume video', 'show my videos', 'my projects', 'video history', 'continue project'."
        )
    )
    def videomontage_list_projects() -> str:
        """Discover existing video projects on disk for session resumption."""
        data = adapters.list_projects()
        return json.dumps(data, indent=2)

    @server.tool(
        description=(
            "Query the status and stage progress of a video project, including pending human approval gates and dashboard URL. "
            "Triggers: 'project status', 'video progress', 'stage status', 'check progress', 'pending approvals'."
        )
    )
    def videomontage_get_project_status(project_id: str) -> str:
        """Query lifecycle state of a specific video project."""
        data = adapters.get_project_status(project_id)
        return json.dumps(data, indent=2)

    @server.tool(
        description=(
            "Record a verified stage checkpoint with its canonical artifact JSON (brief, script, scene_plan, "
            "asset_manifest, edit_decisions, or render_report). Enforces human approval gate policies. "
            "Triggers: 'approve stage', 'advance stage', 'record checkpoint', 'human approval', 'save script'."
        )
    )
    def videomontage_record_checkpoint(
        project_id: str,
        stage: str,
        status: str,
        artifacts_json: str,
        human_approved: bool = False,
        error: Optional[str] = None,
    ) -> str:
        """Record an official pipeline checkpoint."""
        try:
            artifacts = json.loads(artifacts_json) if isinstance(artifacts_json, str) else artifacts_json
        except Exception as e:
            return json.dumps({"success": False, "error": f"Invalid artifacts_json: {e}"})

        data = adapters.record_checkpoint(
            project_id=project_id,
            stage=stage,
            status=status,
            artifacts=artifacts,
            human_approved=human_approved,
            error=error,
        )
        return json.dumps(data, indent=2)

    @server.tool(
        description=(
            "Generate an individual media asset (voiceover audio via TTS, image keyframe, or video clip) "
            "using OpenMontage provider selectors. Checks against Telegram 50MB file size limits. "
            "Triggers: 'generate voiceover', 'generate image', 'make music', 'tts', 'speech', 'keyframe'."
        )
    )
    def videomontage_generate_asset(
        capability: str,
        prompt: str,
        output_path: str,
        provider: Optional[str] = None,
        options_json: Optional[str] = None,
    ) -> str:
        """Generate a media asset (TTS audio, image, or video)."""
        options = None
        if options_json:
            try:
                options = json.loads(options_json)
            except Exception:
                pass

        data = adapters.generate_asset(
            capability=capability,
            prompt=prompt,
            output_path=output_path,
            provider=provider,
            options=options,
        )
        return json.dumps(data, indent=2)

    @server.tool(
        description=(
            "Execute video composition via Remotion, HyperFrames, or FFmpeg to render the deliverable MP4 video. "
            "Validates file size against Telegram 50MB bot upload limit. "
            "Triggers: 'render video', 'compile video', 'compose video', 'final mp4', 'export video', 'build video'."
        )
    )
    def videomontage_compose_and_render(
        project_id: str,
        edit_decisions_json: str,
        asset_manifest_json: Optional[str] = None,
        audio_path: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """Compose and render the final MP4 video."""
        try:
            edit_decisions = json.loads(edit_decisions_json) if isinstance(edit_decisions_json, str) else edit_decisions_json
        except Exception as e:
            return json.dumps({"success": False, "error": f"Invalid edit_decisions_json: {e}"})

        asset_manifest = None
        if asset_manifest_json:
            try:
                asset_manifest = json.loads(asset_manifest_json) if isinstance(asset_manifest_json, str) else asset_manifest_json
            except Exception:
                pass

        data = adapters.compose_and_render(
            project_id=project_id,
            edit_decisions=edit_decisions,
            asset_manifest=asset_manifest,
            audio_path=audio_path,
            output_path=output_path,
        )
        return json.dumps(data, indent=2)

    # =========================================================================
    # MCP PROMPTS
    # =========================================================================

    @server.prompt(
        description="Comprehensive production guide for planning, scripting, pacing, and orchestrating a video."
    )
    def create_video(
        topic: str,
        target_platform: str = "vertical-9:16",
        target_duration_seconds: int = 60,
        preferred_style: str = "midnight-keynote",
    ) -> str:
        """Generate structured instructions for orchestrating a video production."""
        # Word budget: ~2.2 - 2.5 words per second
        target_words = int(target_duration_seconds * 2.3)
        min_words = int(target_words * 0.9)
        max_words = int(target_words * 1.1)
        # Visual density: 1 shot every 4 - 8 seconds
        estimated_shots = max(3, round(target_duration_seconds / 5.5))

        return f"""# Video Production Blueprint: {topic}

You are the Director orchestrating a complete video production for VideoMontage.

## 1. Production Parameters
- **Topic**: {topic}
- **Target Platform**: {target_platform}
  - Vertical (9:16, 1080x1920) for TikTok, Reels, Shorts.
  - Landscape (16:9, 1920x1080) for YouTube and Web.
- **Target Duration**: {target_duration_seconds} seconds
- **Word Budget**: {min_words} to {max_words} words (strict: narration must match planned duration).
- **Target Shot Count**: ~{estimated_shots} visual scenes/cuts (Visual Density Rule: 1 visual change every 4–8 seconds).
- **Visual Playbook**: `{preferred_style}`
  - If using 'midnight-keynote': Matte obsidian (#0B0B0E) canvas, titanium white (#F5F5F7) typography, electric sapphire (#0A84FF) focal accents, Inter/Space Grotesk + JetBrains Mono.

## 2. Stage Progression & Human Checkpoints
Follow the pipeline stages strictly:
1. `idea` -> Initialize project with `videomontage_init_project` and save `brief`. Present 3 hook angles to user.
2. `script` -> Write structured script respecting the word budget ({min_words}-{max_words} words). Checkpoint as `awaiting_human` for user approval.
3. `scene_plan` -> Break script into ~{estimated_shots} scenes with exact timings and asset requirements.
4. `assets` -> Generate visual keyframes and narration audio with `videomontage_generate_asset`. Present keyframe storyboard for user sign-off.
5. `edit` -> Produce `edit_decisions` specifying transitions (fade, dissolve, slide-left, pop) and caption timings.
6. `compose` -> Render deliverable MP4 via `videomontage_compose_and_render`. Check file size for Telegram delivery.

Always provide the user with their live web dashboard link so they can follow progress in real-time.
"""

    @server.prompt(
        description="Format a stage review card for Telegram chat with approval buttons and dashboard link."
    )
    def review_stage(project_id: str, stage: str) -> str:
        """Prompt to format a human-in-the-loop review card in chat."""
        return f"""# Human Review Request: Project '{project_id}' — Stage '{stage}'

Present a clean, high-impact review summary in chat for the user:
1. **Stage Completed**: {stage.upper()}
2. **Key Highlights**: Summarize the 2-3 most important creative decisions made.
3. **Dashboard Link**: Invite the user to inspect the visual filmstrip / script on their dashboard.
4. **Approval Options**:
   - Reply 'Approve' (or tap [✅ Approve Stage]) to proceed to the next stage.
   - Reply with revision notes (or tap [🔄 Request Revisions]) to adjust.
"""

    return server


def main() -> None:
    """CLI entrypoint for running the MCP server."""
    server = create_server()
    # Default to stdio transport for direct agent integration
    if "--transport" in sys.argv:
        idx = sys.argv.index("--transport")
        if idx + 1 < len(sys.argv) and sys.argv[idx + 1] == "sse":
            port = 8000
            if "--port" in sys.argv:
                p_idx = sys.argv.index("--port")
                if p_idx + 1 < len(sys.argv):
                    port = int(sys.argv[p_idx + 1])
            logger.info(f"Starting VideoMontage MCP server over SSE on port {port}...")
            server.run(transport="sse", port=port)
            return

    # Standard stdio
    logger.info("Starting VideoMontage MCP server over stdio...")
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
