# Fixed Scope

This skill is for deterministic Prometheus inspection, not for open-ended metric exploration.

## Supported Jobs

- `node_exporter`
- `java_jmx`
- `redis_exporter`
- `rabbitmq_exporter`

## Job Aliases

Normalize user language to the canonical jobs below before selecting packs:

| Alias | Canonical job |
| --- | --- |
| `node`, `node-exporter`, `node_exporer`, `linux`, `host`, `server` | `node_exporter` |
| `jvm`, `java`, `spring` | `java_jmx` |
| `redis` | `redis_exporter` |
| `mq`, `rabbitmq` | `rabbitmq_exporter` |

## Fixed Pack Defaults

| Job | Pack key | Pack title | Range hours | Step seconds | Current window |
| --- | --- | --- | ---: | ---: | --- |
| `node_exporter` | `node-fixed-inspection` | `Host Fixed Inspection` | 24 | 60 | `5m` |
| `java_jmx` | `jvm-fixed-inspection` | `JVM Fixed Inspection` | 24 | 60 | `5m` |
| `redis_exporter` | `redis-fixed-inspection` | `Redis Fixed Inspection` | 24 | 60 | `5m` |
| `rabbitmq_exporter` | `rabbitmq-fixed-inspection` | `RabbitMQ Fixed Inspection` | 24 | 60 | `5m` |

Use metric-level overrides from the job reference file when a metric defines a different window, range, or step.

## Discovery Rules

1. Read `/api/v1/label/job/values` to get raw jobs.
2. Read `/api/v1/targets` to get active targets and instances.
3. Normalize jobs using the alias table above.
4. If the user explicitly requests jobs, keep only supported requested jobs.
5. If the user does not request jobs, select packs in this order:
   - `node_exporter`
   - `java_jmx`
   - `redis_exporter`
   - `rabbitmq_exporter`
6. If requested jobs are unsupported, keep going and record a warning.
7. If no packs match, still produce a report that shows discovery results and warnings.

## Scope Boundaries

- Do not invent new metrics.
- Do not let AI decide what to query.
- Do not let AI change severity.
- Do not change pack ordering.
- Do not change the HTML report shape without an explicit user request.
- Keep the output to one report file by default.
