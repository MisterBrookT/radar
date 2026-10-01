# Minimal research explainer

Focus on one paper and its useful insight, not on completing a paper walkthrough. Start with the title and a whole-picture explanation, illustrated by the original workflow overview. Then include only details necessary to understand the core idea, followed by the necessary evidence and limitations. Minimal does not mean diving immediately into a feature or skipping orientation. Remove greetings, empty concept slides, settings walkthroughs and module-name recitals. Length follows the useful content, not a duration quota.

## Visual policy

- Prefer original paper figures, with source/version and figure citations.
- Show original architecture context, then focus only on the mechanism needed to explain the insight. Do not recite every panel or module.
- Crop and smoothly zoom into the part being explained. Do not redraw diagrams by default.
- Keep one heading, the original figure or one quantitative comparison, a quiet citation and a phrase subtitle. No branding, popularity metrics, badges, decorative progress or redundant bullet lists.
- Use verified source numbers for simple count comparisons. Label the study and preserve the distinction between reported preference, self-reported support and objective performance.
- Missing statistical significance is not proof of equivalence.

## Rendering

`radar/minimal_video.py` accepts a `script.json` with semantic events. Each event contains `say`, the matching `subtitle`, and a visual state. Original figure scenes refer to bounded PNG assets under the run's `assets/` directory and source-pixel crop rectangles. These are rendered as original images inside a clipped SVG viewport; they are not reconstructed figures.

For bilingual captions, supply explicit `segments: [{en, zh}]` on each event. These are complete semantic units, not character-width cuts. Joined English must equal `say`; Chinese is a reviewed, concise translation. English appears above Chinese, with both held for that unit's measured speech duration. Verify CJK fonts and the longest captions in the actual browser.

Each subtitle phrase is synthesized locally and measured. The resulting audio durations drive visual cues, deterministic easing, captions and the single `timing.json` manifest. Optional duration normalization uses one bounded speaking-rate adjustment for the entire video, then remeasures every audio clip; it does not guess scene times or pad the talk with silence.

```bash
python -m radar.minimal_video RUN_DIR --preview-scene s4 --preview-events 5
python -m radar.minimal_video RUN_DIR
# Optional only when genuinely needed, not a default length quota:
python -m radar.minimal_video RUN_DIR --target-seconds 300
```

Preview the hardest representative sequence before the full render. Verify figure crops, subtitle readability, source claims, boundary frames and full audio/video decode. Inspect the actual generated duration rather than assuming the word count yields five minutes.

## Case source

VisCanvas: A Node-Based Interface for Exploratory Visualization Authoring with LLMs:
https://arxiv.org/html/2607.21886v3

Original Figures 2, 3, 7, 8 and 10 are used as source illustrations. Preference counts are from Section 5.2.3: open-ended canvas preference 14/20; targeted preference canvas 8, chat 10, neutral 2. The latter is a reported preference, not a separately measured targeted-task performance trial.

The original five-minute case is under `runs/minimal-five-minute/`. The latest overview-first revision is under `runs/overview-first/`: title and a complete original workflow overview before one interaction example and the preference evidence. It omits implementation details and metric-specific demonstrations that are not needed to grasp the core. The earlier tightened revision is under `runs/concise-bilingual/`: direct original-figure opening, copy/modify and merge examples, explicit-context mechanism, only the preference counts needed to interpret the results, and bilingual semantic captions. It has no forced-duration adjustment. This experimental renderer does not automatically replace the scheduled briefing installation or its legacy stage-6 renderer.
