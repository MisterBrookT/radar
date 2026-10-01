# Weekly briefing playbook

Radar is the reusable engine; Generative UI is its first topic preset (`topics/genui.json`), not the project boundary. `radar/briefing_policy.py` defines the rhythm, `radar/engine.py` runs autonomous research/narration/visual-review workers and guarded rendering/delivery, and `radar/minimal_video.py` is the deterministic visual engine. Source queries, repositories and relevance scope live in data presets.

Full project run: `python -m radar run --topic genui --week-ending YYYY-MM-DD --run-id UNIQUE-ID`. The project does the research and production; the supervising assistant launches and verifies it, not handwrites the digest.

## The approved rhythm

**Title → whole-picture core idea → only necessary detail → evidence, boundaries and takeaway.**

For the episode, introduce the week’s few main lines. For each work, name it and show its overall idea before an example or implementation detail. A one-work episode can combine these introductions. An overview is information, not a disposable welcome card.

Every detail must pass: **would removing it prevent understanding the core idea?** If not, remove it. Prefer one illuminating example to a feature tour. No settings walkthrough, module roll-call, decorative metadata or duplicated bullets. An important mechanism can stay; irrelevant implementation detail cannot.

Duration follows the useful material. There is no 59-second, five-minute or ten-minute target, no minimum word count, and no silence padding. A weekly episode may be ten or twenty minutes; a quiet week may be much shorter or have no video.

The accepted visual/rhythm reference is `runs/overview-first/video.mp4`: original whole-workflow image first, concise visual guidance, one necessary example, interpreted preference data and boundaries. Its VisCanvas topic is **not** a gold-standard GenUI selection example.

## 1. Define the week

Use seven inclusive UTC calendar dates, recorded in `briefing.json` and `collection-status.json`. For example, an end date of 2026-10-01 means September25–October1; the next endpoint October8 means October2–8. These date intervals do not overlap. Prefer a completed period when reviewing once a week; the default endpoint is today’s UTC date and can include an incomplete current day.

```bash
uv run python -m radar --topic genui --week-ending YYYY-MM-DD --through collect
```

Papers, X and HN use the same seven-day window. No silent 14-day paper/6-day HN backfill. Old papers with merely updated arXiv records are not new-publication candidates. Genuine new versions or releases can be added after checking their dated primary announcement; label the precise new development.

The collector is not exhaustive: arXiv query terms/categories, HN search limits and available X login constrain coverage. Optional `--max-pages` bounds arXiv and is recorded. Missing/empty X is not proof of no discussion. Check coverage and supplement official releases, project blogs and primary announcements when important work would otherwise be missed. Never compensate for weak coverage with off-topic filler.

## 2. Select important work, not popular filler

```bash
uv run python -m radar --topic genui --week-ending YYYY-MM-DD --from plan --through plan
```

Default upper bound: four coherent main lines, **not a four-story quota**. Group several sources about the same contribution. There is no platform quota or obligation to include every candidate. Importance comes from a substantive capability, useful research insight, credible evidence or consequential shipped change. Engagement is secondary. Weekly X collection has no minimum-like threshold.

Topic decisions are audited in `topic-decisions.json`:

| Role | Meaning | Use |
|---|---|---|
| direct | AI generates/adapts interface layout, components, interaction workflows, or directly renderable UI structures | Can anchor a GenUI main line |
| adjacent | Relevant AI/HCI/visualization work, but the interface itself is not the generated contribution | Optional explicitly labelled related context |
| exclude | Generic agent/model/MCP news, unsupported marketing, listicles, ordinary design shots | Do not include |

VisCanvas uses a fixed node interface for LLM-assisted visualization authoring. Generating a chart inside that fixed workspace does not by itself make the paper a core Generative UI work. A2UI/MCP-UI/AG-UI names likewise do not suffice without an actual supported interface-generation/rendering contribution.

`plan.json` records the week’s overview, selected main lines, importance reasons and things to verify. `selected.json` has stable source indices and explicit topic roles. A plan with no core headlines stops here; it is not a reason to manufacture a video. With incomplete source coverage, say only that no eligible headlines were found in the collected sources, not that nothing important happened.

## 3. Primary-source and figure review

The project's research worker performs this stage autonomously; a model’s abstract-based plan is **not** a finished, verified script. Full-source artifacts and a separately checked final video remain mandatory.

- Read the full original papers, official release notes or documentation for selected claims. Preserve them under the run’s `research/` directory.
- Extract/download original figures. Keep source URLs, figure numbers, dates/versions and hashes. Use relevant crops; do not regenerate the diagram simply to match a house style.
- Record architecture and experiment evidence. Distinguish measured outcomes, subjective preference, illustrative interactions and our interpretation. A nonsignificant difference is not equivalence.
- Label old/background and adjacent material. Do not let it take over a core GenUI main line.
- Sonnet drafts narration and aligned translations; Opus can plan difficult visual focus. The deterministic renderer executes no model-authored HTML or code.

Write `evidence.json`, for example:

```json
{"sources": [{"source": 0, "primary_url": "https://official-source.example/",
  "full_source": "research/source-0.html",
  "reviewed_claims": ["Claim and exact section/table/figure supporting it"],
  "limitations": ["What the evidence does not establish"]}]}
```

These placeholders illustrate the schema, not an actual news item. The CLI requires reviewed primary-source artifacts for every core source referenced by the final script.

## 4. Write only the necessary script

Use the existing minimal renderer schema, plus:

- `briefing: {cadence: "weekly", policy_version: 1}`
- `language: "en"`, `caption_languages: ["en", "zh-CN"]`
- `stories: [{name, sources: [selected-source indices]}]`
- Scene `story`: story index, or null for the episode overview.
- Scene `role`: overview, example, mechanism, evidence, boundary, takeaway or related.
- Scene `purpose`: what understanding would be lost if this scene were removed.
- Each work’s first scene is its overview. Each work needs evidence and a stated boundary; an evidence scene may set `contains_boundary: true` rather than adding a redundant limitations slide.
- Each event has `say`, identical `subtitle`, and complete aligned `segments: [{en, zh}]`. Joined English must exactly equal the speech.
- Original PNG figures stay inside `assets/`; source-pixel crops focus the relevant region. For new count plots, declare the denominator explicitly or supply verified `display_label` values (e.g. percentages). Never assume every study has twenty participants.

English appears above concise Chinese. Split at complete meanings, not at an arbitrary character width. Check the longest unit for orphaned words/characters and clipping. Do not use a short empty overview just to satisfy the schema.

## 5. Render and inspect

Heavy work runs in an isolated DGX snapshot; use allowlisted rsync dry runs and never overwrite an active job’s code. Keep provenance, command, logs and real exit status. Local Piper English is preferred; set its existing interpreter/model paths explicitly. No fixed-duration normalization is needed.

```bash
uv run python -m radar --topic genui --week-ending YYYY-MM-DD --from video --through video
```

This route validates the policy and source review, uses the minimal renderer, then fully decodes the final file and records its script/video hashes and selected-source/evidence/figure input hashes in `verification.json`. Changing reviewed inputs invalidates delivery readiness.

Inspect the **actual encoded video**: episode title/whole-picture opening, each work’s overview before detail, key source crops, data meaning, semantic transitions and the longest bilingual captions. Speech duration is the animation/caption clock. Audio and video should align to within frame/sample rounding. A quiet week must not acquire padding to match an arbitrary duration.

Record `video-review.json` against the final video hash:

```json
{"video_sha256": "actual SHA256",
 "opening_overview_checked": true, "captions_checked": true,
 "source_figures_checked": true, "claim_boundaries_checked": true}
```

The flags mean these checks were actually performed. Do not fill them speculatively.

## 6. Deliver once

```bash
uv run python -m radar --topic genui --week-ending YYYY-MM-DD --from deliver --through deliver
```

Delivery checks that decode verification and visual review match the current script/video. Weekly caption branding includes the date interval; adjacent sources are labelled related context. Existing standalone Weixin ledger/marker safety remains authoritative. API acceptance is not independently verified phone playback. Never replay an unknown or partial submission.

The bot needs a recent owner-message context; weekly unattended push can be blocked by that upstream reply window. A stale context is a delivery constraint, not permission to bypass it or restore endless twenty-minute retries.

## Operational status

- Bare entry point performs weekly collection/planning; `radar run` owns the full autonomous project job.
- Rendering/delivery require reviewed source artifacts, full decode, input hashes and independent actual-frame review. Source review is performed by a project worker, not bypassed.
- DGX daily and twenty-minute retry timers were disabled after brook requested weekly cadence; zero matching timers remain scheduled.
- First autonomous DGX case completed: `weekly-20261001T105106Z`, AUV-Bench + native Angular A2UI rendering, 157.26s. Research/visual/review workers exited zero; full decode and final input/artifact checks passed; caption+video API accepted once. Local proof: `runs/radar-first-weekly-20261001/e2e-proof.json`.
- This is a verified one-off project job, not an enabled recurring weekly production timer. Phone playback is not independently verified.
- Hermes stays retired. Do not use old broad deployment instructions or activate the old daily units. Migrate a dedicated, immutable weekly installation only after testing the full new path and recent-context delivery behavior.
