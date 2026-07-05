# Prometheus Fixed Inspection Skill

这是一个面向通用 Agent 的 Prometheus 固定巡检 Skill。

它的目标不是做一个“自由问答式 PromQL 助手”，而是把一套固定范围、固定指标、固定 PromQL、固定规则判定、固定 HTML 输出的巡检流程，沉淀成一个可复用的 Skill。

## 这个 Skill 解决什么问题

很多 Agent 在做 Prometheus 巡检时，容易出现下面几种不稳定情况：

- 每次临时决定查哪些指标
- 同一个系统前后使用不同的 PromQL
- 严重等级依赖模型主观判断
- 最终报告结构不稳定，难以做标准化交付

这个 Skill 的设计就是为了解决这些问题。

它强调：

- 巡检范围固定
- 指标目录固定
- PromQL 固定
- 告警级别由规则决定
- 输出为单个固定结构的 HTML 报告

## 适用场景

适合在下面这些场景里使用：

- 用户给出一个 Prometheus 地址，希望生成一份标准巡检报告
- 巡检对象是常见基础组件，而不是完全自定义业务指标
- 希望不同 Agent、多次执行时，输出结果尽量稳定一致
- 希望尽量少依赖 Python 脚本，而是优先用 HTTP API + Skill 指令完成工作

不适合的场景：

- 用户要做自由探索式 PromQL 分析
- 用户想让 Agent 临时发明新的指标或新的判定逻辑
- 用户希望报告格式高度自定义

## Skill 的核心设计

这个 Skill 不是把一整套 Python 服务打包进去，而是把巡检方法拆成了几类清晰的静态资源：

- `SKILL.md`
  作用是定义 Agent 在触发这个 Skill 后应该遵循的总体工作流
- `references/`
  作用是提供固定范围、固定规则、固定指标目录等知识
- `assets/report-template.html`
  作用是提供固定 HTML 报告模板
- `agents/openai.yaml`
  作用是给 Skill 提供界面展示和默认调用提示等元信息

你可以把它理解成：

- `SKILL.md` 是“执行总说明”
- `references/` 是“规则手册和指标手册”
- `assets/` 是“输出模板”
- `openai.yaml` 是“技能名片”

## 支持的巡检对象

当前内置支持 4 类常见 Prometheus Job：

- `node_exporter`
- `java_jmx`
- `redis_exporter`
- `rabbitmq_exporter`

同时支持一些常见别名归一化，例如：

- `node`、`host`、`server` 会归一到 `node_exporter`
- `java`、`jvm`、`spring` 会归一到 `java_jmx`
- `redis` 会归一到 `redis_exporter`
- `mq`、`rabbitmq` 会归一到 `rabbitmq_exporter`

## 工作流程

这个 Skill 的执行流程可以概括为 6 步：

1. 先连接 Prometheus，读取 `/api/v1/label/job/values` 和 `/api/v1/targets`
2. 根据发现到的 job，匹配支持的固定巡检 pack
3. 从对应的 reference 中读取固定指标、固定 PromQL、阈值和分析方法
4. 对每个指标分别执行 instant query 和 range query
5. 按固定规则计算 severity，而不是让模型主观判断
6. 把结果填充进固定 HTML 模板，输出单个报告文件

整个过程中，Agent 应该优先直接调用 Prometheus HTTP API，而不是重建一套本地 Python 巡检引擎。

## 规则设计原则

这个 Skill 的一个关键原则是“规则优先，AI 补充”。

也就是说：

- `critical` / `warning` / `info` / `ok` / `unknown` 必须来自确定性规则
- AI 可以补充总结、解释、备注
- AI 不能决定查什么
- AI 不能修改 severity

这能保证不同 Agent 在相同输入下，尽量得到一致结果。

## 输出结果

默认输出是一个固定结构的 HTML 文件。

报告里应当包含：

- 生成时间
- 总体严重级别
- 巡检 pack 数量
- finding 数量
- 活跃 target 数量
- Prometheus 地址
- 实例过滤条件
- 已发现 job
- 各严重级别统计
- 固定 pack 列表
- findings 明细表
- 可选 warnings
- 可选 AI summary

HTML 模板位于：

- [assets/report-template.html](/D:/Professional/myCode/prometheus-agent/prometheus-fixed-inspection-v8/assets/report-template.html)

详细输出契约位于：

- [references/report-contract.md](/D:/Professional/myCode/prometheus-agent/prometheus-fixed-inspection-v8/references/report-contract.md)

## 目录说明

当前 Skill 目录结构大致如下：

```text
prometheus-fixed-inspection-v8/
├─ SKILL.md
├─ README.md
├─ agents/
│  └─ openai.yaml
├─ assets/
│  └─ report-template.html
└─ references/
   ├─ fixed-scope.md
   ├─ http-workflow.md
   ├─ analysis-rules.md
   ├─ report-contract.md
   ├─ node-exporter.md
   ├─ java-jmx.md
   ├─ redis-exporter.md
   └─ rabbitmq-exporter.md
```

其中每个 reference 的职责是：

- `fixed-scope.md`：定义支持范围、job 别名、pack 默认配置
- `http-workflow.md`：定义如何通过 Prometheus HTTP API 执行查询
- `analysis-rules.md`：定义固定 severity 判定规则
- `report-contract.md`：定义 HTML 报告必须包含什么
- `node-exporter.md` 等：定义每个 job 的固定指标目录与 PromQL

## 怎么使用这个 Skill

一个典型的调用意图可以是：

- “对这个 Prometheus 地址做固定巡检，并生成 HTML 报告”
- “只巡检 Redis 和 RabbitMQ，输出固定格式报告”
- “对某个 instance 做固定巡检，不要自由发挥 PromQL”

默认推荐让 Agent：

- 使用这个 Skill
- 直接访问 Prometheus HTTP API
- 严格按 references 中的固定目录执行
- 只生成一个 HTML 报告

## 和普通 Prometheus Skill 的区别

这个 Skill 和通用 `prometheus` skill 的区别很明确：

- 通用 `prometheus` skill 更像“Prometheus API 工具箱”
- 这个 Skill 更像“固定巡检方案”

前者强调“能查什么就查什么”，后者强调“只查约定好的内容”。

如果用户明确要自由探索指标、尝试不同 PromQL、临时做问题定位，那么应该优先用通用 `prometheus` skill。

如果用户要的是标准化、可复用、可复制的巡检结果，那么应该优先用这个 Skill。

## 后续扩展建议

如果后续要继续增强这个 Skill，建议优先按下面顺序扩展：

1. 增加新的固定 job reference，而不是修改整体工作流
2. 优化某个指标的阈值、PromQL 或 labels，而不是引入自由推理
3. 在确实有必要时，再补一个很薄的辅助脚本用于批量查询或填充 HTML

不建议直接把它重新做回一个重型 Python 服务，因为那会削弱这个 Skill “通用 Agent 可执行、轻脚本依赖”的初衷。

## 相关文件

- 总流程说明见 [SKILL.md](/D:/Professional/myCode/prometheus-agent/prometheus-fixed-inspection-v8/SKILL.md)
- 输出契约见 [report-contract.md](/D:/Professional/myCode/prometheus-agent/prometheus-fixed-inspection-v8/references/report-contract.md)
- Redis 指标目录见 [redis-exporter.md](/D:/Professional/myCode/prometheus-agent/prometheus-fixed-inspection-v8/references/redis-exporter.md)
- RabbitMQ 指标目录见 [rabbitmq-exporter.md](/D:/Professional/myCode/prometheus-agent/prometheus-fixed-inspection-v8/references/rabbitmq-exporter.md)
- Node 指标目录见 [node-exporter.md](/D:/Professional/myCode/prometheus-agent/prometheus-fixed-inspection-v8/references/node-exporter.md)
