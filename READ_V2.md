# Prometheus 巡检 Agent V2 设计与接口说明

本版本是新的实现方案，代码全部放在新目录中：

- Python HTTP 服务：`prometheus_agent_v2/`
- V2 skills：`skills_v2/`
- AI 提示词模板：`prompts_v2/`

旧目录 `prometheus_agent/`、`skills/` 保留不动。

## 1. 能力分配

| 能力 | 实现位置 | 说明 |
|---|---|---|
| 用户意图理解 | AI 大模型 + `skills_v2/intent-extraction` | 提取 `prometheus_url`、`job`、`instance`，job/instance 可为空 |
| 指标目录 | Python 代码 `catalog.py` + `skills_v2/metric-query-catalog` | Python 决定实际查哪些指标，skill 用于让 AI 理解 |
| PromQL 查询计划 | Python HTTP `/v2/plan` | 按 job/instance/metric 生成查询任务 |
| Prometheus API 查询 | Python HTTP `/v2/query` | 一条一条查询，查询一个记录一个 |
| 突变/持续增长/预计到达上限 | Python HTTP `/v2/analyze` | 确定性分析和分级 |
| 单指标范围数据补充分析 | Python HTTP `/v2/build-ai-series-inputs` + AI 大模型 + `prompts_v2/metric_ai_comment.md` | 把指标历史采样数据压缩后交给 AI，分析固定规则之外的潜在问题 |
| 多指标关联分析 | AI 大模型 + `prompts_v2/correlation_analysis.md` | 基于全部异常项做关联分析 |
| 报告生成 | Python HTTP `/v2/report` | 生成 Markdown 或 HTML |

原则：Python 给出确定性 severity；AI 可以基于范围采样数据做补充分析和关联分析，但不直接改 severity。

## 2. 启动 HTTP 服务

```powershell
python -m prometheus_agent_v2 --host 127.0.0.1 --port 8010
```

健康检查：

```text
GET http://127.0.0.1:8010/health
```

## 3. 平台编排流程

推荐在公司平台中这样串：

```text
用户输入
  -> AI 使用 intent-extraction skill 提取 prometheus_url/job/instance
  -> HTTP POST /v2/plan 生成查询计划
  -> HTTP POST /v2/query 逐条查询 Prometheus
  -> HTTP POST /v2/analyze 做确定性分析和分级
  -> HTTP POST /v2/build-ai-series-inputs 构造 AI 范围数据分析输入
  -> AI 基于每条指标的历史采样数据做补充分析
  -> HTTP POST /v2/merge-ai-series-findings 合并 AI 补充分析
  -> AI 对异常项做关联性分析
  -> HTTP POST /v2/report 生成 md/html
```

如果不需要 AI 范围数据补充分析和关联分析，可以直接调用：

```text
POST /v2/run
```

它会执行 plan -> query -> analyze -> report，但不会调用大模型。

### 3.1 完整 AI 编排调用链路

下面是推荐的完整链路，适合用户通过聊天框发起巡检，并希望 AI 基于每条指标的范围采样数据做补充分析，再做多指标关联分析的场景。

| 步骤 | 调用方 | 被调用方 | 输入 | 输出 | 下一步 |
|---|---|---|---|---|---|
| 1 | 公司平台 | AI + `skills_v2/intent-extraction` | 用户原始问题 | `prometheus_url`、`job`、`instance`、时间范围 | 调 `/v2/plan` |
| 2 | 公司平台 | Python HTTP `/v2/plan` | Step1 的结构化意图 | `plan`，其中包含每个 job/instance/metric 的 PromQL 查询任务 | 调 `/v2/query` |
| 3 | 公司平台 | Python HTTP `/v2/query` | `plan` | `results`，每个 task 包含 current 查询结果、range 查询结果、errors | 调 `/v2/analyze` |
| 4 | 公司平台 | Python HTTP `/v2/analyze` | Step3 的 `results` | `analysis`，包含 severity、counts、items、risky_items | 调 `/v2/build-ai-series-inputs` |
| 5 | 公司平台 | Python HTTP `/v2/build-ai-series-inputs` | `results` + `analysis` | 每条指标给 AI 的压缩采样数据和 Python 分析证据 | 调 AI 做单指标范围数据分析 |
| 6 | 公司平台 | AI + `prompts_v2/metric_ai_comment.md` | Step5 的单条 `items[]` | 每条指标的 `summary`、`extra_risks`、`suggestion` | 调 `/v2/merge-ai-series-findings` |
| 7 | 公司平台 | Python HTTP `/v2/merge-ai-series-findings` | `analysis` + AI findings | 合并了 `ai_sample_analysis` 的 `analysis` | 调 AI 做关联分析 |
| 8 | 公司平台 | AI + `prompts_v2/correlation_analysis.md` | `analysis.risky_items`、`counts`、总体 severity | `ai_correlation` JSON | 调 `/v2/report` |
| 9 | 公司平台 | Python HTTP `/v2/report` | `analysis` + `ai_correlation` + `format` | Markdown 或 HTML 报告内容 | 返回给用户或落库 |

这条链路里，严重级别由 `/v2/analyze` 给出，AI 可以补充识别采样形态中的其他风险，但不修改 severity。

### 3.2 数据在各步骤中的流转

核心数据对象按下面顺序流动：

```text
用户问题
  -> Intent JSON
  -> Inspection Plan
  -> Query Results
  -> Deterministic Analysis
  -> AI Series Inputs
  -> AI Series Findings
  -> Merged Analysis
  -> AI Correlation
  -> Report
```

其中：

- `Intent JSON`：AI 从用户问题中抽取出来的结构化意图。
- `Inspection Plan`：`/v2/plan` 生成，包含所有要执行的 PromQL。
- `Query Results`：`/v2/query` 生成，逐条记录每个指标的查询结果。
- `Deterministic Analysis`：`/v2/analyze` 生成，包含固定规则分析和风险分级。
- `AI Series Inputs`：`/v2/build-ai-series-inputs` 生成，包含每条指标的压缩采样点和 Python 分析证据。
- `AI Series Findings`：AI 对单条指标范围数据的补充分析。
- `Merged Analysis`：`/v2/merge-ai-series-findings` 生成，把 AI 补充分析合并回分析结果。
- `AI Correlation`：AI 对多个异常指标之间关系的分析。
- `Report`：`/v2/report` 生成的 Markdown 或 HTML。

### 3.3 平台侧伪代码

```python
# Step 1: AI 意图识别
intent = call_llm(
    skill="skills_v2/intent-extraction",
    user_message=user_message,
)

# Step 2: 生成查询计划
plan_payload = http_post("http://127.0.0.1:8010/v2/plan", intent)
plan = plan_payload["plan"]

# Step 3: 查询 Prometheus
query_payload = http_post("http://127.0.0.1:8010/v2/query", {
    "plan": plan,
    "timeout_seconds": 20
})

# Step 4: Python 确定性分析
analysis = http_post("http://127.0.0.1:8010/v2/analyze", {
    "results": query_payload["results"]
})

# Step 5: 构造 AI 单指标范围数据分析输入
ai_series_inputs = http_post("http://127.0.0.1:8010/v2/build-ai-series-inputs", {
    "results": query_payload["results"],
    "analysis": analysis,
    "max_points_per_series": 24,
    "risky_only": False,
})

# Step 6: AI 基于历史采样数据做补充分析
findings = []
for item in ai_series_inputs["items"]:
    finding = call_llm(
        prompt_file="prompts_v2/metric_ai_comment.md",
        input=item,
    )
    findings.append(finding)

# Step 7: 合并 AI 补充分析
merged = http_post("http://127.0.0.1:8010/v2/merge-ai-series-findings", {
    "analysis": analysis,
    "findings": findings,
})

# Step 8: AI 关联性分析
ai_correlation = call_llm(
    prompt_file="prompts_v2/correlation_analysis.md",
    input={
        "severity": merged["analysis"]["severity"],
        "counts": merged["analysis"]["counts"],
        "risky_items": merged["analysis"]["risky_items"],
    },
)

# Step 9: 生成报告
report = http_post("http://127.0.0.1:8010/v2/report", {
    "analysis": merged["analysis"],
    "ai_correlation": ai_correlation,
    "format": "html",
})
```

### 3.4 无 AI 快速链路

如果只想验证 Python 服务能否跑通，或者定时任务暂时不需要 AI 解释，可以直接调用：

```text
POST /v2/run
```

等价于：

```text
/v2/plan -> /v2/query -> /v2/analyze -> /v2/report
```

但它不会执行：

- 单指标 AI 范围数据补充分析
- 多指标 AI 关联分析
- AI 生成运维建议

### 3.5 完整调用链路输入输出样例

下面给一个从用户输入到最终 HTML 报告的完整样例。为了让结构清晰，示例只展示 `redis_memory_usage` 这一条指标；真实执行时，`/v2/plan` 会按 catalog 返回 Redis 下配置的多条指标。

#### Step 0：用户输入

输入：

```text
请帮我检查 http://127.0.0.1:9090 上 redis 最近 24 小时是否有异常
```

#### Step 1：AI 意图识别

调用方：公司平台  
被调用方：AI + `skills_v2/intent-extraction/SKILL.md`

输入：

```json
{
  "user_message": "请帮我检查 http://127.0.0.1:9090 上 redis 最近 24 小时是否有异常"
}
```

输出：

```json
{
  "prometheus_url": "http://127.0.0.1:9090",
  "job": "redis",
  "instance": null,
  "range_hours": 24,
  "step_seconds": 60,
  "current_window": "5m",
  "need_ai_series_analysis": true,
  "need_ai_correlation": true
}
```

说明：

- `job = redis` 表示只查 Redis 指标。
- `instance = null` 表示查 Redis job 下全部 instance。
- 这里 AI 只做意图提取，不生成 PromQL。

#### Step 2：生成查询计划

调用方：公司平台  
被调用方：Python HTTP `/v2/plan`

请求：

```http
POST http://127.0.0.1:8010/v2/plan
Content-Type: application/json
```

```json
{
  "prometheus_url": "http://127.0.0.1:9090",
  "job": "redis",
  "instance": null,
  "range_hours": 24,
  "step_seconds": 60,
  "current_window": "5m"
}
```

响应：

```json
{
  "ok": true,
  "plan": {
    "prometheus_url": "http://127.0.0.1:9090",
    "job": "redis",
    "instance": null,
    "range_hours": 24,
    "step_seconds": 60,
    "current_window": "5m",
    "start": "2026-06-13T00:00:00Z",
    "end": "2026-06-14T00:00:00Z",
    "tasks": [
      {
        "task_id": "redis:all:redis_memory_usage",
        "job": "redis",
        "metric_id": "redis_memory_usage",
        "metric_name": "Redis Memory Usage",
        "instance": null,
        "current_promql": "redis_memory_used_bytes / redis_memory_max_bytes * 100",
        "range_promql": "redis_memory_used_bytes / redis_memory_max_bytes * 100",
        "start": "2026-06-13T00:00:00Z",
        "end": "2026-06-14T00:00:00Z",
        "step_seconds": 60,
        "spec": {
          "job": "redis",
          "id": "redis_memory_usage",
          "name": "Redis Memory Usage",
          "value_type": "percent",
          "unit": "%",
          "direction": "higher_is_bad",
          "analysis_methods": ["threshold", "burst", "sustained_growth", "time_to_limit"],
          "warning": 75,
          "critical": 90,
          "max_value": 100
        }
      }
    ]
  }
}
```

说明：

- `/v2/plan` 根据 Python 内置 catalog 生成 PromQL。
- 一个 `task` 对应一个 job + instance 范围 + metric。
- 真实 Redis catalog 还会包含 `redis_up`、`redis_connected_clients`、`redis_evicted_keys_rate` 等 task。

#### Step 3：逐条查询 Prometheus

调用方：公司平台  
被调用方：Python HTTP `/v2/query`

请求：

```http
POST http://127.0.0.1:8010/v2/query
Content-Type: application/json
```

```json
{
  "plan": {
    "prometheus_url": "http://127.0.0.1:9090",
    "job": "redis",
    "instance": null,
    "range_hours": 24,
    "step_seconds": 60,
    "current_window": "5m",
    "tasks": [
      {
        "task_id": "redis:all:redis_memory_usage",
        "job": "redis",
        "metric_id": "redis_memory_usage",
        "metric_name": "Redis Memory Usage",
        "current_promql": "redis_memory_used_bytes / redis_memory_max_bytes * 100",
        "range_promql": "redis_memory_used_bytes / redis_memory_max_bytes * 100",
        "start": "2026-06-13T00:00:00Z",
        "end": "2026-06-14T00:00:00Z",
        "step_seconds": 60,
        "spec": {
          "job": "redis",
          "id": "redis_memory_usage",
          "name": "Redis Memory Usage",
          "value_type": "percent",
          "unit": "%",
          "direction": "higher_is_bad",
          "analysis_methods": ["threshold", "burst", "sustained_growth", "time_to_limit"],
          "warning": 75,
          "critical": 90,
          "max_value": 100
        }
      }
    ]
  },
  "timeout_seconds": 20
}
```

响应：

```json
{
  "ok": true,
  "results": [
    {
      "task": {
        "task_id": "redis:all:redis_memory_usage",
        "job": "redis",
        "metric_id": "redis_memory_usage",
        "metric_name": "Redis Memory Usage"
      },
      "ok": true,
      "current": [
        {
          "labels": {
            "job": "redis",
            "instance": "10.0.0.12:9121"
          },
          "points": [
            {
              "timestamp": "2026-06-14T00:00:00Z",
              "value": 82.4
            }
          ]
        }
      ],
      "range": [
        {
          "labels": {
            "job": "redis",
            "instance": "10.0.0.12:9121"
          },
          "points": [
            {
              "timestamp": "2026-06-13T00:00:00Z",
              "value": 61.2
            },
            {
              "timestamp": "2026-06-13T06:00:00Z",
              "value": 68.5
            },
            {
              "timestamp": "2026-06-13T12:00:00Z",
              "value": 74.8
            },
            {
              "timestamp": "2026-06-13T18:00:00Z",
              "value": 79.1
            },
            {
              "timestamp": "2026-06-14T00:00:00Z",
              "value": 82.4
            }
          ]
        }
      ],
      "errors": []
    }
  ]
}
```

说明：

- `current` 是当前状态，通常来自最近 5 分钟窗口。
- `range` 是历史采样数据，用于趋势分析。
- 如果某条查询失败，`ok=false` 且错误写入 `errors`，不会中断其他 task。

#### Step 4：Python 确定性分析

调用方：公司平台  
被调用方：Python HTTP `/v2/analyze`

请求：

```http
POST http://127.0.0.1:8010/v2/analyze
Content-Type: application/json
```

```json
{
  "results": [
    {
      "task": {
        "task_id": "redis:all:redis_memory_usage",
        "job": "redis",
        "metric_id": "redis_memory_usage",
        "metric_name": "Redis Memory Usage",
        "spec": {
          "unit": "%",
          "direction": "higher_is_bad",
          "warning": 75,
          "critical": 90,
          "max_value": 100
        }
      },
      "ok": true,
      "current": [
        {
          "labels": {
            "job": "redis",
            "instance": "10.0.0.12:9121"
          },
          "points": [
            {
              "timestamp": "2026-06-14T00:00:00Z",
              "value": 82.4
            }
          ]
        }
      ],
      "range": [
        {
          "labels": {
            "job": "redis",
            "instance": "10.0.0.12:9121"
          },
          "points": [
            {"timestamp": "2026-06-13T00:00:00Z", "value": 61.2},
            {"timestamp": "2026-06-13T06:00:00Z", "value": 68.5},
            {"timestamp": "2026-06-13T12:00:00Z", "value": 74.8},
            {"timestamp": "2026-06-13T18:00:00Z", "value": 79.1},
            {"timestamp": "2026-06-14T00:00:00Z", "value": 82.4}
          ]
        }
      ],
      "errors": []
    }
  ]
}
```

响应：

```json
{
  "ok": true,
  "severity": "warning",
  "counts": {
    "critical": 0,
    "warning": 1,
    "info": 0,
    "ok": 0,
    "unknown": 0
  },
  "items": [
    {
      "job": "redis",
      "instance": "10.0.0.12:9121",
      "metric_id": "redis_memory_usage",
      "metric_name": "Redis Memory Usage",
      "severity": "warning",
      "current_value": 82.4,
      "reason": "Current value is already warning. Series is continuously growing without clear slowdown.",
      "analysis": {
        "current": 82.4,
        "min": 61.2,
        "max": 82.4,
        "avg": 73.2,
        "p95": 81.74,
        "slope_per_hour": 0.88,
        "forecast_24h": 103.52,
        "burst": false,
        "sustained_growth": true,
        "time_to_limit_hours": 20.0,
        "warning": 75,
        "critical": 90,
        "max_value": 100,
        "unit": "%"
      },
      "ai_comment": null
    }
  ],
  "risky_items": [
    {
      "job": "redis",
      "instance": "10.0.0.12:9121",
      "metric_id": "redis_memory_usage",
      "severity": "warning"
    }
  ]
}
```

说明：

- `severity` 由 Python 固定规则给出。
- `reason` 是规则分析结论。
- `analysis` 中的字段是后续 AI 范围数据补充分析和关联分析的证据。

#### Step 5：构造 AI 范围数据分析输入

调用方：公司平台  
被调用方：Python HTTP `/v2/build-ai-series-inputs`

请求：

```json
{
  "results": [
    {
      "task": {
        "task_id": "redis:all:redis_memory_usage",
        "job": "redis",
        "metric_id": "redis_memory_usage",
        "metric_name": "Redis Memory Usage"
      },
      "ok": true,
      "range": [
        {
          "labels": {
            "job": "redis",
            "instance": "10.0.0.12:9121"
          },
          "points": [
            {"timestamp": "2026-06-13T00:00:00Z", "value": 61.2},
            {"timestamp": "2026-06-13T06:00:00Z", "value": 68.5},
            {"timestamp": "2026-06-13T12:00:00Z", "value": 74.8},
            {"timestamp": "2026-06-13T18:00:00Z", "value": 79.1},
            {"timestamp": "2026-06-14T00:00:00Z", "value": 82.4}
          ]
        }
      ]
    }
  ],
  "analysis": {
    "items": [
      {
        "job": "redis",
        "instance": "10.0.0.12:9121",
        "metric_id": "redis_memory_usage",
        "metric_name": "Redis Memory Usage",
        "severity": "warning",
        "reason": "Current value is already warning. Series is continuously growing without clear slowdown.",
        "analysis": {
          "current": 82.4,
          "avg": 73.2,
          "p95": 81.74,
          "slope_per_hour": 0.88,
          "forecast_24h": 103.52,
          "sustained_growth": true,
          "time_to_limit_hours": 20.0,
          "unit": "%"
        }
      }
    ]
  },
  "max_points_per_series": 24,
  "risky_only": false
}
```

响应：

```json
{
  "ok": true,
  "items": [
    {
      "job": "redis",
      "instance": "10.0.0.12:9121",
      "metric_id": "redis_memory_usage",
      "metric_name": "Redis Memory Usage",
      "series_labels": {
        "job": "redis",
        "instance": "10.0.0.12:9121"
      },
      "python_severity": "warning",
      "python_reason": "Current value is already warning. Series is continuously growing without clear slowdown.",
      "python_analysis": {
        "current": 82.4,
        "avg": 73.2,
        "p95": 81.74,
        "slope_per_hour": 0.88,
        "forecast_24h": 103.52,
        "sustained_growth": true,
        "time_to_limit_hours": 20.0,
        "unit": "%"
      },
      "sample_policy": {
        "original_point_count": 5,
        "included_point_count": 5,
        "sampling": "evenly_spaced"
      },
      "range_points": [
        {"timestamp": "2026-06-13T00:00:00Z", "value": 61.2},
        {"timestamp": "2026-06-13T06:00:00Z", "value": 68.5},
        {"timestamp": "2026-06-13T12:00:00Z", "value": 74.8},
        {"timestamp": "2026-06-13T18:00:00Z", "value": 79.1},
        {"timestamp": "2026-06-14T00:00:00Z", "value": 82.4}
      ],
      "instruction": "Analyze this metric's historical samples for additional concerns that the fixed Python rules may not capture. Do not change python_severity."
    }
  ]
}
```

说明：

- 这里会把 Prometheus range 采样数据交给 AI，但不是无限制传全量点。
- `max_points_per_series` 用于控制每条 series 最多给 AI 多少个点。
- Python 固定分析结果也会一起给 AI，作为上下文和约束。

#### Step 6：AI 基于范围采样数据做补充分析

调用方：公司平台  
被调用方：AI + `prompts_v2/metric_ai_comment.md`

输入：

```json
{
  "job": "redis",
  "instance": "10.0.0.12:9121",
  "metric_id": "redis_memory_usage",
  "metric_name": "Redis Memory Usage",
  "python_severity": "warning",
  "python_reason": "Current value is already warning. Series is continuously growing without clear slowdown.",
  "python_analysis": {
    "current": 82.4,
    "avg": 73.2,
    "p95": 81.74,
    "slope_per_hour": 0.88,
    "forecast_24h": 103.52,
    "sustained_growth": true,
    "time_to_limit_hours": 20.0,
    "unit": "%"
  },
  "range_points": [
    {"timestamp": "2026-06-13T00:00:00Z", "value": 61.2},
    {"timestamp": "2026-06-13T06:00:00Z", "value": 68.5},
    {"timestamp": "2026-06-13T12:00:00Z", "value": 74.8},
    {"timestamp": "2026-06-13T18:00:00Z", "value": 79.1},
    {"timestamp": "2026-06-14T00:00:00Z", "value": 82.4}
  ]
}
```

输出：

```json
{
  "job": "redis",
  "instance": "10.0.0.12:9121",
  "metric_id": "redis_memory_usage",
  "summary": "内存使用率阶梯式上升，未看到明显回落。",
  "extra_risks": [
    "高位持续时间较长",
    "采样点呈连续抬升"
  ],
  "suggestion": "建议检查 key 增长、过期策略和 maxmemory 配置。"
}
```

说明：

- AI 在这里看的是历史采样数据本身，而不只是 Python 的分析结论。
- AI 输出的是补充发现，不改变 `python_severity`。

#### Step 7：合并 AI 范围数据补充分析

调用方：公司平台  
被调用方：Python HTTP `/v2/merge-ai-series-findings`

请求：

```json
{
  "analysis": {
    "severity": "warning",
    "counts": {
      "warning": 1
    },
    "items": [
      {
        "job": "redis",
        "instance": "10.0.0.12:9121",
        "metric_id": "redis_memory_usage",
        "metric_name": "Redis Memory Usage",
        "severity": "warning",
        "current_value": 82.4,
        "reason": "Current value is already warning. Series is continuously growing without clear slowdown."
      }
    ]
  },
  "findings": [
    {
      "job": "redis",
      "instance": "10.0.0.12:9121",
      "metric_id": "redis_memory_usage",
      "summary": "内存使用率阶梯式上升，未看到明显回落。",
      "extra_risks": [
        "高位持续时间较长",
        "采样点呈连续抬升"
      ],
      "suggestion": "建议检查 key 增长、过期策略和 maxmemory 配置。"
    }
  ]
}
```

响应：

```json
{
  "ok": true,
  "analysis": {
    "severity": "warning",
    "counts": {
      "warning": 1
    },
    "items": [
      {
        "job": "redis",
        "instance": "10.0.0.12:9121",
        "metric_id": "redis_memory_usage",
        "metric_name": "Redis Memory Usage",
        "severity": "warning",
        "current_value": 82.4,
        "reason": "Current value is already warning. Series is continuously growing without clear slowdown.",
        "ai_sample_analysis": {
          "summary": "内存使用率阶梯式上升，未看到明显回落。",
          "extra_risks": [
            "高位持续时间较长",
            "采样点呈连续抬升"
          ],
          "suggestion": "建议检查 key 增长、过期策略和 maxmemory 配置。"
        },
        "ai_comment": "内存使用率阶梯式上升，未看到明显回落。"
      }
    ],
    "risky_items": [
      {
        "job": "redis",
        "instance": "10.0.0.12:9121",
        "metric_id": "redis_memory_usage",
        "severity": "warning",
        "ai_comment": "内存使用率阶梯式上升，未看到明显回落。"
      }
    ]
  }
}
```

#### Step 8：AI 多指标关联分析

调用方：公司平台  
被调用方：AI + `prompts_v2/correlation_analysis.md`

输入：

```json
{
  "severity": "warning",
  "counts": {
    "critical": 0,
    "warning": 1,
    "info": 0,
    "ok": 0,
    "unknown": 0
  },
  "risky_items": [
    {
      "job": "redis",
      "instance": "10.0.0.12:9121",
      "metric_id": "redis_memory_usage",
      "metric_name": "Redis Memory Usage",
      "severity": "warning",
      "current_value": 82.4,
      "ai_sample_analysis": {
        "summary": "内存使用率阶梯式上升，未看到明显回落。",
        "extra_risks": [
          "高位持续时间较长",
          "采样点呈连续抬升"
        ],
        "suggestion": "建议检查 key 增长、过期策略和 maxmemory 配置。"
      }
    }
  ]
}
```

输出：

```json
{
  "summary": "当前主要风险集中在 Redis 实例 10.0.0.12:9121 的内存使用率持续上升。",
  "correlations": [
    {
      "level": "warning",
      "job": "redis",
      "instance": "10.0.0.12:9121",
      "reason": "Redis 内存使用率已超过 warning，并保持持续增长趋势。",
      "suggestion": "建议优先检查 key 增长、过期策略、maxmemory 配置和是否存在大 key。"
    }
  ]
}
```

说明：

- 如果有多个异常指标，AI 在这里做跨指标关联。
- 如果只有一个异常指标，AI 只做保守总结，不编造其他问题。
#### Step 8：生成最终报告

调用方：公司平台  
被调用方：Python HTTP `/v2/report`

请求：

```json
{
  "analysis": {
    "severity": "warning",
    "counts": {
      "critical": 0,
      "warning": 1,
      "info": 0,
      "ok": 0,
      "unknown": 0
    },
    "items": [
      {
        "job": "redis",
        "instance": "10.0.0.12:9121",
        "metric_id": "redis_memory_usage",
        "metric_name": "Redis Memory Usage",
        "severity": "warning",
        "current_value": 82.4,
        "reason": "Current value is already warning. Series is continuously growing without clear slowdown.",
        "analysis": {
          "unit": "%"
        },
        "ai_comment": "内存使用率已达 warning，且持续上升，约20小时可能接近上限。"
      }
    ]
  },
  "ai_correlation": {
    "summary": "当前主要风险集中在 Redis 实例 10.0.0.12:9121 的内存使用率持续上升。",
    "correlations": [
      {
        "level": "warning",
        "job": "redis",
        "instance": "10.0.0.12:9121",
        "reason": "Redis 内存使用率已超过 warning，并保持持续增长趋势。",
        "suggestion": "建议优先检查 key 增长、过期策略、maxmemory 配置和是否存在大 key。"
      }
    ]
  },
  "format": "html"
}
```

响应：

```json
{
  "ok": true,
  "format": "html",
  "content": "<!doctype html><html lang=\"zh-CN\">...</html>"
}
```

如果要 Markdown：

```json
{
  "analysis": {},
  "ai_correlation": {},
  "format": "md"
}
```

响应：

```json
{
  "ok": true,
  "format": "markdown",
  "content": "# Prometheus 巡检报告\n\n- 生成时间: ..."
}
```

#### Step 9：返回给用户

最终用户看到的内容可以是：

```text
本次 Redis 巡检总体等级为 warning。

主要风险：
- 10.0.0.12:9121 的 Redis Memory Usage 当前为 82.4%，已超过 warning 阈值 75%。
- 过去 24 小时持续上升，按趋势约 20 小时可能接近上限。

建议：
- 检查 key 增长情况。
- 检查是否存在大 key。
- 检查 maxmemory 和淘汰策略配置。
- 结合 Redis 日志确认是否出现 evicted keys 或 rejected connections。
```

## 4. 关键接口

### 4.1 获取指标目录

```text
GET /v2/catalog
```

返回 node、jvm、redis、rabbitmq 下配置的指标。

### 4.2 生成查询计划

```text
POST /v2/plan
```

请求：

```json
{
  "prometheus_url": "http://127.0.0.1:9090",
  "job": "redis",
  "instance": null,
  "range_hours": 24,
  "step_seconds": 60,
  "current_window": "5m"
}
```

说明：

- `job` 可为空，表示查询全部已配置 job。
- `instance` 可为空，表示查询全部 instance。
- 当前状态使用 `current_promql`。
- 历史趋势使用 `range_promql`。

### 4.3 查询 Prometheus

```text
POST /v2/query
```

请求可以直接传 `/v2/plan` 返回的 `plan`：

```json
{
  "plan": {
    "...": "..."
  },
  "timeout_seconds": 20
}
```

返回结构按 task 记录：

```json
{
  "ok": true,
  "results": [
    {
      "task": {},
      "ok": true,
      "current": [],
      "range": [],
      "errors": []
    }
  ]
}
```

如果某个指标查询失败，只会记录在该 task 的 `errors` 中，不会中断整个巡检。

### 4.4 分析查询结果

```text
POST /v2/analyze
```

请求：

```json
{
  "results": []
}
```

分析方法包括：

- `threshold`：阈值判断
- `burst`：后半段均值相比前半段大幅上升
- `sustained_growth`：多数采样点持续增加
- `time_to_limit`：按趋势估算多久达到 `max_value`、`critical` 或 `warning`

返回：

```json
{
  "ok": true,
  "severity": "warning",
  "counts": {
    "critical": 0,
    "warning": 1,
    "info": 2,
    "ok": 10,
    "unknown": 0
  },
  "items": [],
  "risky_items": []
}
```

### 4.5 构造 AI 范围数据分析输入

```text
POST /v2/build-ai-series-inputs
```

请求：

```json
{
  "results": [],
  "analysis": {},
  "max_points_per_series": 24,
  "risky_only": false
}
```

返回：

```json
{
  "ok": true,
  "items": [
    {
      "job": "redis",
      "instance": "10.0.0.12:9121",
      "metric_id": "redis_memory_usage",
      "metric_name": "Redis Memory Usage",
      "python_severity": "warning",
      "python_reason": "Current value is already warning.",
      "python_analysis": {},
      "sample_policy": {
        "original_point_count": 1440,
        "included_point_count": 24,
        "sampling": "evenly_spaced"
      },
      "range_points": []
    }
  ]
}
```

这个接口的作用是把 `/v2/query` 返回的范围采样数据压缩成适合发送给 AI 的输入。不要直接把无限量原始采样点全部发给大模型。

### 4.6 合并 AI 范围数据补充分析

```text
POST /v2/merge-ai-series-findings
```

请求：

```json
{
  "analysis": {},
  "findings": [
    {
      "job": "redis",
      "instance": "10.0.0.12:9121",
      "metric_id": "redis_memory_usage",
      "summary": "内存使用率阶梯式上升，未看到明显回落。",
      "extra_risks": ["高位持续时间较长"],
      "suggestion": "建议检查 key 增长、过期策略和 maxmemory 配置。"
    }
  ]
}
```

返回：

```json
{
  "ok": true,
  "analysis": {}
}
```

该接口会把 AI 输出合并到每个指标的 `ai_sample_analysis` 字段，同时保留 Python 原始 severity。

### 4.7 合并 AI 单指标简评（兼容旧链路）

```text
POST /v2/merge-ai-comments
```

请求：

```json
{
  "analysis": {},
  "comments": [
    {
      "job": "redis",
      "instance": "127.0.0.1:9121",
      "metric_id": "redis_memory_usage",
      "comment": "过去24小时持续上升，建议关注内存上限。"
    }
  ]
}
```

这个接口保留给旧的“AI 只生成简评”链路。新链路优先使用 `/v2/build-ai-series-inputs` 和 `/v2/merge-ai-series-findings`。
### 4.8 生成报告

```text
POST /v2/report
```

请求：

```json
{
  "analysis": {},
  "ai_correlation": {
    "summary": "整体风险摘要",
    "correlations": []
  },
  "format": "html"
}
```

`format` 支持：

- `html`
- `md`
- `markdown`

### 4.9 无 AI 端到端执行

```text
POST /v2/run
```

请求：

```json
{
  "prometheus_url": "http://127.0.0.1:9090",
  "job": "redis",
  "instance": null,
  "range_hours": 24,
  "step_seconds": 60,
  "current_window": "5m",
  "format": "html"
}
```

返回包含：

- `plan`
- `query`
- `analysis`
- `report.content`

## 5. AI 插入点

### Step 1 意图理解

使用：

```text
skills_v2/intent-extraction/SKILL.md
```

AI 输出 JSON 后，把 JSON 传给 `/v2/plan`。

### Step 5 单指标范围数据补充分析

使用：

```text
prompts_v2/metric_ai_comment.md
```

推荐先调用 `/v2/build-ai-series-inputs`，再把返回的 `items[]` 逐条发给 AI。

输入建议包含：

- `python_severity`
- `python_reason`
- `python_analysis`
- `sample_policy`
- `range_points`

AI 输出后，调用 `/v2/merge-ai-series-findings` 合并回 `analysis`。

注意：`range_points` 是经过 Python 服务抽样后的历史采样点，避免把完整高频采样数据全部发给 AI。

### Step 6 关联性分析

使用：

```text
prompts_v2/correlation_analysis.md
```

输入建议只给：

- `analysis.risky_items`
- `analysis.counts`
- `analysis.severity`

关联分析阶段建议只传异常项和 AI 补充分析结论，不再传完整 `range_points`，降低 token 和泄露风险。

## 6. 当前内置 Job 与指标

当前 Python catalog 内置：

- `node`
  - CPU Usage
  - Memory Usage
  - Filesystem Usage
- `jvm`
  - JVM Heap Usage
  - JVM GC Pause Rate
  - JVM Live Threads
- `redis`
  - Redis Up
  - Redis Memory Usage
  - Redis Connected Clients
  - Redis Evicted Keys Rate
- `rabbitmq`
  - Queue Ready
  - Queue Unacked
  - Consumers

后续新增指标优先改：

```text
prometheus_agent_v2/catalog.py
```

如果希望不改代码，也可以扩展服务支持从 JSON 文件加载 catalog。当前 `/v2/plan` 已支持传 `catalog_path`。

## 7. 注意事项

- 当前服务不负责调用 AI，大模型调用由公司平台编排。
- 当前服务不保存报告文件，只返回报告内容字符串。
- 当前服务不做 Prometheus 地址白名单校验；如果生产需要，建议在平台或服务前面加白名单。
- 当前服务使用 Python 标准库，无第三方依赖。
- 查询全部 job 且时间范围较大时，Prometheus 压力会变大，建议平台限制 `range_hours` 和 `step_seconds`。


