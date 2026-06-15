# Prometheus 巡检 Agent V4 设计与接口说明

V4 的目标是兼顾平台编排简单性和 Python 服务内存稳定性。

核心变化：

- Python 服务内部逐指标查询 Prometheus。
- 完整 raw 采样数据写入 JSON 文件。
- 内存中只短暂保留单个查询结果，随后释放。
- Python 生成 compact 文件：统计摘要 + 抽样点。
- AI 输入按 `job + instance` 分批生成，不直接给 AI 完整 raw 数据。
- 平台只传 `inspection_id` 和 `batch_id`，不传大段采样数据。

V4 新代码：

```text
prometheus_agent_v4/
prompts_v4/
READ_V4.md
```

运行数据默认写入：

```text
data_v4/inspections/{inspection_id}/
```

该目录已加入 `.gitignore`。

## 1. 启动服务

```powershell
python -m prometheus_agent_v4 --host 127.0.0.1 --port 8030
```

指定数据目录：

```powershell
python -m prometheus_agent_v4 --host 127.0.0.1 --port 8030 --data-dir D:\prometheus-agent-data
```

## 2. 文件结构

一次巡检的文件结构：

```text
data_v4/inspections/{inspection_id}/
  meta.json
  plan.json
  plain_plan.json
  raw/
    redis/
      redis_memory_usage.json
  compact/
    redis/
      10.0.0.12_9121/
        redis_memory_usage.json
      index.jsonl
  analysis/
    analysis.json
    redis/
      10.0.0.12_9121/
        redis_memory_usage.json
  ai_input/
    redis__10.0.0.12_9121.json
    final_correlation.json
  ai_output/
    redis__10.0.0.12_9121.json
    final_correlation.json
  report/
    report.html
```

说明：

- `raw/` 保存完整 Prometheus 查询结果。
- `compact/` 保存压缩摘要和抽样点。
- `analysis/` 保存 Python 固定规则分析结果。
- `ai_input/` 保存发给 AI 的 job+instance 批次输入。
- `ai_output/` 保存 AI 返回结果。
- `report/` 保存最终报告。

## 3. 推荐调用链路

```text
用户输入
  -> AI 使用 prompts_v4/intent_extraction.md 解析意图
  -> POST /v4/inspections 创建巡检和 plan
  -> POST /v4/query-and-compact 查询 Prometheus，写 raw 和 compact 文件
  -> POST /v4/analyze 读取 compact 文件做 Python 分析
  -> POST /v4/build-ai-batches 按 job+instance 生成 AI batch 文件
  -> 平台通过 POST /v4/next-ai-batch 或 POST /v4/get-ai-batch 获取 batch 内容
  -> 平台逐个 batch 调用 AI，使用 prompts_v4/batch_analysis.md
  -> POST /v4/merge-ai-batch-findings 保存每个 batch 的 AI 输出
  -> POST /v4/build-final-correlation-input 生成最终关联分析输入
  -> 平台调用 AI，使用 prompts_v4/final_correlation.md
  -> POST /v4/merge-final-correlation 保存最终关联分析
  -> POST /v4/report 生成报告
```

## 4. 关键接口

### 4.1 创建巡检

```text
POST /v4/inspections
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

响应：

```json
{
  "ok": true,
  "inspection_id": "uuid",
  "status": "planned",
  "plan_summary": {
    "task_count": 4
  },
  "base_path": "data_v4/inspections/uuid"
}
```

### 4.2 查询并压缩

```text
POST /v4/query-and-compact
```

请求：

```json
{
  "inspection_id": "uuid",
  "timeout_seconds": 20,
  "max_points_per_series": 60
}
```

响应：

```json
{
  "ok": true,
  "inspection_id": "uuid",
  "status": "compacted",
  "query_summary": {
    "task_count": 4,
    "series_count": 8,
    "failed_count": 0,
    "raw_files": [],
    "compact_files": []
  }
}
```

该步骤会：

- 逐 task 查询 Prometheus。
- 把完整结果写入 `raw/`。
- 把摘要和抽样点写入 `compact/`。
- 不在内存中保留所有 raw points。

### 4.3 Python 分析

```text
POST /v4/analyze
```

请求：

```json
{
  "inspection_id": "uuid"
}
```

响应：

```json
{
  "ok": true,
  "inspection_id": "uuid",
  "status": "analyzed",
  "analysis_summary": {
    "severity": "warning",
    "counts": {},
    "risky_count": 3
  }
}
```

### 4.4 构建 AI 批次

```text
POST /v4/build-ai-batches
```

请求：

```json
{
  "inspection_id": "uuid",
  "risky_only": false
}
```

响应：

```json
{
  "ok": true,
  "inspection_id": "uuid",
  "status": "ai_batches_built",
  "batches": [
    {
      "batch_id": "redis__10.0.0.12_9121",
      "job": "redis",
      "instance": "10.0.0.12:9121",
      "item_count": 4,
      "path": "data_v4/inspections/uuid/ai_input/redis__10.0.0.12_9121.json"
    }
  ],
  "batch_progress": {
    "total": 1,
    "completed": 0,
    "remaining": 1,
    "done": false
  }
}
```

`path` 是服务端本地文件路径，主要用于排查和审计。平台不需要直接读取该文件，而是通过下面的 HTTP 接口获取 batch 内容。

### 4.5 查询 AI 批次列表

```text
POST /v4/list-ai-batches
```

请求：

```json
{
  "inspection_id": "uuid",
  "include_content": false
}
```

响应：

```json
{
  "ok": true,
  "inspection_id": "uuid",
  "batches": [
    {
      "batch_id": "redis__10.0.0.12_9121",
      "job": "redis",
      "instance": "10.0.0.12:9121",
      "item_count": 4,
      "path": "data_v4/inspections/uuid/ai_input/redis__10.0.0.12_9121.json",
      "completed": false,
      "output_path": null
    }
  ],
  "batch_progress": {
    "total": 1,
    "completed": 0,
    "remaining": 1,
    "done": false
  }
}
```

如果平台想一次拿到所有 batch 内容，可以传 `"include_content": true`。如果 batch 很多，推荐不要这样做，改用下一个接口逐个拉取。

### 4.6 获取指定 AI 批次

```text
POST /v4/get-ai-batch
```

请求：

```json
{
  "inspection_id": "uuid",
  "batch_id": "redis__10.0.0.12_9121"
}
```

响应：

```json
{
  "ok": true,
  "inspection_id": "uuid",
  "batch_id": "redis__10.0.0.12_9121",
  "completed": false,
  "batch": {
    "inspection_id": "uuid",
    "batch_id": "redis__10.0.0.12_9121",
    "job": "redis",
    "instance": "10.0.0.12:9121",
    "item_count": 4,
    "items": []
  }
}
```

平台把 `batch` 字段作为 AI 输入，配合 `prompts_v4/batch_analysis.md` 调用大模型。

### 4.7 获取下一个未分析 AI 批次

```text
POST /v4/next-ai-batch
```

请求：

```json
{
  "inspection_id": "uuid"
}
```

响应：

```json
{
  "ok": true,
  "inspection_id": "uuid",
  "done": false,
  "batch_progress": {
    "total": 3,
    "completed": 1,
    "remaining": 2,
    "done": false
  },
  "batch": {
    "batch_id": "redis__10.0.0.12_9121",
    "job": "redis",
    "instance": "10.0.0.12:9121",
    "items": []
  }
}
```

当所有 batch 都已经通过 `/v4/merge-ai-batch-findings` 保存 AI 结果后，响应会变成：

```json
{
  "ok": true,
  "inspection_id": "uuid",
  "done": true,
  "batch_progress": {
    "total": 3,
    "completed": 3,
    "remaining": 0,
    "done": true
  },
  "batch": null
}
```

这是平台循环编排最推荐使用的接口。平台每次取一个未完成 batch，调用 AI，保存 AI 结果，然后继续取下一个，直到 `done=true`。

### 4.8 合并批次 AI 输出

```text
POST /v4/merge-ai-batch-findings
```

请求：

```json
{
  "inspection_id": "uuid",
  "batch_id": "redis__10.0.0.12_9121",
  "finding": {
    "summary": "该 Redis 实例主要风险是内存持续升高。",
    "findings": [
      {
        "level": "warning",
        "metrics": ["redis_memory_usage"],
        "reason": "内存使用率持续增长。",
        "suggestion": "检查 key 增长和 maxmemory 配置。"
      }
    ]
  }
}
```

响应：

```json
{
  "ok": true,
  "inspection_id": "uuid",
  "status": "ai_batch_findings_merged",
  "path": "data_v4/inspections/uuid/ai_output/redis__10.0.0.12_9121.json",
  "batch_progress": {
    "total": 3,
    "completed": 2,
    "remaining": 1,
    "done": false
  }
}
```

### 4.9 构建最终关联分析输入

```text
POST /v4/build-final-correlation-input
```

请求：

```json
{
  "inspection_id": "uuid"
}
```

响应包含 `input`，也会写入：

```text
ai_input/final_correlation.json
```

### 4.10 合并最终关联分析

```text
POST /v4/merge-final-correlation
```

请求：

```json
{
  "inspection_id": "uuid",
  "ai_correlation": {
    "summary": "整体风险摘要",
    "correlations": []
  }
}
```

### 4.11 生成报告

```text
POST /v4/report
```

请求：

```json
{
  "inspection_id": "uuid",
  "format": "html",
  "include_content": true
}
```

响应：

```json
{
  "ok": true,
  "inspection_id": "uuid",
  "status": "reported",
  "report": {
    "format": "html",
    "path": "data_v4/inspections/uuid/report/report.html",
    "content": "<!doctype html>..."
  }
}
```

## 5. 完整调用示例

下面用一次 Redis 巡检说明完整调用链路。示例中的 `inspection_id` 使用 `ins-001` 表示；真实接口会返回 UUID。

### Step 0：用户输入

```text
请帮我巡检 http://127.0.0.1:9090 上 redis 最近 24 小时是否异常
```

### Step 1：AI 意图解析

调用方：公司平台  
被调用方：AI + `prompts_v4/intent_extraction.md`

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
  "need_ai_batch_analysis": true,
  "need_final_correlation": true
}
```

### Step 2：创建巡检

调用方：公司平台  
被调用方：Python HTTP `/v4/inspections`

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
  },
  "base_path": "data_v4/inspections/ins-001"
}
```

服务端生成：

```text
data_v4/inspections/ins-001/
  meta.json
  plan.json
  plain_plan.json
```

平台后续只需要保存：

```json
{
  "inspection_id": "ins-001"
}
```

### Step 3：查询并压缩

调用方：公司平台  
被调用方：Python HTTP `/v4/query-and-compact`

请求：

```json
{
  "inspection_id": "ins-001",
  "timeout_seconds": 20,
  "max_points_per_series": 60
}
```

响应：

```json
{
  "ok": true,
  "inspection_id": "ins-001",
  "status": "compacted",
  "query_summary": {
    "task_count": 4,
    "series_count": 4,
    "failed_count": 0,
    "raw_files": [
      "data_v4/inspections/ins-001/raw/redis/redis_memory_usage.json"
    ],
    "compact_files": [
      "data_v4/inspections/ins-001/compact/redis/10.0.0.12_9121/redis_memory_usage.json"
    ]
  }
}
```

raw 文件示例：

```json
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
```

compact 文件示例：

```json
{
  "job": "redis",
  "instance": "10.0.0.12:9121",
  "metric_id": "redis_memory_usage",
  "metric_name": "Redis Memory Usage",
  "raw_point_count": 1440,
  "current": 82.4,
  "summary": {
    "point_count": 1440,
    "first": 61.2,
    "last": 82.4,
    "min": 61.2,
    "max": 82.4,
    "avg": 73.2,
    "p95": 81.74,
    "slope_per_hour": 0.88
  },
  "sampled_points": [
    {"timestamp": "2026-06-13T00:00:00Z", "value": 61.2},
    {"timestamp": "2026-06-13T06:00:00Z", "value": 68.5},
    {"timestamp": "2026-06-13T12:00:00Z", "value": 74.8},
    {"timestamp": "2026-06-13T18:00:00Z", "value": 79.1},
    {"timestamp": "2026-06-14T00:00:00Z", "value": 82.4}
  ]
}
```

说明：

- raw 文件保留完整采样点，用于审计和复查。
- compact 文件只保留摘要和抽样点，用于 Python 分析和 AI 输入。
- Python 不把所有 raw points 长期放在内存中。

### Step 4：Python 固定规则分析

调用方：公司平台  
被调用方：Python HTTP `/v4/analyze`

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

服务端生成：

```text
analysis/analysis.json
analysis/redis/10.0.0.12_9121/redis_memory_usage.json
```

单指标分析文件示例：

```json
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
```

### Step 5：构建 AI 批次

调用方：公司平台  
被调用方：Python HTTP `/v4/build-ai-batches`

请求：

```json
{
  "inspection_id": "ins-001",
  "risky_only": false
}
```

响应：

```json
{
  "ok": true,
  "inspection_id": "ins-001",
  "status": "ai_batches_built",
  "batches": [
    {
      "batch_id": "redis__10.0.0.12_9121",
      "job": "redis",
      "instance": "10.0.0.12:9121",
      "item_count": 4,
      "path": "data_v4/inspections/ins-001/ai_input/redis__10.0.0.12_9121.json"
    }
  ],
  "batch_progress": {
    "total": 1,
    "completed": 0,
    "remaining": 1,
    "done": false
  }
}
```

`path` 是 Python 服务本地文件路径，平台不直接读取它。平台可以先查询批次列表，确认总数和完成进度：

```json
{
  "inspection_id": "ins-001",
  "include_content": false
}
```

调用 `POST /v4/list-ai-batches` 的响应：

```json
{
  "ok": true,
  "inspection_id": "ins-001",
  "batches": [
    {
      "batch_id": "redis__10.0.0.12_9121",
      "job": "redis",
      "instance": "10.0.0.12:9121",
      "item_count": 4,
      "completed": false
    }
  ],
  "batch_progress": {
    "total": 1,
    "completed": 0,
    "remaining": 1,
    "done": false
  }
}
```

然后平台通过 `POST /v4/next-ai-batch` 获取下一个未完成批次：

```json
{
  "inspection_id": "ins-001"
}
```

响应中的 `batch` 就是要传给 AI 的输入：

```json
{
  "ok": true,
  "inspection_id": "ins-001",
  "done": false,
  "batch_progress": {
    "total": 1,
    "completed": 0,
    "remaining": 1,
    "done": false
  },
  "batch": {
    "inspection_id": "ins-001",
    "batch_id": "redis__10.0.0.12_9121",
    "job": "redis",
    "instance": "10.0.0.12:9121",
    "item_count": 4,
    "items": []
  }
}
```

AI batch 内容示例：

```json
{
  "inspection_id": "ins-001",
  "batch_id": "redis__10.0.0.12_9121",
  "job": "redis",
  "instance": "10.0.0.12:9121",
  "item_count": 4,
  "items": [
    {
      "metric_id": "redis_memory_usage",
      "metric_name": "Redis Memory Usage",
      "python_severity": "warning",
      "python_reason": "Current value is already warning. Series is continuously growing without clear slowdown.",
      "summary": {
        "current": 82.4,
        "avg": 73.2,
        "p95": 81.74,
        "slope_per_hour": 0.88
      },
      "sampled_points": [
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

平台把 `/v4/next-ai-batch` 或 `/v4/get-ai-batch` 返回的 `batch` 字段交给 AI，使用：

```text
prompts_v4/batch_analysis.md
```

### Step 6：AI 批次分析

调用方：公司平台  
被调用方：AI + `prompts_v4/batch_analysis.md`

输入：`/v4/next-ai-batch` 或 `/v4/get-ai-batch` 返回的 `batch` JSON。

AI 输出：

```json
{
  "batch_id": "redis__10.0.0.12_9121",
  "job": "redis",
  "instance": "10.0.0.12:9121",
  "summary": "该 Redis 实例主要风险是内存使用率持续升高。",
  "findings": [
    {
      "level": "warning",
      "metrics": ["redis_memory_usage"],
      "reason": "内存使用率已超过 warning，且采样点持续抬升。",
      "suggestion": "检查 key 增长、大 key、过期策略和 maxmemory 配置。"
    }
  ]
}
```

### Step 7：合并批次 AI 输出

调用方：公司平台  
被调用方：Python HTTP `/v4/merge-ai-batch-findings`

请求：

```json
{
  "inspection_id": "ins-001",
  "batch_id": "redis__10.0.0.12_9121",
  "finding": {
    "batch_id": "redis__10.0.0.12_9121",
    "job": "redis",
    "instance": "10.0.0.12:9121",
    "summary": "该 Redis 实例主要风险是内存使用率持续升高。",
    "findings": [
      {
        "level": "warning",
        "metrics": ["redis_memory_usage"],
        "reason": "内存使用率已超过 warning，且采样点持续抬升。",
        "suggestion": "检查 key 增长、大 key、过期策略和 maxmemory 配置。"
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
  "status": "ai_batch_findings_merged",
  "path": "data_v4/inspections/ins-001/ai_output/redis__10.0.0.12_9121.json",
  "batch_progress": {
    "total": 1,
    "completed": 1,
    "remaining": 0,
    "done": true
  }
}
```

### Step 8：构建最终关联分析输入

调用方：公司平台  
被调用方：Python HTTP `/v4/build-final-correlation-input`

请求：

```json
{
  "inspection_id": "ins-001"
}
```

响应节选：

```json
{
  "ok": true,
  "inspection_id": "ins-001",
  "path": "data_v4/inspections/ins-001/ai_input/final_correlation.json",
  "input": {
    "severity": "warning",
    "counts": {
      "critical": 0,
      "warning": 1,
      "info": 0,
      "ok": 3,
      "unknown": 0
    },
    "risky_items": [],
    "batch_findings": [
      {
        "batch_id": "redis__10.0.0.12_9121",
        "finding": {
          "summary": "该 Redis 实例主要风险是内存使用率持续升高。"
        }
      }
    ]
  }
}
```

平台把 `input` 或 `path` 对应文件发给 AI，使用：

```text
prompts_v4/final_correlation.md
```

### Step 9：AI 最终关联分析

调用方：公司平台  
被调用方：AI + `prompts_v4/final_correlation.md`

AI 输出：

```json
{
  "summary": "当前主要风险集中在 Redis 实例 10.0.0.12:9121 的内存持续增长。",
  "correlations": [
    {
      "level": "warning",
      "jobs": ["redis"],
      "instances": ["10.0.0.12:9121"],
      "reason": "Redis 内存使用率持续增长，存在容量压力。",
      "suggestion": "优先检查 key 增长、大 key、过期策略和 maxmemory 配置。"
    }
  ]
}
```

### Step 10：合并最终关联分析

调用方：公司平台  
被调用方：Python HTTP `/v4/merge-final-correlation`

请求：

```json
{
  "inspection_id": "ins-001",
  "ai_correlation": {
    "summary": "当前主要风险集中在 Redis 实例 10.0.0.12:9121 的内存持续增长。",
    "correlations": [
      {
        "level": "warning",
        "jobs": ["redis"],
        "instances": ["10.0.0.12:9121"],
        "reason": "Redis 内存使用率持续增长，存在容量压力。",
        "suggestion": "优先检查 key 增长、大 key、过期策略和 maxmemory 配置。"
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
  "status": "final_correlation_merged",
  "path": "data_v4/inspections/ins-001/ai_output/final_correlation.json"
}
```

### Step 11：生成报告

调用方：公司平台  
被调用方：Python HTTP `/v4/report`

请求：

```json
{
  "inspection_id": "ins-001",
  "format": "html",
  "include_content": true
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
    "path": "data_v4/inspections/ins-001/report/report.html",
    "content": "<!doctype html><html lang=\"zh-CN\">...</html>"
  }
}
```

最终平台可以把 `report.content` 直接展示给用户，也可以只保存 `report.path`。

## 6. 平台侧最小编排

```python
intent = call_llm(prompt_file="prompts_v4/intent_extraction.md", input=user_message)

created = http_post("/v4/inspections", intent)
inspection_id = created["inspection_id"]

http_post("/v4/query-and-compact", {
    "inspection_id": inspection_id,
    "max_points_per_series": 60
})

http_post("/v4/analyze", {"inspection_id": inspection_id})

batch_payload = http_post("/v4/build-ai-batches", {
    "inspection_id": inspection_id,
    "risky_only": false
})

while True:
    next_batch = http_post("/v4/next-ai-batch", {
        "inspection_id": inspection_id
    })
    if next_batch["done"]:
        break

    batch = next_batch["batch"]
    finding = call_llm(prompt_file="prompts_v4/batch_analysis.md", input=batch)
    http_post("/v4/merge-ai-batch-findings", {
        "inspection_id": inspection_id,
        "batch_id": batch["batch_id"],
        "finding": finding
    })

correlation_input = http_post("/v4/build-final-correlation-input", {
    "inspection_id": inspection_id
})["input"]

ai_correlation = call_llm(prompt_file="prompts_v4/final_correlation.md", input=correlation_input)

http_post("/v4/merge-final-correlation", {
    "inspection_id": inspection_id,
    "ai_correlation": ai_correlation
})

report = http_post("/v4/report", {
    "inspection_id": inspection_id,
    "format": "html"
})
```

## 7. 设计取舍

V4 推荐用于数据量较大的巡检：

- 平台配置简单。
- Python 内部逐指标处理。
- raw 数据可审计。
- AI 输入按 job+instance 分批，避免一次性塞给模型过多数据。
- 内存压力比 V3 小。

代价：

- 需要管理 `data_v4/` 目录。
- 需要定期清理历史巡检文件。
- 如果多实例部署，需要共享文件系统或改成对象存储/数据库。
