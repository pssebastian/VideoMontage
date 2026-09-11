# Asset Intake Protocol — Meta Skill

## When to Use

Read this skill when a pipeline director (scene-director or asset-director) tells you to. It teaches the complete Two-Part Asset Intake, Pre-Generation Cost Approval, and Edge-Case Handling protocols. It replaces improvised reference gathering with a structured, user-governed workflow.

**Part 1** is used by scene-directors (during the scene_plan stage). It is a **strictly zero-cost ($0.00) planning and reference audit step**. No billable images or keyframes are generated during Part 1.
**Part 2** is used by asset-directors (at the assets stage). It executes the **Mixed Asset Generation Strategy** (visual keyframes, concept anchors, and audio assets) with mandatory cost disclosure and complete provenance registration into the asset manifest.

Both parts share the **Pre-Generation Service & Cost Disclosure Card** — the mandatory approval gate before any paid generation call.

---

## Part 1 — Zero-Cost Visual Intake & Scene Strategy Planning ($0.00)

> [!IMPORTANT]
> **Zero-Cost Planning Gate**: The `scene_plan` stage must complete with **$0.00 in generation spend**. Do not call image generation tools, character sheet generators, or keyframe models during this stage. Visual intake in Part 1 is purely declarative and structural.

### Step 1: Script Entity Audit

Walk every beat of the approved script and enumerate every visual entity that must appear on screen:

| Category | Examples | Where to look |
|----------|----------|--------------|
| Characters | Protagonists, supporting cast, crowds | Dialogue lines, stage directions, character descriptions |
| Locations / Environments | Rooms, exteriors, abstract spaces | Scene settings, establishing beats |
| Props / Objects | Devices, vehicles, branded items | Action descriptions, enhancement cues |
| Costumes / States | Outfit changes, transformations, aging | Timeline progression, script notes |

Produce a **Visual Entity Registry** — a flat list of `{ entity_id, category, description, scenes_used_in[] }`.

### Step 2: Cross-Reference Against User References

Check `projects/<id>/assets/references/` for any files the user has already provided. For each entity in the registry:

- **Matched**: File exists → bind it as `reference_path` on the entity.
- **Unmatched**: No file → mark as `status: "missing"`.

Also check: are there reference files that don't match any entity? If so, ask the user what they are for — they may reveal a creative intent the script didn't capture.

### Step 3: Asset Gap Report & Generation Planning

Present a structured report to the user:

```
## Visual Asset Status & Plan

### ✅ Matched (reference provided)
| Entity | Category | Reference File | Scenes |
|--------|----------|---------------|--------|
| Detective Lin | Character | references/detective_lin.png | 1, 3, 5, 7 |
| Office interior | Environment | references/office.jpg | 2, 4 |

### ❌ Missing (no reference)
| Entity | Category | Scenes | Options |
|--------|----------|--------|---------|
| Suspect | Character | 3, 6 | (A) You provide a reference, (B) Generate concept art in assets stage, (C) Rewrite scenes to avoid |
| Warehouse exterior | Environment | 5 | (A) You provide a reference, (B) Generate concept art in assets stage, (C) Rewrite scenes to avoid |

### Action Required
Please choose an option for each missing asset, or upload reference files to assets/references/.
```

**Wait for user response.** Record the user's choice in the scene plan metadata.

### Step 4: Mixed Visual Strategy Planning (Complexity-Based)

For each scene in the `scene_plan`, determine its visual production strategy based on scene metadata:

1. **`procedural`** (Cost: $0.00):
   - For `text_card`, `diagram`, `chart`, `code_snippet`, or `synthetic_terminal` scene types.
   - Rendered natively via Remotion/HyperFrames/SVG. No image/video generation needed.
2. **`source_footage`** (Cost: $0.00):
   - When the user provided video clips or screen recordings in `assets/references/` or `assets/video/`.
3. **`temporal_recycling`** (Cost: $0.00 for start frame):
   - When the scene continues directly from the prior scene.
   - Reuses the preceding scene's end frame as the starting anchor, preserving continuity without regenerating.
4. **`single_i2v`** (Low-moderate cost):
   - For scenes with moderate camera motion or ambient movement. Single anchor image used as video input.
5. **`start_and_end_frame`** (Standard cost):
   - For hero moments, major character actions, or precise choreographies requiring start and end keyframes.
6. **`direct_t2v`** (Direct text-to-video):
   - For atmospheric transitions, background plates, or b-roll where character identity locks are not required.

Populate each scene definition in `scene_plan.json` with its planned `keyframe_strategy`, required prompts, and entity bindings, **without generating the image files**.

Proceed to checkpoint the scene plan with `status="completed"` (or `status="awaiting_human"` if required by policy). The cost remains **$0.00**.

---

## Part 2 — Asset Generation & Audio Intake (Assets Stage)

Part 2 runs during the `assets` stage under the Asset Director.

### Phase 2A — Visual Asset Generation & Provenance Registration

#### Step 1: Pre-Generation Service & Cost Disclosure Card
Before generating any concept anchors or keyframes, calculate total estimated cost and present the mandatory **Service & Cost Disclosure Card** (see full specification below) for user sign-off.

#### Step 2: Generate Concept Anchors (Option B Entities)
For entities where the user approved AI concept generation:
1. **Character sheets**: Generate multi-pose reference image using `image_selector`.
2. **Environment plates**: Wide establishing shots saved to `projects/<id>/assets/concept_anchors/`.
3. **Prop renders**: Isolated props on neutral backgrounds.

#### Step 3: Generate Storyboard Keyframes
Execute the approved `keyframe_strategy` per scene:
- Generate start frames and end frames as planned, saved to `projects/<id>/assets/keyframes/<scene_id>_start.png` and `<scene_id>_end.png`.
- Condition end frames on start frames to avoid identity drift.
- Support **selective re-roll**: individual frames can be re-generated without invalidating others.

#### Step 4: Mandatory Provenance Registration & Budget Reconciliation
Every visual asset produced (concept anchors, keyframes, diagrams) **MUST be registered** into `asset_manifest.assets[]`:

```json
{
  "id": "keyframe-scene-3-start",
  "type": "keyframe",
  "scene_id": "scene-3",
  "path": "assets/keyframes/scene-3_start.png",
  "source": "generated",
  "tool": "image_selector",
  "model": "imagen-3",
  "seed": 42891,
  "cost_usd": 0.04,
  "provenance": {
    "prompt": "Detective Lin inspecting desk, dramatic noir lighting...",
    "reference_ids": ["detective_lin", "office_interior"]
  }
}
```

- **Budget reconciliation**: Add all keyframe and anchor costs into `asset_manifest.total_cost_usd`.
- **Forward Compatibility**: If a legacy or resumed project already has generated keyframes recorded in `scene_plan`, adopt those records directly into `asset_manifest.assets[]` without re-generating them.

---

### Phase 2B — Non-Visual & Audio Asset Intake

### Step 1: Audio Entity Audit

From the approved scene plan and script, enumerate every audio asset needed:

| Category | Required Information |
|----------|---------------------|
| Voiceover / Narration | Which sections need narration, total word count, language, intended tone |
| Character Dialogue | Which characters speak, line count per character, emotional range |
| Background Music | Mood per section, transitions, total duration, tempo preferences |
| Sound Effects | Per-scene SFX needs (whooshes, impacts, ambience, UI sounds) |
| Ambient Audio | Environmental audio (crowd, traffic, rain, office hum) |

### Step 2: Check User Assets First

**MANDATORY**: Before proposing ANY audio generation, ask the user:

```
## Audio Assets Check

I need the following audio for this video:

### Voiceover
- X sections, ~Y words total
- Do you have a voice recording, or should I generate narration?

### Music
- ~Z seconds of background music needed
- Mood: [describe per section]
- Do you have a music track? (You can drop it in `music_library/`)
- Or should I find/generate one?

### Sound Effects
- [list specific SFX needed per scene]
- Do you have SFX packs, or should I generate them?

### Action Required
For each category, let me know: (A) you'll provide it, (B) I should generate it (I'll show costs first), or (C) skip it.
```

**Wait for user response.** Do not silently generate any audio asset.

### Step 3: Audio Gap Report

For items the user chose Option B, present the service options with cost disclosure (same card format as Part 1).

### Step 4: Pre-Generation Cost Disclosure

Apply the **Service & Cost Disclosure Card** (below) to every audio generation call.

### Step 5: Sample Approval

Before batch synthesis:

1. **Voice sample**: Generate a 1-sentence sample (~5-10 seconds) using the chosen TTS provider and voice. Present for approval. Let the user hear the voice, speed, and tone before committing to the full narration.

2. **Music preview**: Generate or retrieve a 15-second preview clip. Present for approval.

3. **SFX sample**: Generate one representative sound effect. Present for approval.

Only after all samples are approved, proceed with full generation.

### Step 6: Pronunciation & Timing Reconciliation

#### Technical Jargon Pronunciation Mapping

Before full TTS generation, build a pronunciation map:

```
## Pronunciation Confirmation

The script contains these technical/specialized terms:
| Term | Default Pronunciation | Your Preference |
|------|----------------------|-----------------|
| CUDA | "KOO-dah" | |
| PostgreSQL | "post-GRES-Q-L" | |
| Kubernetes | "koo-ber-NET-eez" | |

Please confirm or correct each pronunciation.
```

If the TTS provider supports SSML or phoneme tags, apply the confirmed pronunciations.

#### Audio Duration vs. Visual Timing Drift

After generating the full narration:

1. Compare `audio_duration_seconds` against the video's total duration.
2. If drift exceeds 1 second, present options:
   - Extend the video's closing/breathing scenes to match audio
   - Speed up narration slightly (within 1.1x — beyond that, re-record)
   - Tighten the script and regenerate narration
3. Per-scene alignment: check that each section's narration fits within its scene's time slot. Flag overruns.

#### Multi-Speaker Dialogue Allocation

When the script has character dialogue:

1. Present distinct voice options for each character.
2. Assign a unique voice ID per character.
3. Ensure voices are sufficiently distinct (different pitch, pace, or accent).
4. Generate one sample line per character for approval before batch synthesis.

---

## Pre-Generation Service & Cost Disclosure Card

This card is **MANDATORY** before any generation call — visual or audio, concept art or final asset. Present it, wait for explicit approval, then execute.

### Card Format

```
## Generation Approval Required

### [Asset Category] — [Brief Description]
| Field | Value |
|-------|-------|
| **Service / Provider** | e.g., "image_selector → openrouter_image" |
| **Model Variant** | e.g., "FLUX.1 Pro" or "GPT Image 2" |
| **Quantity & Units** | e.g., "6 images (start + end frames for 3 scenes)" |
| **Est. Unit Cost** | e.g., "$0.04 per image" |
| **Est. Total Cost** | e.g., "$0.24" |
| **Budget Balance** | e.g., "$4.76 remaining of $5.00 budget" |
| **Free/Cheaper Alternative** | e.g., "FLUX.1 Schnell (free, lower quality)" |

### Proceed?
- **Yes** → I'll generate using the service above
- **Use alternative** → I'll use the cheaper option
- **Skip** → Proceed without this asset
- **Cancel** → Stop and reconsider
```

### Rules

1. **Batch where possible**: Group related generation calls into a single card (e.g., all keyframes for scenes 1–6 in one card, not 12 individual cards).
2. **Show at least one alternative** when a cheaper or free option exists.
3. **Log the approval** as a `decision_log` entry with `category: "service_and_cost_approval"` and `subject` describing what was approved (e.g., "Keyframe generation — 6 scenes").
4. **If budget is exceeded**: Warn explicitly. Do not proceed without the user acknowledging the overage.
5. **If no cost data is available**: State "Cost unknown — provider does not report pricing" and ask for explicit go-ahead.

---

## Edge-Case Protocols

### 1. Selective Scene Cherry-Picking / Re-Rolls

When the user approves some keyframes but rejects others:
- Track approval status per scene (`approved` / `rejected` / `pending`).
- Only regenerate rejected scenes. Approved scenes are frozen.
- If a rejected start frame had a dependent end frame, regenerate both.
- Present only the regenerated frames for the next review cycle.

### 2. Scene Splitting or Merging After Storyboard Review

If the user wants to split one scene into two or merge adjacent scenes:
- Update the scene plan with new IDs and timing.
- Generate new keyframes for the new/modified scenes only.
- Re-validate timing continuity (no gaps, no overlaps).
- Present the updated storyboard section for re-approval.

### 3. Verbatim Text / UI Card Protection

Scenes containing exact text that must render correctly (business names, URLs, phone numbers, CTAs, legal text, statistics, prices):
- MUST use `type: "text_card"` so Remotion/HyperFrames renders the text.
- NEVER use `type: "generated"` for text-critical scenes — AI image models hallucinate text.
- Set `keyframe_strategy: "procedural"` — no AI-generated keyframe needed.
- The scene description should specify the exact text to render.

### 4. Character Costume/State Changes Across Scenes

When a character changes appearance across the video (costume change, aging, injury, transformation):
- Generate a **per-state anchor image** for each distinct appearance.
- Tag each scene with the character's state: `source_reference_ids: ["detective_lin_casual"]` vs `["detective_lin_uniform"]`.
- Present all state variants together in the concept kit for approval.
- Do NOT use a single reference for a character who changes appearance — it will force visual consistency where the story requires change.

### 5. Multi-Character Identity Bleeding Prevention

When multiple characters appear in the same scene:
- Use **explicit spatial separation** in the prompt ("Character A on the left, Character B on the right").
- Provide each character's reference image individually bound to their role.
- If the generation model supports named character slots (e.g., `[identity_lock]`), use them.
- After generation, visually verify that each character matches their reference. Flag any identity bleeding to the user.

### 6. Platform Safe-Zone Framing (9:16 Vertical)

For TikTok, Instagram Reels, YouTube Shorts, and other vertical platforms:
- The top ~15% and bottom ~20% of the frame are obscured by platform UI (username, captions, buttons).
- Important visual content must be composed within the central safe zone.
- Include this constraint in keyframe generation prompts: "Subject centered vertically, leaving top 15% and bottom 20% clear."
- Flag any scene where critical text or character faces would fall in the dead zone.

### 7. Technical Jargon Pronunciation Mapping

See Part 2, Step 6. Build the pronunciation table before full TTS synthesis. If the script is in a language with ambiguous readings (e.g., Japanese kanji, Chinese characters), present all ambiguous terms.

### 8. Audio Duration vs. Visual Timing Drift Reconciliation

See Part 2, Step 6. This is checked after TTS generation and before the assets gate. Options:
- Extend visual timing (add holds, extend closing scene).
- Adjust narration speed (within 1.0x–1.1x only).
- Tighten the script and regenerate (most expensive but best quality).

Present the drift amount and options to the user. Do not silently adjust timing.

### 9. Multi-Speaker Dialogue Voice Allocation

See Part 2, Step 6. Each speaking character gets a distinct voice. Present voice options as a table, generate one sample line per character, and get approval before batch synthesis.

### 10. Provider API Outages or Quota Depletion Mid-Run

If a provider fails mid-generation (API error, rate limit, quota exhausted):
- **STOP immediately.** Do not silently switch to a backup provider.
- Present the failure to the user:
  - What was attempted.
  - What failed (error code, quota status).
  - What has already been generated successfully.
  - Options: (A) Retry the same provider, (B) Switch to a named alternative (with cost disclosure), (C) Wait and retry later, (D) Proceed with partial results.
- This follows the existing "Escalate Blockers Explicitly" protocol in `AGENT_GUIDE.md`.

### 11. AI Safety Filter False Positives

If a generation call is rejected by the provider's safety filter:
- Present the rejection to the user with the prompt that triggered it.
- Diagnose the likely trigger word or concept.
- Propose a sanitized prompt that preserves creative intent while avoiding the filter.
- Get user approval on the sanitized prompt before retrying.
- If repeated rejections occur, suggest switching to a more permissive provider (with cost disclosure) or rewriting the scene.

---

## Key Principles

1. **Never generate silently.** Every generation call — concept art, keyframes, narration, music, SFX, video — requires user awareness and approval via the Cost Disclosure Card.

2. **Always check user assets first.** The user may have professional-quality assets that are better than anything AI can generate. Ask before offering to generate.

3. **Visual before audio.** Part 1 (visual references and keyframes) must complete before Part 2 (audio). The visual storyboard locks the timing, which the audio must match.

4. **Selective, not all-or-nothing.** The user can approve some items and reject others. Track per-item status. Never regenerate approved items.

5. **Cost transparency always.** Even for free providers, present the card to confirm the service choice. The user may prefer a different free provider.

6. **One protocol, many pipelines.** This meta skill is shared across all production pipelines. Individual scene-directors and asset-directors reference it, but the protocol lives here. If the protocol changes, it changes everywhere.
