# Prometheus Agent V5

## 1. Purpose

This directory contains a complete V5 asset bundle for ad hoc Prometheus diagnosis on your agent platform:

- one main agent prompt
- one Prometheus domain skill
- one lightweight Python HTTP tool service

V5 is focused on natural-language temporary diagnosis, for example:

- `帮我看下 10.22.23.24 上的 redis 有没有异常`
- `最近 24 小时 rabbitmq 哪些队列消费能力不足`
- `帮我查询下内存使用率超过了 70% 的服务器`

It is intentionally separate from V4.

## 2. Layout

```text
prometheus-agent-v5/
  README.md
  agent_prompt.md
  skills/
    prometheus-agent/
      SKILL.md
  http_tools/
    __init__.py
    semantics.py
    discovery.py
    service.py
    server.py
```

## 3. Recommended Platform Design

Use one agent first. Do not start with parent-child agents.

Recommended composition:

1. Main prompt: [agent_prompt.md](D:/Professional/myCode/prometheus-agent/prometheus-agent-v5/agent_prompt.md)
2. Skill: [SKILL.md](D:/Professional/myCode/prometheus-agent/prometheus-agent-v5/skills/prometheus-agent/SKILL.md)
3. HTTP tools: this directory's `http_tools`

Role split:

- Prompt controls workflow.
- Skill provides Prometheus semantics and mapping rules.
- HTTP tools execute queries and deterministic analysis.

## 4. HTTP Tool Endpoints

The service exposes these routes:

- `GET /health`
- `GET /v5/catalog`
- `GET /v5/semantics`
- `POST /v5/query/inspection`
- `POST /v5/query/filter`
- `POST /v5/query/topn`
- `POST /v5/query/discovery`

### 4.1 Inspection

`POST /v5/query/inspection`

Typical payload:

```json
{
  "prometheus_url": "http://10.22.23.24:9090",
  "semantic_key": "redis-health",
  "job": "redis",
  "instance": null,
  "range_hours": 24,
  "step_seconds": 60,
  "current_window": "5m"
}
```

### 4.2 Filter

`POST /v5/query/filter`

Typical payload:

```json
{
  "prometheus_url": "http://10.22.23.24:9090",
  "semantic_key": "node-memory-usage",
  "job": "node",
  "comparison": ">",
  "threshold": 70,
  "range_hours": 1
}
```

### 4.3 TopN

`POST /v5/query/topn`

Typical payload:

```json
{
  "prometheus_url": "http://10.22.23.24:9090",
  "semantic_key": "node-cpu-top",
  "job": "node",
  "top_n": 10,
  "range_hours": 1
}
```

### 4.4 Discovery

`POST /v5/query/discovery`

Supported `action` values:

- `job_values`
- `metric_names`
- `label_values`
- `series`
- `targets`
- `alerts`
- `metadata`

Example:

```json
{
  "prometheus_url": "http://10.22.23.24:9090",
  "action": "series",
  "match": "{job=\"redis_exporter\"}"
}
```

## 5. Run the HTTP Tool Service

From repo root:

```powershell
python .\prometheus-agent-v5\http_tools\server.py --host 127.0.0.1 --port 8050
```

## 6. How the Agent Should Work

Recommended flow:

```text
user question
  -> main prompt + prometheus-agent skill
  -> model chooses one semantic_key and one tool route
  -> platform calls the HTTP tool
  -> model formats the final answer from tool JSON
```

## 7. First-Version Scope

This V5 is meant for stable high-frequency questions.

Good fit:

- redis abnormality inspection
- jvm memory risk inspection
- node memory usage threshold filtering
- node cpu topn
- rabbitmq consumer capacity filtering
- metric discovery by job / labels / targets

Not intended for:

- free-form PromQL generation
- arbitrary boolean query language
- large multi-step root cause workflows
- replacing Grafana dashboards
