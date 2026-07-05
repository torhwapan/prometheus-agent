# Fixed Scope

This skill is for deterministic Prometheus inspection, not ad hoc natural-language querying.

## Supported Jobs

- `node_exporter`
- `java_jmx`
- `redis_exporter`
- `rabbitmq_exporter`

## Fixed Behavior

- Discover jobs from the target Prometheus instance.
- Match discovered jobs to the fixed inspection packs in `prometheus_agent_v6.catalog`.
- Run the predefined metric set and PromQL only.
- Apply deterministic rule analysis only.
- Generate one fixed-format HTML report.

## Read This File When

- The user asks which systems or jobs are supported.
- The user wants to change the inspection scope.
- You need to explain why the skill does not behave like a free-form PromQL assistant.

## Scope Boundaries

- Do not invent new metrics.
- Do not let AI decide what to query.
- Do not change the severity based on AI output.
- Use AI only for optional short comments and summary text.
