---
name: prometheus-v2-metric-query-catalog
description: Explain and select v2 Prometheus inspection metric definitions for node-exporter, JVM, Redis, and RabbitMQ jobs. Use when the platform needs to understand which configured metrics will be queried, how current and range PromQL differ, and how job/instance filters should be applied.
---

# Prometheus V2 Metric Query Catalog

The Python service owns the executable metric catalog. Use this skill to explain or choose from catalog concepts, not to replace the catalog.

## Job Families

- `node`: Linux host metrics from node-exporter.
- `jvm`: JVM runtime metrics from Micrometer or JMX exporter.
- `redis`: Redis metrics from redis_exporter.
- `rabbitmq`: RabbitMQ queue and broker metrics.

## Query Model

Each metric has:

- `current_promql`: short-window query for current state, normally 5 minutes.
- `range_promql`: range query expression for historical samples.
- `value_type`: `number` or `percent`.
- `analysis_methods`: deterministic Python methods such as threshold, burst, sustained growth, and time-to-limit.
- `unit`, `direction`, optional `warning`, `critical`, and optional `max_value`.

## Selection Rules

- If user specifies a job, query only that job family.
- If user does not specify a job, query all configured job families.
- If user specifies an instance, apply `instance` filtering to every metric query.
- Preserve labels that identify risk source: `job`, `instance`, `mountpoint`, `queue`, `vhost`, `area`.

## AI Role

AI can explain what metrics mean and why they are useful. AI must not override deterministic severity returned by Python.
