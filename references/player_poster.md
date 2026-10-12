# Player verdict poster: v0.3

## Purpose and evidence order

Create a dense but readable, team-colored conclusion page in addition to the full research book. Treat the supplied basketball graphic as a reference for visual hierarchy, not as a statistical source. Do not copy its proprietary rating, ranks, EPM values, player likeness, logos, or percentile fields into another player's report.

Use this order: audited data and claims -> compact editorial conclusions -> deterministic SVG charts -> HTML -> optional PNG. Preserve the original full article and its limitations. Every chart gets an interpretation, denominator, source IDs, and a statement of what it cannot show.

## Workflow

1. Complete report.md and claims.json, then book_content.json, using existing contracts.
2. Run `render_player_poster.py --run-dir RUN --prepare` to create `poster_content.template.json`.
3. Author a separate `poster_content.json`. Preserve its identity and data_kind; use schema_version 0.3.0 and set status to ready only when finished.
4. Render both presentations with the same `--theme auto` or explicit team code.
5. Run validate_book.py and validate_poster.py. Review numbers, claim support, layout, and inferential language separately.
6. Optionally run export_poster.py for the long PNG and a cover preview. Do not claim PNG export or browser QA succeeded unless actually run.

## Editorial contract

Apply references/writing_style.md and references/plain_language.md. Use plain Chinese for chart titles and primary labels; keep English only as a secondary cue. Explain abbreviations briefly in each standalone poster. Do not turn missing evidence into a negative ability judgment. Keep denominators, source links and important caveats. Review language before regenerating all outputs.

- headline: up to 32 characters. Phrase as a useful, player-specific tension, not a rating.
- deck: up to 110 characters. State the actual scope without restating the headline.
- verdict, strength, fit, risk: objects with concise text (up to 120 characters) and nonempty claim_ids.
- roles.offense and roles.defense: text up to 28 characters, each with claim_ids. These are evidence-based use hypotheses or evidence limits, not a statistical classifier or external scouting label.
- chart_notes: exactly six entries: efficiency, shot_mix, scoring_mix, creation, assisted, team_context. Each has takeaway (up to 100 characters) and claim_ids. Explain what the pattern means in basketball and what remains unknown. The engine suppresses a chart's affirmative takeaway when that chart's required data is missing.
- No Arabic numeric claims in editorial text: the audited metric layer renders statistics. Do not evade this using Chinese numerals or spelling out unsupported quantities.
- portrait: null by default. Only add a local relative path, nonempty credit and rights_confirmed=true for a user-authorized image. Never fetch, invent or swap an athlete portrait just because the style reference includes one.

All referenced claims must exist in claims.json and be supported by the original report. Automatic checks cannot prove that the shortened conclusion logically follows; manually review every shortened sentence against the referenced claim and its caveats.

## Six supported chart modules

| Key | Graphic | Denominator / interpretation boundary |
|---|---|---|
| efficiency | Common zero-based TS bars, exact values and rTS callout | rTS is a percentage-point gap from the matched weighted baseline, not a score. TS can exceed 100% in tiny samples; extend the scale rather than clipping. |
| shot_mix | Two-/three-point attempt mix and separate 3P% | Attempt shares exclude free throws. 3P% uses three-point attempts. Not a shot map or point distribution. |
| scoring_mix | Two-point, three-point and free-throw share donut | 2*(FGM-FG3M), 3*FG3M and FTM divided by PTS. Validate the points identity; do not call this play-type breakdown. |
| creation | Per-75 PTS/AST/TOV bars on a shared numeric scale | Different event counts, not interchangeable measures of quality. Do not sum them into a rating or infer passing skill from AST alone. |
| assisted | Assisted/unassisted shares of made field goals and made threes | Made shots only. Unassisted does not equal isolation; assisted makes are not all catch-and-shoot attempts. |
| team_context | On-court ORTG/DRTG beside target-team ORTG/DRTG | Descriptive contexts, different samples. Never subtract them and call the result on/off, causal impact or individual defense. |

Derived display metrics live in poster_metrics.json, not in analysis.json. They are recomputed from the validated sample and have source IDs and formulae. Missing inputs yield a missing chart; zero is not used as a substitute. A full synthetic sample currently renders all six, but a real report may have fewer.

## Team themes

Thirty team-inspired editorial presets plus NEUTRAL are bundled in team_themes.py. They are curated high-contrast design choices, not official brand specifications, historic uniforms, or licensing evidence. `auto` selects the player sample's team ID when available, otherwise the reported team label; unresolved or aggregate labels use NEUTRAL. A hypothetical destination does not silently change the player's theme.

Use explicit overrides only as styling: `--theme LAL`, `--theme MIN`, `--theme BOS`, etc. The theme never edits player identity, target team, season or stats. Historical and traded-player labels require special care: a reported team tag does not prove the whole season was played there. A synthetic player's real-team palette is prominently disclosed as an appearance demo, not team membership.

`--theme-config PATH` accepts exactly `{ "primary": "#55209A", "accent": "#FFD447" }`. Reject CSS expressions and low-contrast accent colors. Foreground colors are selected for readable contrast. Preserve direct labels in addition to colors; the colors do not encode "good" or "bad".

## Portrait safety

The optional portrait is a PNG, JPEG or WebP inside the run directory; maximum 5 MB. Reject path traversal, remote URLs, SVG and unconfirmed rights. Record credit. The HTML embeds the image to remain offline. Rights confirmation is the user's attestation, not a license audit. The example intentionally has no real athlete photograph or team logo. Text and a clearly labeled rTS callout fill the cover instead.

## Exports and checks

HTML and SVG generation need only the standard library. PNG export uses optional Playwright/Chromium, installed separately and with user permission. No external resources are requested by the generated page. Source URLs are outbound citation links, not page dependencies.

The default screenshot target is the complete poster, not the expandable evidence appendix. The cover preview includes the sample disclaimer, player identity, core metrics, conclusion and role labels. The HTML preserves a clickable evidence drawer with the exact registered quotes and the metric/source tables. Each standalone SVG includes season, source IDs and synthetic disclosure when applicable.

Inspect desktop and mobile widths. Do not crop away the synthetic disclosure or sample context for social publication. The default wide poster is 1080 CSS pixels; the HTML reorganizes into a one-column view on phones. Browser fonts can change wrapping. Font files are not bundled.

## Explicitly unsupported

No fabricated overall grade, league/position/team ranks, same-role percentile radar, EPM chart, salary valuation, play-type efficiency wheel or shot-coordinate map. Adding one later requires an identified accessible source, matching sample, denominator, method and tests. Do not copy such values from an example image as substitute data.


v0.8.0 封面与研究册共用 core_metrics 选择；原六图契约不变。缺失块依据 comparison_context 与 shot_context 生成，不再默认断言缺少比较/坐标。新统计结论需登记正文与 claims，正文变化后重新导出长图。
