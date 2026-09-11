# OpenMontage Stage Gates

In OpenMontage, stage gates are **declarative and manifest-driven**. Rather than relying on separate procedural gate scripts, each pipeline manifest in `pipeline_defs/<pipeline>.yaml` declares the exact quality and approval gates for each stage:

## Gate Configuration Fields

Each stage entry in a pipeline manifest defines:

- `checkpoint_required`: Boolean indicating whether a stage must record a resumable checkpoint.
- `human_approval_default`: Boolean indicating whether human review and approval is required before the pipeline can advance to subsequent stages.
- `review_focus`: List of critical questions and dimensions evaluated by `skills/meta/reviewer.md`.
- `success_criteria`: Concrete schema and deliverable rules that must be met to achieve `status: "completed"`.

## Enforcement Mechanism

1. **Self-Review Protocol**: Stages are self-reviewed using `skills/meta/reviewer.md`. If critical findings exist, the stage enters revision up to `manifest.orchestration.max_revisions_per_stage` (default 3 rounds).
2. **Runtime Gate Enforcement**: `lib/checkpoint.py:write_checkpoint()` enforces that any stage with `human_approval_default: true` cannot be written with `status: "completed"` unless `human_approved=True` is provided. If approval is missing, the stage is written as `status: "awaiting_human"` and execution pauses.
3. **Prerequisite & Rewind Safety**: `lib/checkpoint.py` verifies all preceding stages are completed and approved before allowing later stages to write checkpoints. If an upstream stage is revised/rewound, downstream checkpoints are automatically archived to `history/` and marked `invalidated_by_upstream_rewind`.
