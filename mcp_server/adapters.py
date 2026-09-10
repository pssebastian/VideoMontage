"""Adapters connecting OpenMontage core systems to VideoMontage MCP server.

Provides clean, normalized helper methods for tool execution, state queries,
and asset delivery.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

import yaml

from lib.paths import PROJECTS_DIR, REPO_ROOT
from lib.checkpoint import (
    init_project as _lib_init_project,
    write_checkpoint as _lib_write_checkpoint,
    read_checkpoint as _lib_read_checkpoint,
    get_latest_checkpoint as _lib_get_latest_checkpoint,
    get_pipeline_stages,
    CheckpointValidationError,
)
from lib.pipeline_loader import list_pipelines, load_pipeline_readonly
from styles.playbook_loader import list_playbooks, load_playbook
from tools.tool_registry import registry

logger = logging.getLogger("videomontage.adapters")

TELEGRAM_MAX_FILE_BYTES = 50 * 1024 * 1024  # 50MB Telegram Bot API limit


def _load_config() -> dict[str, Any]:
    """Read config.yaml safely."""
    config_path = REPO_ROOT / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"Failed to read config.yaml: {e}")
        return {}


def get_dashboard_url(project_id: str) -> str:
    """Build dashboard URL for a project, using public tunnel if configured."""
    config = _load_config()
    dashboard_cfg = config.get("dashboard", {})
    public_base = dashboard_cfg.get("public_base_url") or config.get("backlot", {}).get("public_base_url")
    if public_base:
        return f"{public_base.rstrip('/')}/project/{project_id}"
    port = dashboard_cfg.get("port", 8000)
    return f"http://localhost:{port}/project/{project_id}"


def check_setup() -> dict[str, Any]:
    """Inspect environment, configured tools, missing API keys, and setup offers."""
    registry.ensure_discovered()
    summary = registry.provider_menu_summary()
    return {
        "status": "ready",
        "composition_runtimes": summary.get("composition_runtimes", {}),
        "capabilities": summary.get("capabilities", []),
        "quick_setup_offers": summary.get("setup_offers", []),
        "runtime_warnings": summary.get("runtime_warnings", []),
    }


def list_pipelines_and_styles() -> dict[str, Any]:
    """List available video pipelines and style playbooks."""
    pipelines = []
    for pipe_name in list_pipelines():
        try:
            m = load_pipeline_readonly(pipe_name)
            pipelines.append({
                "name": pipe_name,
                "title": m.get("name", pipe_name),
                "description": m.get("description", ""),
                "stability": m.get("stability", "production"),
                "stages": [s.get("name") for s in m.get("stages", [])],
            })
        except Exception:
            pipelines.append({"name": pipe_name})

    styles = []
    for s_name in list_playbooks():
        try:
            pb = load_playbook(s_name)
            ident = pb.get("identity", {})
            styles.append({
                "id": s_name,
                "name": ident.get("name", s_name),
                "category": ident.get("category", "cinematic"),
                "mood": ident.get("mood", ""),
                "pace": ident.get("pace", "deliberate"),
                "best_for": ident.get("best_for", ""),
            })
        except Exception:
            styles.append({"id": s_name})

    return {
        "pipelines": pipelines,
        "styles": styles,
        "default_style": "midnight-keynote",
    }


def init_project(
    project_id: str,
    title: str,
    pipeline_type: str = "animated-explainer",
    style_playbook: str = "midnight-keynote",
) -> dict[str, Any]:
    """Initialize project directory and metadata marker."""
    clean_id = re.sub(r"[^a-zA-Z0-9_\-]", "-", project_id.lower()).strip("-")
    project_dir = _lib_init_project(
        clean_id,
        title=title,
        pipeline_type=pipeline_type,
        style_playbook=style_playbook,
    )
    return {
        "project_id": clean_id,
        "title": title,
        "pipeline_type": pipeline_type,
        "style_playbook": style_playbook,
        "workspace_dir": str(project_dir),
        "dashboard_url": get_dashboard_url(clean_id),
    }


def list_projects() -> list[dict[str, Any]]:
    """Discover existing projects on disk for session resumption."""
    if not PROJECTS_DIR.exists():
        return []

    results = []
    for entry in PROJECTS_DIR.iterdir():
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        marker_file = entry / "project.json"
        if not marker_file.exists():
            continue

        try:
            with open(marker_file, encoding="utf-8") as f:
                marker = json.load(f)
        except Exception:
            marker = {}

        latest_cp = _lib_get_latest_checkpoint(PROJECTS_DIR, entry.name)
        active_stage = latest_cp.get("stage") if latest_cp else "idea"
        status = latest_cp.get("status") if latest_cp else "not_started"
        awaiting_human = latest_cp.get("status") == "awaiting_human" if latest_cp else False

        results.append({
            "project_id": entry.name,
            "title": marker.get("title", entry.name),
            "pipeline_type": marker.get("pipeline_type", "animated-explainer"),
            "style_playbook": marker.get("style_playbook", "midnight-keynote"),
            "created_at": marker.get("created_at"),
            "active_stage": active_stage,
            "status": status,
            "awaiting_human": awaiting_human,
            "dashboard_url": get_dashboard_url(entry.name),
            "_mtime": marker_file.stat().st_mtime,
        })

    results.sort(key=lambda p: p["_mtime"], reverse=True)
    for r in results:
        del r["_mtime"]
    return results


def get_project_status(project_id: str) -> dict[str, Any]:
    """Inspect current stage, checkpoints, and pending approvals for a project."""
    project_dir = PROJECTS_DIR / project_id
    if not project_dir.exists():
        return {"error": f"Project {project_id} not found."}

    marker_file = project_dir / "project.json"
    marker = {}
    if marker_file.exists():
        try:
            with open(marker_file, encoding="utf-8") as f:
                marker = json.load(f)
        except Exception:
            pass

    pipeline_type = marker.get("pipeline_type", "animated-explainer")
    stages = get_pipeline_stages(pipeline_type)

    stage_status: dict[str, Any] = {}
    pending_approval: Optional[str] = None
    last_completed: Optional[str] = None

    for s in stages:
        cp = _lib_read_checkpoint(PROJECTS_DIR, project_id, s)
        if cp:
            status = cp.get("status", "unknown")
            stage_status[s] = {
                "status": status,
                "human_approved": cp.get("human_approved", False),
                "timestamp": cp.get("timestamp"),
            }
            if status == "awaiting_human":
                pending_approval = s
            elif status == "completed":
                last_completed = s
        else:
            stage_status[s] = {"status": "not_started"}

    return {
        "project_id": project_id,
        "title": marker.get("title", project_id),
        "pipeline_type": pipeline_type,
        "style_playbook": marker.get("style_playbook", "midnight-keynote"),
        "stages": stage_status,
        "pending_human_approval": pending_approval,
        "last_completed_stage": last_completed,
        "dashboard_url": get_dashboard_url(project_id),
    }


def record_checkpoint(
    project_id: str,
    stage: str,
    status: str,
    artifacts: dict[str, Any],
    human_approved: bool = False,
    review: Optional[dict[str, Any]] = None,
    cost_snapshot: Optional[dict[str, Any]] = None,
    error: Optional[str] = None,
) -> dict[str, Any]:
    """Write an official pipeline checkpoint, strictly validating schemas and gates."""
    try:
        path = _lib_write_checkpoint(
            PROJECTS_DIR,
            project_id,
            stage,
            status,
            artifacts,
            human_approved=human_approved,
            review=review,
            cost_snapshot=cost_snapshot,
            error=error,
        )
        return {
            "success": True,
            "project_id": project_id,
            "stage": stage,
            "status": status,
            "checkpoint_path": str(path),
            "human_approved": human_approved,
        }
    except CheckpointValidationError as e:
        return {
            "success": False,
            "error": f"Checkpoint validation failed: {e}",
            "stage": stage,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stage": stage,
        }


def extract_brand(
    name: str,
    primary_color: str,
    accent_color: str,
    background_color: str = "#0B0B0E",
    text_color: str = "#F5F5F7",
    font_heading: str = "Inter",
    font_body: str = "Inter",
    mood: str = "authoritative, sleek, visionary",
) -> dict[str, Any]:
    """Create a client-specific style playbook YAML following the playbook schema."""
    slug = re.sub(r"[^a-zA-Z0-9_\-]", "-", name.lower()).strip("-")
    playbook_path = REPO_ROOT / "styles" / f"{slug}.yaml"

    playbook_data = {
        "identity": {
            "name": name,
            "category": "custom",
            "mood": mood,
            "pace": "deliberate",
            "best_for": f"Custom brand videos for {name}",
        },
        "taste_profile": {
            "design_read": f"{name} custom brand identity: cohesive brand palette, balanced typography, clear focal points.",
            "visual_variance": 4,
            "motion_intensity": 3,
            "information_density: ": 5,
            "palette_discipline": f"Background {background_color}, text {text_color}, accents {primary_color} and {accent_color}.",
            "layout_variation": "Alternating split and centered statement frames.",
            "reference_strategy": "One keyframe anchor per scene family.",
            "anti_patterns": ["off-brand color usage", "cluttered text cards"],
            "quality_gates": ["Contrast ratio >= 4.5:1 on all text."],
        },
        "visual_language": {
            "color_palette": {
                "primary": [primary_color],
                "accent": [accent_color],
                "background": background_color,
                "text": text_color,
                "muted": "#8E8E93",
            },
            "composition": "balanced brand framing with prominent visual anchors",
            "texture": "matte fields, subtle brand accents",
        },
        "typography": {
            "headings": {"font": font_heading, "weight": 700, "tracking": "-0.01em"},
            "body": {"font": font_body, "weight": 400, "line_height": 1.55},
            "code": {"font": "JetBrains Mono", "weight": 400},
            "stat_card": {"font": font_heading, "weight": 800, "size_multiplier": 3.2},
            "scale_system": "major_third",
            "weight_matrix": {"title": 800, "heading": 700, "body": 400, "caption": 500},
        },
        "motion": {
            "transitions": ["fade", "dissolve", "slide-left"],
            "animation_style": "smooth ease-out, restrained spring",
            "pacing_rules": {
                "min_scene_hold_seconds": 2.5,
                "max_scene_hold_seconds": 8.0,
                "text_card_hold_seconds": 3.5,
                "stat_card_hold_seconds": 3.0,
                "transition_duration_seconds": 0.4,
            },
            "entrance": "fade-up 10px",
            "exit": "fade",
        },
        "audio": {
            "voice_style": "confident, clear, professional",
            "music_mood": "modern acoustic or clean synth",
            "music_volume": 0.08,
            "sfx_style": "soft UI clicks",
            "ducking_threshold_db": -4,
        },
        "asset_generation": {
            "image_prompt_prefix": f"clean editorial photo with {primary_color} and {accent_color} accents, {mood}, ",
            "image_negative_prompt": "cluttered, cartoon, low quality, oversaturated",
            "diagram_style": "minimalist branded diagram with clean vectors",
            "consistency_anchors": [
                f"Consistent background: {background_color}",
                f"Brand primary: {primary_color}, accent: {accent_color}",
            ],
        },
        "overlays": {
            "stat_card": {"bg": background_color, "border": primary_color, "radius": 6},
            "key_term": {"bg": "rgba(255,255,255,0.08)", "text": accent_color, "radius": 4},
            "code_block": {"bg": background_color, "text": text_color, "highlight": accent_color},
        },
        "quality_rules": [
            "Text must meet 4.5:1 contrast ratio",
            "Brand colors must be preserved across scenes",
        ],
        "chart_palette": [primary_color, accent_color, "#30D158", "#FF9F0A"],
        "color_rules": {
            "harmony_type": "analogous",
            "contrast_validation": True,
            "colorblind_safe": True,
        },
    }

    with open(playbook_path, "w", encoding="utf-8") as f:
        yaml.dump(playbook_data, f, sort_keys=False)

    return {
        "success": True,
        "style_id": slug,
        "playbook_path": str(playbook_path),
        "message": f"Brand style '{name}' saved as '{slug}'. Pass style_playbook='{slug}' when initializing projects.",
    }


def generate_asset(
    capability: str,
    prompt: str,
    output_path: str,
    provider: Optional[str] = None,
    options: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Route asset generation through OpenMontage selector tools."""
    registry.ensure_discovered()
    selector_map = {
        "tts": "tts_selector",
        "image": "image_selector",
        "video": "video_selector",
    }
    tool_name = selector_map.get(capability.lower())
    if not tool_name:
        return {"success": False, "error": f"Unknown capability '{capability}'. Choose: tts, image, video."}

    tool = registry.get(tool_name)
    if not tool:
        return {"success": False, "error": f"Selector tool '{tool_name}' not available in registry."}

    params = {"prompt": prompt, "output_path": output_path}
    if capability.lower() == "tts":
        params["text"] = prompt
    if provider:
        params["provider"] = provider
    if options:
        params.update(options)

    result = tool.execute(params)
    out_file = Path(output_path)
    file_size_mb = (out_file.stat().st_size / (1024 * 1024)) if out_file.exists() else 0.0

    resp = {
        "success": result.success,
        "data": result.data,
        "error": result.error,
        "cost_usd": result.cost_usd,
        "output_path": output_path,
        "file_size_mb": round(file_size_mb, 2),
    }

    if file_size_mb > 50.0:
        resp["telegram_warning"] = "File exceeds 50MB Telegram Bot API limit. Video compression recommended."

    return resp


def compose_and_render(
    project_id: str,
    edit_decisions: dict[str, Any],
    asset_manifest: Optional[dict[str, Any]] = None,
    audio_path: Optional[str] = None,
    output_path: Optional[str] = None,
) -> dict[str, Any]:
    """Execute VideoCompose to build and render the final deliverable video."""
    registry.ensure_discovered()
    tool = registry.get("video_compose")
    if not tool:
        return {"success": False, "error": "video_compose tool not found in registry."}

    proj_dir = PROJECTS_DIR / project_id
    final_out = output_path or str(proj_dir / "renders" / "final.mp4")

    params = {
        "project_id": project_id,
        "edit_decisions": edit_decisions,
        "output_path": final_out,
    }
    if asset_manifest:
        params["asset_manifest"] = asset_manifest
    if audio_path:
        params["audio_path"] = audio_path

    result = tool.execute(params)
    out_file = Path(final_out)
    size_mb = (out_file.stat().st_size / (1024 * 1024)) if out_file.exists() else 0.0

    resp = {
        "success": result.success,
        "output_path": final_out,
        "file_size_mb": round(size_mb, 2),
        "data": result.data,
        "error": result.error,
        "dashboard_url": get_dashboard_url(project_id),
    }

    if size_mb > 50.0:
        resp["telegram_warning"] = (
            f"Rendered file is {round(size_mb, 1)}MB, exceeding Telegram's 50MB direct bot upload limit. "
            "Downscaling or CRF compression recommended."
        )

    return resp
