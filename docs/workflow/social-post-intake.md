# Social Post Intake (X/LinkedIn/Threads)

Fast extraction workflow for social links used as research inputs.

## Goal

Get reliable content quickly, then move into `research-evaluator` scoring. Never proceed with missing or partial evidence without labeling it.

## Extraction Cascade

1. Open the original social URL in browser automation and capture an accessibility snapshot.
2. If login wall appears, check for visible post/article content in the same page snapshot before falling back.
3. For X, prefer the post's `Article`/focus link if present (`/handle/article/<id>`), which often exposes the full text.
4. Extract and open outbound source links from the post (blog/docs/benchmarks), then treat those as primary evidence.
5. If content is still blocked, use a mirror/fallback renderer (for X threads) and clearly mark evidence quality.

## Evidence Quality Labels

| Label | Meaning | Allowed next step |
|------|---------|-------------------|
| `full` | Full post/article text captured | Score + verdict allowed |
| `partial` | Only partial text/metadata captured | Score only if primary links provide full evidence |
| `title-only` | Only title/author/date visible | No scoring; report blocker and request alternative source |

## Required Metadata Capture

- Author handle/name
- Post date/time (absolute date)
- Original URL
- Visible engagement snapshot (optional but useful context)
- Whether extraction was `full`, `partial`, or `title-only`

## Notes For Efficiency

- Do not spend time perfecting social extraction if primary linked source is accessible.
- Treat social post as index pointer when it links to richer primary material.
- Store one context trace when fallback path was required, so future sessions reuse the working extraction route.

