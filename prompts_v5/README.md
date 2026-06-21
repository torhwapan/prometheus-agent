# Prometheus Agent V5 Assets

V5 is a prompt-and-skill package for natural-language Prometheus diagnosis.

It is intentionally not a standalone Python service.

## Files

- `intent_extraction.md`
  - Extract user questions into structured JSON intent.
- `result_explanation.md`
  - Optionally turn deterministic tool output into a short Chinese summary.
- `skills/prometheus-v5-dialog/SKILL.md`
  - Constrain the model's behavior, semantic mapping, and extraction rules.

## Recommended Usage

```text
user question
  -> intent_extraction.md + prometheus-v5-dialog skill
  -> structured intent JSON
  -> existing Python execution tool
  -> optional result_explanation.md
```
