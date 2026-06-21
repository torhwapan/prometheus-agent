---
name: prometheus-agent
description: Prometheus ad hoc diagnosis skill for agent-platform use. Map Chinese natural-language Prometheus questions into a fixed set of semantic keys and stable HTTP tool calls instead of free-form PromQL generation.
---

# Prometheus Agent Skill

Use this skill when the user is asking common Prometheus diagnosis questions in natural language.

This skill does not execute queries by itself.

Its job is to help the model:

- understand Prometheus question patterns
- normalize addresses, jobs, thresholds, and time ranges
- choose one stable `semantic_key`
- choose one stable HTTP tool route

## Core Rule

Do not generate PromQL directly.

Always map the question into one of the fixed semantic scenarios below.

## Supported Semantic Keys

### 1. `redis-health`

Mode: `inspection`

Use for questions like:

- `帮我看下 10.22.23.24 上的 redis 有没有异常`
- `看下 redis 最近有没有问题`

Default job:

- `redis_exporter`

### 2. `jvm-memory-risk`

Mode: `inspection`

Use for questions like:

- `帮我看下这台机器上的 jvm 有没有风险`
- `检查一下 java 内存情况`

Default job:

- `java_jmx`

### 3. `rabbitmq-consumer-capacity`

Mode: `metric_filter`

Use for questions like:

- `最近 24 小时 rabbitmq 哪些队列消费能力不足`
- `哪些队列消费能力比较差`

Default job:

- `rabbitmq_exporter`

Default comparison:

- `<`

Default threshold:

- `70`

### 4. `node-memory-usage`

Mode: `metric_filter`

Use for questions like:

- `帮我查询下内存使用率超过了 70% 的服务器`
- `哪些机器内存比较高`

Default job:

- `node_exporter`

Default comparison:

- `>`

### 5. `node-cpu-top`

Mode: `metric_topn`

Use for questions like:

- `CPU 最高的 10 台服务器`
- `最近 CPU 最高的主机有哪些`

Default job:

- `node_exporter`

Default top_n:

- `10`

## Job Mapping Rules

- `redis` -> `redis_exporter`
- `redis exporter` -> `redis_exporter`
- `rabbitmq` -> `rabbitmq_exporter`
- `mq` -> `rabbitmq_exporter`
- `java` -> `java_jmx`
- `jvm` -> `java_jmx`
- `spring` -> `java_jmx`
- `server` -> `node_exporter`
- `host` -> `node_exporter`
- `linux` -> `node_exporter`
- `node` -> `node_exporter`

## Intent Type Rules

### `inspection`

Use when the user is asking:

- whether something is abnormal
- whether there is risk
- whether a target should be inspected

Typical words:

- `异常`
- `巡检`
- `有没有问题`
- `是否有风险`

### `metric_filter`

Use when the user is asking:

- which objects satisfy a condition
- which objects exceed or fall below a threshold

Typical words:

- `哪些`
- `超过`
- `大于`
- `低于`
- `不足`

### `metric_topn`

Use when the user is asking:

- ranking
- highest / lowest objects
- top N

Typical words:

- `最高`
- `前几`
- `top`
- `排名`

### `discovery`

Use when the user is asking:

- what jobs exist
- what metrics exist
- what targets exist
- what labels or series exist

## Address Extraction Rules

- If the user gives `http://...` or `https://...`, keep it.
- If the user gives `IP:port`, convert it to `http://IP:port`.
- If the user gives a bare IP, convert it to `http://IP:9090`.
- Do not put the Prometheus server address into business `instance`.

## Condition Extraction Rules

- `超过 / 大于 / 高于` -> `>`
- `大于等于` -> `>=`
- `低于 / 小于 / 不足` -> `<`
- `小于等于` -> `<=`

Extract thresholds as plain numbers:

- `70%` -> `70`
- `40` -> `40`

## Time Rules

- If the user says `最近 24 小时`, use `range_hours=24`
- If the user says `最近 12 小时`, use `range_hours=12`
- If the user says `最近 1 小时`, use `range_hours=1`
- If the user says nothing, let the prompt default apply

## HTTP Tool Routing

- `inspection` -> `POST /v5/query/inspection`
- `metric_filter` -> `POST /v5/query/filter`
- `metric_topn` -> `POST /v5/query/topn`
- `discovery` -> `POST /v5/query/discovery`

## Output Discipline

- Prefer one semantic key only.
- Prefer one tool call only for the first answer.
- Do not invent unsupported metrics.
- Do not produce free-form PromQL.
- If the question is outside the fixed semantic scenarios, say it is unsupported.
