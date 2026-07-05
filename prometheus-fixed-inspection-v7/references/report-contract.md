# Report Contract

The final deliverable is a single HTML file.

## Required Output

- Output exactly one HTML report unless the user explicitly requests additional artifacts.
- Prefer a concrete path such as `report_v7.html` inside the workspace.
- The HTML must come from the deterministic renderer in `prometheus_agent_v6.report`.

## Required Report Sections

- Header summary with generated time, overall severity, pack count, finding count, active target count
- Inspection scope with Prometheus URL, instance filter, discovered jobs, counts
- Fixed inspection pack table
- Findings table with severity, pack, job/instance, metric, current value, rule reason, AI comment, labels

## Stability Rules

- Keep the HTML structure fixed across runs.
- Keep the rule analysis deterministic across runs.
- Treat AI output as optional decoration, not as the source of truth.

## Read This File When

- The user asks what the report contains.
- The user asks to adjust the HTML contract.
- You need to verify the output remains a single fixed-format HTML report.
