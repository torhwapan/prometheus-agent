---
name: prometheus-v5-dialog
description: Map Prometheus natural-language diagnosis requests into stable query semantics for v5 ad hoc diagnosis. Use when the user asks questions such as "帮我看下某台 redis 有没有异常", "最近 24 小时 rabbitmq 哪些队列消费能力不足", or "查询内存使用率超过 70% 的服务器", and the platform needs structured intent rather than free-form PromQL generation.
---

# Prometheus V5 Dialog

Use this skill to help the model classify common natural-language diagnosis requests into a small set of stable semantic categories. The downstream Python execution layer owns query execution, filtering, and final PromQL selection.

## Core Rule

Do not generate PromQL directly.

The model's job is only to extract:

- Prometheus target address
- job family
- intent type
- semantic hint
- optional instance
- optional threshold / comparison
- optional time range
- optional top N

Then hand the structured result to the platform's downstream Python execution tool.

## Intent Types

### 1. `inspection`

Use for questions asking whether a target is healthy or abnormal.

Examples:

- 帮我看下 10.22.23.24 上的 redis 有没有异常
- 帮我巡检一下这台机器上的 JVM
- 看看这个 redis 最近是否有问题

Typical semantic hints:

- `redis-health`
- `jvm-memory-risk`

### 2. `metric_filter`

Use for questions asking which objects satisfy a condition.

Examples:

- 最近 24 小时 rabbitmq 哪些队列消费能力不足
- 查询内存使用率超过 70% 的服务器
- 哪些机器 CPU 使用率大于 80%

Typical semantic hints:

- `rabbitmq-consumer-capacity`
- `node-memory-usage`

### 3. `metric_topn`

Use for questions asking for ranking or the highest / lowest objects.

Examples:

- CPU 最高的 10 台服务器
- 最近内存最高的主机有哪些

Typical semantic hints:

- `node-cpu-top`

## Job Mapping

- Redis -> `redis`
- RabbitMQ / MQ -> `rabbitmq`
- JVM / Java / Spring -> `jvm`
- 服务器 / 主机 / Linux / node-exporter -> `node`

If the user does not explicitly mention a job, infer from the metric theme if possible. If still unclear, leave it empty and let Python reject unsupported requests.

## Semantic Hints

Use only these fixed semantic hints unless the user adds a brand-new supported scenario later:

- `redis-health`
- `rabbitmq-consumer-capacity`
- `node-memory-usage`
- `node-cpu-top`
- `jvm-memory-risk`

## Address Extraction

- `http://...` or `https://...`: keep as-is
- `IP:port`: convert to `http://IP:port`
- bare IP: convert to `http://IP:9090`
- do not put the Prometheus server address into `instance`

## Condition Extraction

Comparison mapping:

- 超过 / 大于 / 高于 -> `>`
- 大于等于 -> `>=`
- 小于 / 低于 / 不足 -> `<`
- 小于等于 -> `<=`

Extract threshold values as plain numbers.

Examples:

- 超过 70% -> `threshold=70`
- 低于 40 -> `threshold=40`

## Time Range Defaults

- If the user says `最近 24 小时`, use `range_hours=24`
- If the user says `最近 12 小时`, use `range_hours=12`
- If the user says nothing, keep the default from the prompt or Python service

## Output Discipline

- Return structured intent only
- Do not invent unsupported metric names
- Do not output explanations
- Do not override deterministic Python logic
