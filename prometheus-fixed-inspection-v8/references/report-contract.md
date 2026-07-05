# Report Contract

The final deliverable is one HTML file.

## Required Sections

1. Hero or header summary with:
   - generated time
   - overall severity
   - pack count
   - finding count
   - active target count
2. Inspection scope with:
   - Prometheus URL
   - instance filter
   - discovered normalized jobs
   - severity counts
3. Fixed inspection pack table
4. Findings table
5. Optional warnings block
6. Optional AI summary block

## Findings Table Columns

Include these columns in order:

| Column |
| --- |
| Severity |
| Pack |
| Job / Instance |
| Metric |
| Current value |
| Rule reason |
| AI comment |
| Labels |

## Template Usage

Use [../assets/report-template.html](../assets/report-template.html) as the default skeleton.

Replace these placeholders:

| Placeholder | Meaning |
| --- | --- |
| `{{GENERATED_AT}}` | ISO UTC generation time |
| `{{OVERALL_SEVERITY}}` | Final summary severity |
| `{{PACK_COUNT}}` | Number of selected packs |
| `{{FINDING_COUNT}}` | Number of findings |
| `{{ACTIVE_TARGET_COUNT}}` | Count from discovery |
| `{{PROMETHEUS_URL}}` | Inspected Prometheus URL |
| `{{INSTANCE_FILTER}}` | Instance filter or `not set` |
| `{{DISCOVERED_JOBS}}` | Comma-separated normalized jobs |
| `{{COUNTS_LINE}}` | `critical=..., warning=..., info=..., ok=..., unknown=...` |
| `{{PACK_ROWS}}` | HTML table rows for selected packs |
| `{{FINDING_ROWS}}` | HTML table rows for findings |
| `{{WARNINGS_BLOCK}}` | Optional warning panel HTML |
| `{{AI_SUMMARY_BLOCK}}` | Optional AI summary HTML |

## Stability Rules

- Keep the overall HTML layout stable across runs.
- Keep row ordering deterministic.
- Keep severity badges text-based and machine-readable.
- Escape user-controlled values before inserting them into HTML.
- If AI is skipped, leave the AI summary block empty and the AI comment cells blank.
