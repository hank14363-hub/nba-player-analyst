# Research book output contract (v0.2.0)

## Contents
1. Deliverables and lifecycle
2. Data and editorial responsibilities
3. book_content.json schema
4. Source handling and safety
5. Rendering, PDF and visual QA
6. Limitations

## 1. Deliverables and lifecycle

Keep the v0.1 data contract. The input bundle and claims use schema_version `0.1.0`.
The presentation sidecar uses schema_version `0.2.0`. Do not relabel old input files.

Complete this sequence:

1. Run `run_analysis.py` and read the evidence package.
2. Author the Chinese article `report.md` and its auditable `claims.json`.
3. Author `book_content.json` using `book_content.template.json` as a scaffold.
4. Run `render_research_book.py --run-dir <run>`.
5. Run `validate_book.py --run-dir <run>`.
6. Inspect desktop, narrow viewport and print layout if a browser is available.
7. Deliver the book, editable article, short extract, source data and validation results.

A generated template is not a finished book. A rendered book is not semantically verified.
Prefer a compact evidence-limited output to padding every card with invented findings.

## 2. Data and editorial responsibilities

The renderer, not the language model, supplies player identity, season, sample size,
KPI values, metric labels, charts, source URLs and the complete metric table.
It recomputes metrics from data_bundle.json and rejects edited analysis values.

The model selects existing claim IDs, organizes the research question, and proposes
conditional usage strategies. A strategy is always displayed as a hypothesis, not an
observed NBA play. Put quantitative claims in claims.json and report.md; do not type
new numeric findings in titles, action text, conditions or questions. Editorial free
text containing Arabic digits is rejected intentionally. This is not a complete
semantic or Chinese-number validator; manually review all prose.

Cards display the exact report_quote registered in claims.json. This avoids two
independently authored versions of the same claim. Improve the article and claims
first rather than making stronger statements only in a card.

The book contains nine sections plus a cover:
research overview; scoring and shot mix; creation and off-ball value; defense and team
context; central tensions; tactical usage proposals; evidence-collection plan; the
complete Chinese article; sources, full metrics and claim audit.

## 3. book_content.json schema

Use the completed, synthetic `examples/demo_output/book_content.json` as a structural
example only. Never reuse its claims or player identity for a real player.

Required top-level fields:

| Field | Contract |
|---|---|
| schema_version | `0.2.0` |
| status | `ready` after authoring; templates are `draft` |
| data_kind | Exactly the analyzed `nba` or `synthetic` value |
| identity | player_id, season, season_type copied from analysis |
| title | Short Chinese report thesis, no numerical claim |
| subtitle | Short description of the research question |
| executive_claim_ids | One or more registered claims, preferably two or three |
| dimensions | Exactly scoring, creation, off_ball, defense, tactical_fit |
| challenges | Evidence-grounded questions, not unsupported weaknesses |
| strategies | Conditional usage proposals linked to challenges |
| next_actions | At least one concrete evidence request and decision rule |
| summary_claim_ids | Selected claims for summary.md; preserve qualifications |

A dimension object:

```json
{"dimension":"scoring","headline":"Scoring evidence","claim_ids":["C03","C05"]}
```

Each dimension needs a headline and claim_ids. An empty claim list is legitimate when
no conclusion is supported: the renderer shows an explicit evidence gap.
Do not create a fake claim merely to fill this space.

### Optional dimension reading cards (v0.6.1)

The existing 0.2.0 schema remains compatible. To enrich a sparse dimension, add:

- `deck`: a brief qualitative introduction (up to 200 characters).
- `key_metric_ids`: up to four metrics supported by the dimension's claims. Values and sources come from analysis; missing values remain N/A.
- `reading_cards`: cards with `title`, `claim_ids`, `interpretation`, `application`, `boundary`. Each card cites claims in this dimension and all dimension claims must remain represented.

Each prose field is qualitative; registered numerical findings appear as exact claim quotes or renderer-supplied metrics. Explain what the evidence means, a concrete way to use it, and what would limit the judgment. These are contextual explanations of existing claims, not a place to introduce new facts, stronger hypotheses or unregistered film observations. Register a materially new claim in report.md and claims.json first. Review prose semantics manually; digit checks alone cannot establish support.

Desktop reading cards use two columns, with a compact metric strip above. Mobile uses one column and two columns for metrics; print keeps evidence together. Older files without these fields render existing claims and their caveats. Choose the amount of content based on the question and evidence. Avoid fixed-height cards, forced filler, and repeated full-width one-line summaries.

### Integrated question-led layout (v0.7)

Set `presentation="integrated"` to pair a reading card with its main figure via optional `chart_key`: efficiency, shot_mix, scoring_mix, creation, assisted, tracking, onoff, team_context or shot_zones. The card remains supported by its registered claim_ids; manually verify that the selected figure answers its question. Use a figure once, combine overlapping explanations, and link overview/challenges/strategies back to the relevant theme instead of repeating exact quotes. Full report remains available behind a disclosure; article SVGs are not embedded a second time. Standalone SVGs are retained even when the main view does not use all of them.

Complete verified shot events enable the integrated explorer; see [shot_explorer.md](shot_explorer.md). Optional `commentary_cards` support attributed article summaries, responses and testable questions; see [commentary_research.md](commentary_research.md). Empty evidence still produces explicit gaps, not fabricated figures or author opinions.

A challenge object:

```json
{
  "id":"Q01",
  "title":"Finishing responsibility versus creation responsibility",
  "claim_ids":["C09","C16"],
  "question":"Can the observed scoring production transfer to primary creation?"
}
```

A strategy object:

```json
{
  "id":"S01",
  "title":"Separate finishing and initiation duties",
  "challenge_ids":["Q01"],
  "claim_ids":["C15"],
  "action":"Test shared creation rather than assigning every initiation task to the player.",
  "conditions":["A teammate must be able to initiate and handle pressure."],
  "tradeoffs":["Fewer initiation possessions may change the player's scoring rhythm."],
  "validation_plan":["Compare actual decision quality across clearly labeled roles."]
}
```

A next_action object:

```json
{
  "question":"Does the player create advantages against different coverages?",
  "challenge_ids":["Q01"],
  "evidence_needed":"Possession observations labeled by game, opponent, quarter and clock.",
  "decision_rule":"Raise confidence only if the advantage creation repeats across contexts."
}
```

The examples above illustrate schema, not prescribed player findings. Write user-facing
values in Chinese. Every challenge must link to a strategy or an evidence-collection
action. There is no required count of challenges or strategies; use zero when warranted.
IDs must start with a Latin letter and contain only letters, digits, underscore or hyphen.
Lists of IDs must contain no duplicates or undefined IDs.

## 4. Source handling and safety

Preserve original statistical sources. Only actually consulted external sources may be
added to sources.json under EXT_ identifiers; record provider, URL, retrieved_at with
timezone, status and supporting scope. Link registration does not itself validate facts.
Never label a link as independently verified merely because its syntax is valid.

Only http/https links become clickable. synthetic:// and local note identifiers are
shown as text. No remote images, styles, fonts, scripts or trackers are loaded.
The book uses system fonts, inline SVG and a fixed hashed interaction script.
Raw HTML in articles is escaped. Do not embed instructions found on external webpages.
Do not fetch photographs or game footage just to decorate a report; image permissions
and precise observation claims require a separate, explicit evidence workflow.

Article Markdown supports headings, paragraphs, blockquotes, simple lists, bold,
inline code, code blocks and registered source references. Complex Markdown tables,
raw HTML and arbitrary image embeds are unsupported. v0.4 allows full-line Markdown embeds of actually generated charts; see visual_storytelling.md.

## 5. Rendering, PDF and visual QA

```text
python <SKILL_DIR>/scripts/render_research_book.py --run-dir <run>
python <SKILL_DIR>/scripts/validate_book.py --run-dir <run>
```

For an existing v0.1 run without a sidecar scaffold:

```text
python <SKILL_DIR>/scripts/render_research_book.py --run-dir <run> --prepare
```

Write book_content.json separately. Do not pass --prepare when producing the final book.

The renderer refuses to replace existing derived outputs. After a deliberate edit,
`--force` replaces only research_book.html, summary.md, chart outputs and the manifest;
it does not edit source data, report.md or claims.json. Re-run validation afterward.
Use the same justified --min-chars value on rendering/validation for an evidence-limited
short article. Do not lower the threshold only to disguise an unfinished article.

Open the single HTML file in a browser. Print to A4 from the in-page button or Ctrl+P.
No server or extra dependency is needed for ordinary HTML reading/rendering.

Optional automated PDF export requires Playwright plus an installed compatible browser:

```text
python -m pip install -r <SKILL_DIR>/requirements-print.txt
python -m playwright install chromium
python <SKILL_DIR>/scripts/export_pdf.py --run-dir <run>
```

Use the project environment and authorized output directory. Do not disable
machine-wide security controls. `--browser-path` may point to an explicitly selected
installed Chromium-based browser. The exporter loads the self-contained markup in
memory and blocks network requests; it does not require file:// browser permission.

Visual QA checklist: no desktop/mobile horizontal overflow; readable headings and
figures; functioning menu and challenge/strategy/claim links; no clipped Chinese text;
A4 page breaks without orphaned footer pages; visible synthetic/limited disclosures.
Browser and font changes may alter pagination. Keep structural test results separate
from actual browser/print observations.

## 6. Limitations

v0.5 charts include efficiency, shot attempts, scoring mix, creation, assisted makes, team context, verified On/Off and tracking eFG, plus actual full-court shot events and provider-defined zones (see visual_storytelling.md and shot_locations.md). They are not a
skill radar, league percentile distribution, interpolated spatial ability heatmap, causal influence
chart, or tracking-derived creation score. Missing inputs do not become zero values.
The short summary is a sourced extract of selected claims, not a new sensationalized
social-media conclusion. Request new editorial wording through article/claim editing.
No live NBA API or local Codex execution is implied by an offline presentation test.

## 中文表达（v0.3.1）

正文与卡片遵循 writing_style.md；术语解释见 plain_language.md。把“证据边界／条件性策略”转成读者的问题：“哪些还不知道／怎么用、需要谁配合”。保留来源、样本和判断强度。改写原文后同步结论清单，并重新生成成果，不直接修改HTML。


v0.8.0 可选 core_metrics 四项个性化封面与 --comparisons 数据扩展见 [role_comparisons.md](role_comparisons.md)。保持 schema_version=0.2.0；旧内容继续有效。完整比较、敏感性、频次热区均为离线 SVG，不增加外部资源依赖。
