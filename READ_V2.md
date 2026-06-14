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
| 单指标简评 | AI 大模型 + `prompts_v2/metric_ai_comment.md` | 基于单条分析结果，输出不超过 100 字 |
| 多指标关联分析 | AI 大模型 + `prompts_v2/correlation_analysis.md` | 基于全部异常项做关联分析 |
| 报告生成 | Python HTTP `/v2/report` | 生成 Markdown 或 HTML |

原则：Python 给出确定性 severity，AI 只解释和关联，不直接改 severity。

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
  -> AI 对每条分析结果生成 <=100 字简评
  -> HTTP POST /v2/merge-ai-comments 合并 AI 简评
  -> AI 对异常项做关联性分析
  -> HTTP POST /v2/report 生成 md/html
```

如果不需要 AI 简评和关联分析，可以直接调用：

```text
POST /v2/run
```

它会执行 plan -> query -> analyze -> report，但不会调用大模型。

### 3.1 完整 AI 编排调用链路

下面是推荐的完整链路，适合用户通过聊天框发起巡检，并希望 AI 给出单指标简评和多指标关联分析的场景。

| 步骤 | 调用方 | 被调用方 | 输入 | 输出 | 下一步 |
|---|---|---|---|---|---|
| 1 | 公司平台 | AI + `skills_v2/intent-extraction` | 用户原始问题 | `prometheus_url`、`job`、`instance`、时间范围 | 调 `/v2/plan` |
| 2 | 公司平台 | Python HTTP `/v2/plan` | Step1 的结构化意图 | `plan`，其中包含每个 job/instance/metric 的 PromQL 查询任务 | 调 `/v2/query` |
| 3 | 公司平台 | Python HTTP `/v2/query` | `plan` | `results`，每个 task 包含 current 查询结果、range 查询结果、errors | 调 `/v2/analyze` |
| 4 | 公司平台 | Python HTTP `/v2/analyze` | Step3 的 `results` | `analysis`，包含 severity、counts、items、risky_items | 调 AI 做单指标简评 |
| 5 | 公司平台 | AI + `prompts_v2/metric_ai_comment.md` | `analysis.items` 中的单条指标分析结果 | 每条指标的简短 `comment` | 调 `/v2/merge-ai-comments` |
| 6 | 公司平台 | Python HTTP `/v2/merge-ai-comments` | `analysis` + AI comments | 合并了 `ai_comment` 的 `analysis` | 调 AI 做关联分析 |
| 7 | 公司平台 | AI + `prompts_v2/correlation_analysis.md` | `analysis.risky_items`、`counts`、总体 severity | `ai_correlation` JSON | 调 `/v2/report` |
| 8 | 公司平台 | Python HTTP `/v2/report` | `analysis` + `ai_correlation` + `format` | Markdown 或 HTML 报告内容 | 返回给用户或落库 |

这条链路里，严重级别由 `/v2/analyze` 给出，AI 只负责解释，不修改 severity。

### 3.2 数据在各步骤中的流转

核心数据对象按下面顺序流动：

```text
用户问题
  -> Intent JSON
  -> Inspection Plan
  -> Query Results
  -> Deterministic Analysis
  -> AI Metric Comments
  -> AI Correlation
  -> Report
```

其中：

- `Intent JSON`：AI 从用户问题中抽取出来的结构化意图。
- `Inspection Plan`：`/v2/plan` 生成，包含所有要执行的 PromQL。
- `Query Results`：`/v2/query` 生成，逐条记录每个指标的查询结果。
- `Deterministic Analysis`：`/v2/analyze` 生成，包含固定规则分析和风险分级。
- `AI Metric Comments`：AI 对单条指标结果的简短解释。
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

# Step 5: AI 单指标简评
comments = []
for item in analysis["items"]:
    comment = call_llm(
        prompt_file="prompts_v2/metric_ai_comment.md",
        input=item,
    )
    comments.append({
        "job": item["job"],
        "instance": item["instance"],
        "metric_id": item["metric_id"],
        "comment": comment,
    })

# Step 6: 合并 AI 简评
merged = http_post("http://127.0.0.1:8010/v2/merge-ai-comments", {
    "analysis": analysis,
    "comments": comments,
})

# Step 7: AI 关联性分析
ai_correlation = call_llm(
    prompt_file="prompts_v2/correlation_analysis.md",
    input={
        "severity": merged["analysis"]["severity"],
        "counts": merged["analysis"]["counts"],
        "risky_items": merged["analysis"]["risky_items"],
    },
)

# Step 8: 生成报告
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

- 单指标 AI 简评
- 多指标 AI 关联分析
- AI 生成运维建议

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

### 4.5 合并 AI 单指标简评

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

### 4.6 生成报告

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

### 4.7 无 AI 端到端执行

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

### Step 5 单指标简评

使用：

```text
prompts_v2/metric_ai_comment.md
```

建议只对 `analysis.items` 或 `analysis.risky_items` 逐条调用 AI。

### Step 6 关联性分析

使用：

```text
prompts_v2/correlation_analysis.md
```

输入建议只给：

- `analysis.risky_items`
- `analysis.counts`
- `analysis.severity`

避免把完整采样数据都给 AI，降低 token 和泄露风险。

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
