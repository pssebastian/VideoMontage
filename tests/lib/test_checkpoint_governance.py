from pathlib import Path
import json
import pytest

from lib.checkpoint import (
    init_project,
    write_checkpoint,
    read_checkpoint,
    get_completed_stages,
    get_invalidated_stages,
    get_stage_revision_count,
    check_revision_limits,
)
from lib.pipeline_loader import (
    load_pipeline,
    get_orchestration_config,
    get_max_revisions,
    get_max_send_backs,
    get_max_wall_time_minutes,
)


from tests.contracts.test_phase0_contracts import sample_artifact


def test_init_project_creates_all_asset_directories(tmp_path: Path):
    proj_dir = init_project("test_scaffold", title="Test Scaffold", pipeline_type="framework-smoke", pipeline_dir=tmp_path)
    assert (proj_dir / "assets" / "references").is_dir()
    assert (proj_dir / "assets" / "concept_anchors").is_dir()
    assert (proj_dir / "assets" / "keyframes").is_dir()
    assert (proj_dir / "assets" / "images").is_dir()
    assert (proj_dir / "assets" / "video").is_dir()
    assert (proj_dir / "assets" / "audio").is_dir()
    assert (proj_dir / "assets" / "music").is_dir()


def test_downstream_checkpoints_invalidated_on_upstream_rewind(tmp_path: Path):
    init_project("rewind_run", title="Rewind Run", pipeline_type="framework-smoke", pipeline_dir=tmp_path)

    # 1. Complete research
    write_checkpoint(
        tmp_path, "rewind_run", "research", "completed",
        {"research_brief": sample_artifact("research_brief")},
        pipeline_type="framework-smoke",
        human_approved=True,
    )

    # 2. Complete script (downstream)
    write_checkpoint(
        tmp_path, "rewind_run", "script", "completed",
        {"script": sample_artifact("script")},
        pipeline_type="framework-smoke",
        human_approved=True,
    )

    completed = get_completed_stages(tmp_path, "rewind_run", "framework-smoke")
    assert completed == ["research", "script"]

    # 3. Rewind to research with updated research
    write_checkpoint(
        tmp_path, "rewind_run", "research", "completed",
        {"research_brief": sample_artifact("research_brief")},
        pipeline_type="framework-smoke",
        human_approved=True,
    )

    # Script should now be invalidated
    script_cp = read_checkpoint(tmp_path, "rewind_run", "script")
    assert script_cp is not None
    assert script_cp["status"] == "invalidated_by_upstream_rewind"
    assert script_cp["rewind_source_stage"] == "research"
    assert "rewind_timestamp" in script_cp

    # get_completed_stages should now only show research
    completed_after = get_completed_stages(tmp_path, "rewind_run", "framework-smoke")
    assert completed_after == ["research"]

    # get_invalidated_stages should report script
    invalidated = get_invalidated_stages(tmp_path, "rewind_run", "framework-smoke")
    assert invalidated == ["script"]


def test_manifest_orchestration_getters():
    manifest = load_pipeline("talking-head")
    orch = get_orchestration_config(manifest)
    assert orch["max_revisions_per_stage"] == 3
    assert orch["max_send_backs"] == 3
    assert orch["max_wall_time_minutes"] == 15

    assert get_max_revisions(manifest) == 3
    assert get_max_send_backs(manifest) == 3
    assert get_max_wall_time_minutes(manifest) == 15


def test_revision_counting_and_limit_check(tmp_path: Path):
    init_project("rev_run", title="Rev Run", pipeline_type="framework-smoke", pipeline_dir=tmp_path)

    # Write stage 1st time
    write_checkpoint(
        tmp_path, "rev_run", "research", "completed",
        {"research_brief": sample_artifact("research_brief")},
        pipeline_type="framework-smoke",
        human_approved=True,
    )
    cp = read_checkpoint(tmp_path, "rev_run", "research")
    assert cp["metadata"]["revision_count"] == 1

    # Write stage 2nd time (re-write archives 1st to history/)
    write_checkpoint(
        tmp_path, "rev_run", "research", "completed",
        {"research_brief": sample_artifact("research_brief")},
        pipeline_type="framework-smoke",
        human_approved=True,
    )
    cp2 = read_checkpoint(tmp_path, "rev_run", "research")
    assert cp2["metadata"]["revision_count"] == 2

    # Check limits
    dummy_manifest = {"orchestration": {"max_revisions_per_stage": 2}}
    is_exceeded, current, max_rev = check_revision_limits(tmp_path, "rev_run", "research", dummy_manifest)
    assert is_exceeded is True
    assert current == 2
    assert max_rev == 2


def test_merge_decision_log_auto_suffixes_colliding_ids(tmp_path: Path):
    from lib.checkpoint import _merge_decision_log, _decision_log_path

    init_project("dec_run", title="Dec Run", pipeline_type="framework-smoke", pipeline_dir=tmp_path)

    # Initial decision
    log1 = {
        "decisions": [
            {
                "decision_id": "d-001",
                "stage": "proposal",
                "category": "voice_selection",
                "subject": "Narration TTS provider",
                "selected": "elevenlabs",
            }
        ]
    }
    _merge_decision_log(tmp_path, "dec_run", log1)

    # Revised decision reusing the SAME decision_id
    log2 = {
        "decisions": [
            {
                "decision_id": "d-001",
                "stage": "assets",
                "category": "voice_selection",
                "subject": "Narration TTS provider",
                "selected": "piper",
            }
        ]
    }
    _merge_decision_log(tmp_path, "dec_run", log2)

    with open(_decision_log_path(tmp_path, "dec_run"), encoding="utf-8") as f:
        merged = json.load(f)

    # Both decisions should be kept, with the second auto-suffixed as d-001-rev1
    assert len(merged["decisions"]) == 2
    assert merged["decisions"][0]["decision_id"] == "d-001"
    assert merged["decisions"][0]["selected"] == "elevenlabs"
    assert merged["decisions"][1]["decision_id"] == "d-001-rev1"
    assert merged["decisions"][1]["selected"] == "piper"


def test_rolling_history_retention_caps_at_5(tmp_path: Path):
    from lib.checkpoint import HISTORY_DIRNAME
    init_project("hist_run", title="Hist Run", pipeline_type="framework-smoke", pipeline_dir=tmp_path)

    # Write 7 revisions of research
    for i in range(7):
        write_checkpoint(
            tmp_path, "hist_run", "research", "completed",
            {"research_brief": sample_artifact("research_brief")},
            pipeline_type="framework-smoke",
            human_approved=True,
        )

    history_dir = tmp_path / "hist_run" / HISTORY_DIRNAME
    archives = list(history_dir.glob("checkpoint_research_*.json"))
    # Rolling retention should cap archived history files to 5
    assert len(archives) == 5

