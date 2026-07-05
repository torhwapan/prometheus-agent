---
name: "prometheus-fixed-inspection-v7"
description: "Generate a fixed-format Prometheus inspection report by running a predefined inspection workflow against a Prometheus endpoint. Use when the task is fixed operational inspection rather than free-form PromQL exploration: the user provides a Prometheus URL, expects fixed metrics and fixed PromQL, wants deterministic rule-based analysis, and needs a single HTML report with stable structure. Also use when Codex should rely on optional LLM commentary without letting AI choose metrics, queries, or severities."
---

# Prometheus Fixed Inspection V7

Run the fixed inspection workflow instead of improvising.

Use the bundled script to generate the report. The skill includes its own bundled inspection engine under `scripts/`, so it should not depend on an external checkout of `prometheus_agent_v6`.

## Workflow

1. Confirm the user is asking for fixed Prometheus inspection, not free-form metric exploration.
2. Run `scripts/run_fixed_inspection.py` with the Prometheus URL and an output HTML path.
3. Pass `--instance` only when the user narrows inspection to one instance.
4. Pass repeated `--job` arguments only when the user wants to limit inspection to specific fixed jobs.
5. Leave AI enabled only when LLM settings are available or explicitly provided. AI is optional.
6. Return the generated HTML path and a short summary of the inspection result.

## Command Pattern

Default form:

```powershell
python prometheus-fixed-inspection-v7/scripts/run_fixed_inspection.py --prometheus-url <PROM_URL> --output report_v7.html
```

With instance filter:

```powershell
python prometheus-fixed-inspection-v7/scripts/run_fixed_inspection.py --prometheus-url <PROM_URL> --instance <INSTANCE> --output report_v7.html
```

With explicit jobs:

```powershell
python prometheus-fixed-inspection-v7/scripts/run_fixed_inspection.py --prometheus-url <PROM_URL> --job redis_exporter --job java_jmx --output report_v7.html
```

If the user provides direct LLM parameters, append:

```powershell
--llm-base-url <BASE_URL> --llm-api-key <API_KEY> --llm-model <MODEL>
```

If AI should be skipped, append:

```powershell
--disable-ai
```

## Guardrails

- Treat the bundled engine under `scripts/prometheus_agent_v6` as the execution engine.
- Keep the report contract fixed.
- Keep metrics and PromQL fixed.
- Keep rule severity deterministic.
- Use AI only for brief supplemental summary or comments.
- Do not replace this workflow with the generic `prometheus` skill unless the user explicitly asks for natural-language metric exploration.

## References

- Read [references/fixed-scope.md](references/fixed-scope.md) when you need the supported jobs, scope boundaries, or rationale for fixed inspection.
- Read [references/report-contract.md](references/report-contract.md) when you need the exact final output contract.

## Output

- Produce one HTML file and report its path.
- Summarize the final severity and key counts in the response.
- Mention if AI enrichment was skipped or failed.
