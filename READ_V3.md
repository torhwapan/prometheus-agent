# Prometheus 巡检 Agent V3 设计与接口说明

V3 保持 V2 的功能目标，但调整状态管理方式：

- 平台仍负责流程编排和调用 AI。
- Python 服务负责维护查询计划、查询结果、分析结果、AI 输入、AI findings、报告等中间态。
- 平台后续步骤只需要传 `inspection_id`，不再反复携带大段 `plan`、`query_results`、`analysis`。
- 用户意图解析从 skill 改为提示词：`prompts_v3/intent_extraction.md`。

V2 代码和 skills 保持不动。V3 新代码位于：

```text
prometheus_agent_v3/
prompts_v3/
READ_V3.md
```

## 1. 启动服务

```powershell
python -m prometheus_agent_v3 --host 127.0.0.1 --port 8020
```

健康检查：

```text
GET http://127.0.0.1:8020/health
```

## 2. V3 状态模型

Python 服务内部维护一个 `inspection` 记录：

```json
{
  "inspection_id": "uuid",
  "status": "planned",
  "intent": {},
  "plan": {},
  "query": {},
  "analysis": {},
  "ai_series_inputs": {},
  "ai_series_findings": [],
  "ai_correlation": {},
  "report": {},
  "errors": []
}
```

当前实现是内存存储，服务重启后状态会丢失。后续可以把 `InspectionStore` 替换成文件、Redis 或数据库。

## 3. 推荐调用链路

```text
用户输入
  -> AI 使用 prompts_v3/intent_extraction.md 解析意图
  -> POST /v3/inspections 创建巡检，服务端生成并保存 plan
  -> POST /v3/query 使用 inspection_id 查询 Prometheus，服务端保存 query results
  -> POST /v3/analyze 使用 inspection_id 分析，服务端保存 analysis
  -> POST /v3/build-ai-series-inputs 使用 inspection_id 构造 AI 输入，服务端保存 ai_series_inputs
  -> 平台调用 AI 分析 ai_series_inputs.items
  -> POST /v3/merge-ai-series-findings 使用 inspection_id 合并 AI findings，服务端保存 merged analysis
  -> 平台调用 AI 做关联分析
  -> POST /v3/merge-ai-correlation 使用 inspection_id 保存 AI correlation
  -> POST /v3/report 使用 inspection_id 生成报告，服务端保存 report
```

平台不再保存大段中间结果，只需要保存 `inspection_id` 和 AI 调用输出。

## 4. 关键接口

### 4.1 创建巡检

```text
POST /v3/inspections
```

请求来自 AI 意图解析结果：

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

响应：

```json
{
  "ok": true,
  "inspection_id": "b4d5...",
  "status": "planned",
  "plan_summary": {
    "prometheus_url": "http://127.0.0.1:9090",
    "job": "redis",
    "instance": null,
    "range_hours": 24,
    "step_seconds": 60,
    "task_count": 4
  }
}
```

### 4.2 查询 Prometheus

```text
POST /v3/query
```

请求：

```json
{
  "inspection_id": "b4d5...",
  "timeout_seconds": 20
}
```

响应：

```json
{
  "ok": true,
  "inspection_id": "b4d5...",
  "status": "queried",
  "query_summary": {
    "task_count": 4,
    "failed_count": 0
  }
}
```

查询结果保存在 Python 服务端。

### 4.3 固定规则分析

```text
POST /v3/analyze
```

请求：

```json
{
  "inspection_id": "b4d5..."
}
```

响应：

```json
{
  "ok": true,
  "inspection_id": "b4d5...",
  "status": "analyzed",
  "analysis_summary": {
    "severity": "warning",
    "counts": {
      "critical": 0,
      "warning": 1,
      "info": 2,
      "ok": 10,
      "unknown": 0
    },
    "risky_count": 3
  }
}
```

### 4.4 构造 AI 单指标范围数据输入

```text
POST /v3/build-ai-series-inputs
```

请求：

```json
{
  "inspection_id": "b4d5...",
  "max_points_per_series": 24,
  "risky_only": false
}
```

响应：

```json
{
  "ok": true,
  "inspection_id": "b4d5...",
  "status": "ai_inputs_built",
  "items": [
    {
      "job": "redis",
      "instance": "10.0.0.12:9121",
      "metric_id": "redis_memory_usage",
      "python_severity": "warning",
      "range_points": []
    }
  ]
}
```

平台把 `items[]` 逐条发给 AI，使用：

```text
prompts_v2/metric_ai_comment.md
```

### 4.5 合并 AI 单指标补充分析

```text
POST /v3/merge-ai-series-findings
```

请求：

```json
{
  "inspection_id": "b4d5...",
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

响应：

```json
{
  "ok": true,
  "inspection_id": "b4d5...",
  "status": "ai_findings_merged",
  "analysis_summary": {
    "severity": "warning",
    "risky_count": 3
  }
}
```

### 4.6 保存 AI 关联分析

```text
POST /v3/merge-ai-correlation
```

请求：

```json
{
  "inspection_id": "b4d5...",
  "ai_correlation": {
    "summary": "主要风险集中在 Redis 内存持续增长。",
    "correlations": [
      {
        "level": "warning",
        "job": "redis",
        "instance": "10.0.0.12:9121",
        "reason": "Redis 内存使用率持续增长。",
        "suggestion": "检查 key 增长和 maxmemory 配置。"
      }
    ]
  }
}
```

### 4.7 生成报告

```text
POST /v3/report
```

请求：

```json
{
  "inspection_id": "b4d5...",
  "format": "html"
}
```

响应：

```json
{
  "ok": true,
  "inspection_id": "b4d5...",
  "status": "reported",
  "report": {
    "format": "html",
    "content": "<!doctype html>..."
  }
}
```

### 4.8 查看巡检详情

```text
GET /v3/inspections/{inspection_id}
```

返回服务端保存的完整中间态，便于调试和审计。

### 4.9 无 AI 快速链路

```text
POST /v3/run-deterministic
```

请求同 `/v3/inspections`，服务会自动执行：

```text
create -> query -> analyze -> report
```

不包含 AI 单指标分析和 AI 关联分析。

## 5. 完整流程示例

下面用一次 Redis 巡检说明 V3 从头到尾怎么调用。示例重点展示 V3 的状态管理方式：平台只需要保存 `inspection_id`，查询计划、查询结果、分析结果都保存在 Python 服务端。

### Step 0：用户输入

```text
请帮我巡检 http://127.0.0.1:9090 上 redis 最近 24 小时是否异常
```

### Step 1：AI 意图解析

调用方：公司平台  
被调用方：AI + `prompts_v3/intent_extraction.md`

输入：

```json
{
  "user_message": "请帮我巡检 http://127.0.0.1:9090 上 redis 最近 24 小时是否异常"
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
  "format": "html",
  "need_ai_series_analysis": true,
  "need_ai_correlation": true
}
```

### Step 2：创建巡检并保存查询计划

调用方：公司平台  
被调用方：Python HTTP `/v3/inspections`

请求：

```json
{
  "prometheus_url": "http://127.0.0.1:9090",
  "job": "redis",
  "instance": null,
  "range_hours": 24,
  "step_seconds": 60,
  "current_window": "5m",
  "format": "html",
  "need_ai_series_analysis": true,
  "need_ai_correlation": true
}
```

响应：

```json
{
  "ok": true,
  "inspection_id": "ins-001",
  "status": "planned",
  "plan_summary": {
    "prometheus_url": "http://127.0.0.1:9090",
    "job": "redis",
    "instance": null,
    "range_hours": 24,
    "step_seconds": 60,
    "task_count": 4
  }
}
```

服务端此时保存：

```json
{
  "inspection_id": "ins-001",
  "status": "planned",
  "intent": {
    "prometheus_url": "http://127.0.0.1:9090",
    "job": "redis"
  },
  "plan": {
    "tasks": [
      {
        "task_id": "redis:all:redis_memory_usage",
        "metric_id": "redis_memory_usage",
        "current_promql": "redis_memory_used_bytes / redis_memory_max_bytes * 100",
        "range_promql": "redis_memory_used_bytes / redis_memory_max_bytes * 100"
      }
    ]
  }
}
```

平台后续只需要保存：

```json
{
  "inspection_id": "ins-001"
}
```

### Step 3：执行 Prometheus 查询

调用方：公司平台  
被调用方：Python HTTP `/v3/query`

请求：

```json
{
  "inspection_id": "ins-001",
  "timeout_seconds": 20
}
```

响应：

```json
{
  "ok": true,
  "inspection_id": "ins-001",
  "status": "queried",
  "query_summary": {
    "task_count": 4,
    "failed_count": 0
  }
}
```

服务端此时保存 `query.results`，结构类似：

```json
{
  "query": {
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
}
```

注意：这些查询结果没有返回给平台，保存在 Python 服务端。

### Step 4：执行固定规则分析

调用方：公司平台  
被调用方：Python HTTP `/v3/analyze`

请求：

```json
{
  "inspection_id": "ins-001"
}
```

响应：

```json
{
  "ok": true,
  "inspection_id": "ins-001",
  "status": "analyzed",
  "analysis_summary": {
    "severity": "warning",
    "counts": {
      "critical": 0,
      "warning": 1,
      "info": 0,
      "ok": 3,
      "unknown": 0
    },
    "risky_count": 1
  }
}
```

服务端此时保存 `analysis`，例如：

```json
{
  "analysis": {
    "severity": "warning",
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
          "avg": 73.2,
          "p95": 81.74,
          "slope_per_hour": 0.88,
          "forecast_24h": 103.52,
          "sustained_growth": true,
          "time_to_limit_hours": 20.0,
          "unit": "%"
        }
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
}
```

### Step 5：构造 AI 单指标范围数据输入

调用方：公司平台  
被调用方：Python HTTP `/v3/build-ai-series-inputs`

请求：

```json
{
  "inspection_id": "ins-001",
  "max_points_per_series": 24,
  "risky_only": false
}
```

响应：

```json
{
  "ok": true,
  "inspection_id": "ins-001",
  "status": "ai_inputs_built",
  "items": [
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
        "slope_per_hour": 0.88,
        "time_to_limit_hours": 20.0,
        "unit": "%"
      },
      "sample_policy": {
        "original_point_count": 1440,
        "included_point_count": 24,
        "sampling": "evenly_spaced"
      },
      "range_points": [
        {"timestamp": "2026-06-13T00:00:00Z", "value": 61.2},
        {"timestamp": "2026-06-13T06:00:00Z", "value": 68.5},
        {"timestamp": "2026-06-13T12:00:00Z", "value": 74.8},
        {"timestamp": "2026-06-13T18:00:00Z", "value": 79.1},
        {"timestamp": "2026-06-14T00:00:00Z", "value": 82.4}
      ]
    }
  ]
}
```

这里平台需要拿 `items[]` 逐条调用 AI。服务端也保存了同一份 `ai_series_inputs`。

### Step 6：AI 分析单指标范围数据

调用方：公司平台  
被调用方：AI + `prompts_v2/metric_ai_comment.md`

输入：`/v3/build-ai-series-inputs` 返回的单个 `items[]` 元素。

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

### Step 7：合并 AI 单指标分析

调用方：公司平台  
被调用方：Python HTTP `/v3/merge-ai-series-findings`

请求：

```json
{
  "inspection_id": "ins-001",
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
  "inspection_id": "ins-001",
  "status": "ai_findings_merged",
  "analysis_summary": {
    "severity": "warning",
    "counts": {
      "critical": 0,
      "warning": 1,
      "info": 0,
      "ok": 3,
      "unknown": 0
    },
    "risky_count": 1
  }
}
```

服务端此时的 `analysis.items[]` 中会多出：

```json
{
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
```

### Step 8：获取巡检详情，准备 AI 关联分析

调用方：公司平台  
被调用方：Python HTTP `GET /v3/inspections/{inspection_id}`

请求：

```text
GET /v3/inspections/ins-001
```

响应节选：

```json
{
  "ok": true,
  "inspection": {
    "inspection_id": "ins-001",
    "status": "ai_findings_merged",
    "analysis": {
      "severity": "warning",
      "counts": {
        "critical": 0,
        "warning": 1,
        "info": 0,
        "ok": 3,
        "unknown": 0
      },
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
}
```

平台把 `analysis.severity`、`analysis.counts`、`analysis.risky_items` 发给 AI 做关联分析。

### Step 9：AI 多指标关联分析

调用方：公司平台  
被调用方：AI + `prompts_v2/correlation_analysis.md`

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

### Step 10：保存 AI 关联分析

调用方：公司平台  
被调用方：Python HTTP `/v3/merge-ai-correlation`

请求：

```json
{
  "inspection_id": "ins-001",
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
  }
}
```

响应：

```json
{
  "ok": true,
  "inspection_id": "ins-001",
  "status": "ai_correlation_merged",
  "ai_correlation": {
    "summary": "当前主要风险集中在 Redis 实例 10.0.0.12:9121 的内存使用率持续上升。",
    "correlations": []
  }
}
```

### Step 11：生成最终报告

调用方：公司平台  
被调用方：Python HTTP `/v3/report`

请求：

```json
{
  "inspection_id": "ins-001",
  "format": "html"
}
```

响应：

```json
{
  "ok": true,
  "inspection_id": "ins-001",
  "status": "reported",
  "report": {
    "format": "html",
    "content": "<!doctype html><html lang=\"zh-CN\">...</html>"
  }
}
```

最终平台只需要把 `report.content` 返回给用户、发送邮件，或者写入巡检系统。

## 6. 与 V2 的区别

| 项目 | V2 | V3 |
|---|---|---|
| 查询计划保存 | 平台保存 | Python 服务保存 |
| 查询结果保存 | 平台保存 | Python 服务保存 |
| 后续接口参数 | 需要传 plan/results/analysis | 主要传 inspection_id |
| 意图解析 | skill | prompt |
| Python 服务状态 | 无状态 | 有状态，当前为内存 |

## 7. 平台侧最小编排伪代码

```python
intent = call_llm(prompt_file="prompts_v3/intent_extraction.md", input=user_message)

created = http_post("/v3/inspections", intent)
inspection_id = created["inspection_id"]

http_post("/v3/query", {"inspection_id": inspection_id})
http_post("/v3/analyze", {"inspection_id": inspection_id})

ai_inputs = http_post("/v3/build-ai-series-inputs", {
    "inspection_id": inspection_id,
    "max_points_per_series": 24
})

findings = []
for item in ai_inputs["items"]:
    findings.append(call_llm(prompt_file="prompts_v2/metric_ai_comment.md", input=item))

http_post("/v3/merge-ai-series-findings", {
    "inspection_id": inspection_id,
    "findings": findings
})

inspection = http_get(f"/v3/inspections/{inspection_id}")["inspection"]

ai_correlation = call_llm(
    prompt_file="prompts_v2/correlation_analysis.md",
    input={
        "severity": inspection["analysis"]["severity"],
        "counts": inspection["analysis"]["counts"],
        "risky_items": inspection["analysis"]["risky_items"]
    }
)

http_post("/v3/merge-ai-correlation", {
    "inspection_id": inspection_id,
    "ai_correlation": ai_correlation
})

report = http_post("/v3/report", {
    "inspection_id": inspection_id,
    "format": intent.get("format", "html")
})
```
