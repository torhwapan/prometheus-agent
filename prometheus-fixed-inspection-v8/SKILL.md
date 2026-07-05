---
name: prometheus-fixed-inspection
description: Generate a deterministic fixed-scope Prometheus inspection report without bundling a full Python inspection engine. Use when the user provides a Prometheus URL, expects fixed jobs, fixed metrics, fixed PromQL, rule-based severity, and one stable HTML report. Prefer direct Prometheus HTTP API calls in the style of the generic prometheus skill, and use Python only when the user explicitly asks for extra automation.
---

# Prometheus Fixed Inspection

## Overview

Use this skill to run a fixed Prometheus inspection workflow as explicit agent instructions instead of shipping a full embedded Python service.

The default execution style is:

- discover from Prometheus directly
- query only the fixed metric catalog
- apply deterministic rules from references
- render one HTML report from the bundled template

## Workflow

1. Confirm the request is fixed inspection, not ad hoc PromQL exploration.
2. Read [references/fixed-scope.md](references/fixed-scope.md), [references/http-workflow.md](references/http-workflow.md), [references/analysis-rules.md](references/analysis-rules.md), and [references/report-contract.md](references/report-contract.md).
3. Discover jobs and active targets from the Prometheus endpoint.
4. Select only the supported fixed packs that match discovered jobs or explicit user-selected jobs.
5. Read only the job reference files that match the selected packs.
6. Run each metric's instant query and range query through the Prometheus HTTP API.
7. Apply deterministic severity rules exactly as documented in the analysis rules reference.
8. Fill [assets/report-template.html](assets/report-template.html) and write one HTML report.
9. Return the report path plus a short summary of overall severity and counts.

## Execution Preferences

- Prefer direct HTTP calls in the same style as the generic `prometheus` skill.
- Prefer `curl` or `Invoke-RestMethod` over Python.
- Do not add a new Python inspection engine to this skill.
- Only write a small task-local helper if the user explicitly asks for automation beyond normal agent execution, or the report is so large that manual assembly becomes unreasonable.
- If a helper becomes necessary, keep it narrow: query batching, payload shaping, or HTML filling. Do not recreate `service.py`.

## Reference Map

- Read [references/fixed-scope.md](references/fixed-scope.md) for supported jobs, aliases, pack defaults, and scope boundaries.
- Read [references/http-workflow.md](references/http-workflow.md) for endpoint usage, parameter patterns, and instance-filter behavior.
- Read [references/analysis-rules.md](references/analysis-rules.md) for the deterministic classification algorithm.
- Read [references/report-contract.md](references/report-contract.md) for the required output shape and HTML placeholders.
- Read [references/node-exporter.md](references/node-exporter.md) only when host or node packs are selected.
- Read [references/java-jmx.md](references/java-jmx.md) only when JVM packs are selected.
- Read [references/redis-exporter.md](references/redis-exporter.md) only when Redis packs are selected.
- Read [references/rabbitmq-exporter.md](references/rabbitmq-exporter.md) only when RabbitMQ packs are selected.

## Guardrails

- Keep the metric set fixed.
- Keep PromQL fixed except for deterministic time and optional instance-filter substitution.
- Keep severity deterministic and rule-based.
- Treat missing data as `unknown`, not healthy.
- Use AI only for optional summary text or short comments after deterministic analysis.
- Do not replace this workflow with the generic `prometheus` skill unless the user explicitly asks for free-form exploration instead of the fixed report.

## Output

- Produce exactly one HTML file unless the user explicitly asks for extra artifacts.
- Include overview cards, scope metadata, pack table, findings table, optional warnings, and optional AI summary.
- Report the final severity and counts in the assistant response.
