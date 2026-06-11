# Prometheus Agent 工具与 Skill 串联说明

本文说明当前项目里的 Python 工具、skills、AI 大模型如何分工，以及在公司 AI 平台里如何串联。

## 1. 分工原则

稳定巡检的核心原则：

- Python 工具负责查询、计算、分级、渲染。
- Skills 负责 PromQL 范式、指标领域知识、巡检流程约束。
- AI 大模型负责理解用户问题、选择巡检域、生成解释和建议。

不要让大模型直接判断严重级别、编造阈值、访问任意 URL 或自由生成 HTML 主体。

## 2. 已实现的 Python 工具

平台可以直接封装 `prometheus_agent.platform_tools` 中的函数。

| 工具函数 | 作用 |
|---|---|
| `list_targets_tool` | 列出已配置的 Prometheus 目标 |
| `target_resolver_tool` | 把用户输入的目标提示解析为允许访问的 Prometheus 配置 |
| `list_metric_domains_tool` | 列出已有指标域，例如 `host`、`redis`、`jvm`、`rabbitmq` |
| `metric_catalog_tool` | 读取某个指标域的核心巡检指标 |
| `build_inspection_plan_tool` | 根据目标、领域、时间范围生成巡检计划 |
| `validate_inspection_plan_tool` | 校验巡检计划是否安全、完整 |
| `grafana_threshold_tool` | 从 Grafana alert rule 尝试提取阈值 |
| `run_inspection_plan_tool` | 执行巡检计划，查询 Prometheus、分析指标、生成报告 |

示例 import：

```python
from prometheus_agent.platform_tools import (
    build_inspection_plan_tool,
    run_inspection_plan_tool,
)
```

## 3. 已实现的 Skills

| Skill | 路径 | 用途 |
|---|---|---|
| `promql-authoring` | `skills/promql-authoring` | PromQL 生成规则和常用样例 |
| `metric-domain-knowledge` | `skills/metric-domain-knowledge` | Host、JVM、Redis、RabbitMQ、业务指标核心巡检项 |
| `inspection-workflow` | `skills/inspection-workflow` | 交互式和定时巡检流程、InspectionPlan 结构、安全约束 |

建议在 AI 平台中把这三个目录配置为 Agent 可用的知识/skill 资源。

## 4. 配置文件

### Prometheus 目标

示例文件：

```text
configs/targets.example.json
```

用于配置允许访问的 Prometheus、Grafana、认证、默认查询范围和各 domain 的 job pattern。

生产环境建议复制为：

```text
configs/targets.prod.json
```

认证信息不要直接写密码，建议使用环境变量引用：

```json
{
  "auth": {
    "type": "bearer",
    "token_env": "PROD_PROMETHEUS_TOKEN"
  }
}
```

### 指标目录

示例目录：

```text
configs/metric_catalog/
```

已包含：

- `host.json`
- `redis.json`
- `jvm.json`
- `rabbitmq.json`

自动巡检应优先使用这些审核过的指标目录，不建议让 AI 每次临时生成 PromQL。

## 5. 交互式巡检串联

用户问题示例：

```text
请帮我查询下 127.0.0.1 那台 Prometheus 上 Redis 指标是否有异常
```

推荐流程：

```text
1. AI 读取 inspection-workflow skill
2. AI 解析用户意图：
   target_hint = "127.0.0.1"
   domain = "redis"
   mode = "interactive"
3. 调用 build_inspection_plan_tool
4. 如计划不完整或目标歧义，AI 追问用户
5. 调用 run_inspection_plan_tool
6. AI 基于工具返回的结构化结果生成原因分析和建议
7. 返回 HTML 报告路径或表格摘要
```

Python 示例：

```python
from prometheus_agent.platform_tools import build_inspection_plan_tool, run_inspection_plan_tool

plan_payload = build_inspection_plan_tool(
    target_hint="127.0.0.1",
    domain="redis",
    range_hours=24,
    step_seconds=60,
    forecast_hours=24,
)

if not plan_payload["ok"]:
    print(plan_payload)
else:
    payload = run_inspection_plan_tool(
        plan_payload["plan"],
        output_path="redis_report.html",
        use_grafana_thresholds=True,
    )
    print(payload["report_path"])
```

## 6. 定时自动巡检串联

定时巡检应尽量少依赖大模型。

推荐流程：

```text
1. 定时任务触发
2. 平台读取固定 targets 和 metric catalog
3. 对每个 target/domain 调用 build_inspection_plan_tool
4. 调用 run_inspection_plan_tool
5. 生成 HTML 报告
6. AI 只基于结构化结果生成摘要和运维建议
7. 发送报告或写入巡检系统
```

定时巡检中不要让 AI 临时决定查询哪些 PromQL，除非该 profile 明确允许。

## 7. InspectionPlan 边界

`InspectionPlan` 是 AI 和工具之间的边界。AI 可以帮助生成计划，但工具必须校验计划。

核心结构：

```json
{
  "mode": "interactive",
  "target": {
    "id": "local-dev",
    "base_url": "http://127.0.0.1:9090",
    "headers": {}
  },
  "scope": {
    "domain": "redis",
    "instance_hint": null,
    "job_patterns": ["redis", "redis-exporter"]
  },
  "time": {
    "current_window": "5m",
    "range_hours": 24,
    "step_seconds": 60,
    "forecast_hours": 24
  },
  "items": [
    {
      "id": "redis_memory_usage",
      "name": "Redis Memory Usage",
      "current_promql": "redis_memory_used_bytes / redis_memory_max_bytes * 100",
      "range_promql": "redis_memory_used_bytes / redis_memory_max_bytes * 100",
      "value_type": "percent",
      "unit": "%",
      "analysis_type": "growth_to_limit",
      "direction": "higher_is_bad",
      "warning": 75,
      "critical": 90
    }
  ]
}
```

## 8. 阈值优先级

建议按以下优先级取阈值：

```text
Grafana alert rule > 指标目录 catalog 默认阈值 > 用户显式输入 > 无阈值
```

当前 `run_inspection_plan_tool(..., use_grafana_thresholds=True)` 会尝试读取 Grafana alert rule。读取失败不会中断巡检，会继续使用指标目录里的默认阈值。

## 9. AI 输出建议

AI 生成原因和建议时，只使用工具返回的 evidence，例如：

- severity
- current
- forecast
- slope_per_hour
- time_to_warning_hours
- time_to_critical_hours
- threshold_source
- affected labels
- query error

不要让 AI 编造未查询到的数据。

推荐输出：

```text
Redis Memory Usage 被标记为 warning。
当前值 78.3%，按过去 24 小时趋势预测，约 10.5 小时后可能接近 critical 阈值 90%。
建议优先检查实例 xxx 的 key 增长、过期策略和 maxmemory 配置。
```

## 10. 后续扩展

下一步建议扩展：

- `target_resolver` 接公司 CMDB 或服务目录。
- `metric_catalog` 增加业务指标 profile。
- `analysis.py` 拆成多分析器：`growth_to_limit`、`burst_detection`、`queue_backlog`、`seasonal_baseline`。
- `grafana.py` 增强 dashboard panel threshold 解析。
- 报告模板按 Host、Redis、JVM、RabbitMQ、Business 分区展示。
