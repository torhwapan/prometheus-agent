# Prometheus Agent 阶段汇报

## 1. 当前结论

目前这套方案已经形成两条可用能力线：

1. `V4 巡检链路`
   - 通过公司平台工作流 + Python HTTP 服务 + AI 大模型，完成定时巡检、固定策略分析、AI 补充分析、HTML 报告输出。
   - 适合日常巡检、风险预警、汇报输出。

2. `Prometheus Skill 问询链路`
   - 通过公司平台挂载 Prometheus skill，完成自然语言临时问询。
   - 适合值班排查、临时问诊、按需查询。

当前建议不是让一个能力替代另一个能力，而是形成：

- `V4` 负责“固定流程巡检”
- `Prometheus skill` 负责“临时自然语言问诊”

两者组合后，基本覆盖“日常巡检 + 临时排障”两个高频场景。

---

## 2. 已完成能力

### 2.1 V4 巡检能力

目前已跑通的巡检链路如下：

1. 用户或定时任务触发巡检
2. 平台调用 AI 做意图解析
3. Python 服务创建巡检计划
4. Python 服务调用 Prometheus API 查询指标
5. Python 服务做固定策略分析
6. 平台按 batch 调用 AI 做单批次补充分析
7. 平台调用 AI 做最终关联分析
8. Python 服务输出 HTML 报告

当前这条链路已经可以支持：

- 按 `job / instance / metric` 组织巡检
- 查询最近 5 分钟当前状态
- 查询最近 24 小时或数小时的范围数据
- 对指标做突增、持续增长、趋势预测等分析
- 输出较完整的巡检报告

### 2.2 临时问询能力

目前通过外部 `prometheus` skill，已经可以较稳定支持：

- 查询某个 Prometheus 上有哪些 job
- 查询某类 job 的真实指标
- 查询 targets / alerts / metadata
- 执行 PromQL 即时查询、范围查询
- 针对 redis、rabbitmq、node、jvm 做基础问询

适合的问法例如：

- `帮我看下 10.22.23.24 上的 redis 有没有异常`
- `最近 24 小时 rabbitmq 哪些队列消费能力不足`
- `帮我查询下内存使用率超过 70% 的服务器`

---

## 3. 为什么外部 Prometheus Skill 比 V5 效果更好

这次验证下来，外部 `prometheus` skill 效果更好，不是偶然，主要有 6 个原因。

### 3.1 定位更接近真实问询场景

我们自己的 `V5` 本质上是“固定语义映射”：

- 先识别问题类型
- 再映射成固定 `semantic_key`
- 最后调用固定 HTTP 接口

它更像一个“半结构化问询代理”。

而外部 `prometheus` skill 的定位更接近“Prometheus 通用操作手册 + 工具集”，它允许模型直接围绕 Prometheus 原生概念思考：

- query
- query_range
- series
- labels
- metadata
- targets
- alerts
- rules
- TSDB

这更符合用户临时问诊时的问题形态，因此泛化能力明显更强。

### 3.2 Prometheus 原生知识覆盖更完整

外部 skill 不只是一个说明文件，它把 Prometheus 常用知识补得比较完整，包括：

- HTTP API 主要端点
- PromQL 常见模式
- 返回结果结构
- 常见错误码
- metadata / discovery / health / rules / alerts 等接口
- 一些 Prometheus 使用陷阱和 gotchas

相比之下，V5 只覆盖了少量固定语义：

- `redis-health`
- `jvm-memory-risk`
- `rabbitmq-consumer-capacity`
- `node-memory-usage`
- `node-cpu-top`

这意味着：

- 只要用户问题稍微偏离预设范畴，V5 就容易失配
- 外部 skill 则还能继续落回到原生 API 查询

### 3.3 外部 skill 有更强的“发现能力”

Prometheus 的一个关键特点是：真实环境里的指标名、label、job、instance，往往和文档、预期并不完全一致。

外部 skill 提供了很强的 discovery 能力，例如：

- 查 job 列表
- 查 label 名称
- 查 label 值
- 查 series
- 查 metadata
- 查 scrape targets

这样模型在回答前，先有能力“看清现场”。

而 V5 更依赖我们事先整理好的 catalog 和固定语义映射，一旦 catalog 不完整，或者现场指标和预期不一致，回答效果就会下降。

### 3.4 对弱模型更友好

你前面已经验证过，你们公司平台上的模型能力偏弱。

在这种前提下，外部 skill 更占优，因为它把很多关键知识显式写出来了：

- 接口怎么调
- 参数怎么传
- 结果长什么样
- 常见 PromQL 怎么写

也就是说，它把“模型需要自己推理出来的东西”压缩掉了很多。

V5 则要求模型同时完成：

1. 理解用户意图
2. 识别 Prometheus 地址
3. 选择语义 key
4. 选择 HTTP 路由
5. 组织参数
6. 最后解释结果

对弱模型来说，这条链路更长，也更容易在前几步就偏掉。

### 3.5 外部 skill 的脚本更贴近底层能力

外部 skill 自带的脚本很实用，主要有三类：

1. `prom_query.py`
   - 支持 instant query / range query
   - 支持 table / json / csv 输出

2. `prom_metadata.py`
   - 支持 series / labels / values / metadata / targets

3. `prom_health.py`
   - 支持 ready / healthy / build info / runtime info / rules / alerts / tsdb

这类脚本本质上是“低假设、强确定性”的工具。

而 V5 的 HTTP 工具虽然也稳定，但它更偏“封装后的场景能力”，不是“Prometheus 原生工具箱”，所以在开放式问询里灵活性不如外部 skill。

### 3.6 V5 的设计目标本来就更窄

这个结论要说清楚：`V5 并不是写差了，而是目标定得更窄了。`

V5 当时的目标是：

- 用一个 prompt + 一个 skill + 一组 HTTP 工具
- 支撑高频、重复、稳定的问法
- 尽量不要自由生成 PromQL
- 用固定语义换稳定性

这个设计对“标准化问题”是合理的，但对“临时问诊”并不占优。

因此这次实测结果说明的是：

`外部 prometheus skill 更适合开放式问询；V5 更适合半结构化、受控场景。`

---

## 4. 当前方案相对 Prometheus + Grafana 的增量价值

Prometheus + Grafana 原本已经能完成：

- 指标采集
- 看板展示
- 阈值告警

Prometheus Agent 的增量价值不在于替代它们，而在于补齐以下能力：

### 4.1 自然语言访问能力

运维或研发不需要先打开 Grafana、找面板、写 PromQL，可以直接提问：

- 哪台机器内存超过 70%
- 最近哪几个队列消费不足
- 某台 Redis 有没有明显风险

这会明显降低日常排查门槛。

### 4.2 巡检型输出能力

Grafana 更适合实时看板和告警，不擅长“按固定格式生成一份巡检报告”。

V4 方案已经支持：

- 固定时间巡检
- 结构化风险分级
- AI 补充说明
- HTML 报告输出

这更适合周报、日报、领导汇报。

### 4.3 趋势预警能力

Grafana 告警更多是“问题已经发生”后的响应。

Prometheus Agent 更适合做：

- 持续增长识别
- 突增识别
- 触顶时间预测
- 24 小时趋势判断

也就是“提前发现风险”，而不是只在越线后报警。

### 4.4 关联解释能力

Grafana 会告诉你某个告警触发了，但不会自然地解释：

- 哪几个指标可能是同一问题的不同表现
- 哪个风险更值得先处理
- 哪些现象可能是上游原因导致的

Agent 通过 AI 可以把多个指标结果汇总成更接近人工巡检结论的说明。

---

## 5. V4 与 Prometheus Skill 的作用和优势

这两个能力不是重复建设，而是分工不同、互相补位。

### 5.1 V4 的作用和优势

#### 架构上

V4 是一条完整的巡检流水线，特点是：

- 平台负责流程编排、定时触发、调用 AI
- Python 服务负责查询计划、查询结果、批次文件、分析结果、报告文件
- AI 只参与意图理解、批次补充分析、最终关联分析

这种分层的好处是：

- 平台配置复杂度可控
- 中间态数据可沉淀、可复查、可审计
- 查询和分析过程不依赖单次模型输出
- 更适合稳定运行

#### 设计上

V4 的设计偏“工程化巡检”：

- 有固定查询计划
- 有固定指标 catalog
- 有固定策略分析
- 有批次化 AI 分析
- 有标准化报告输出

这套设计的优势是：

- 输出一致性强
- 结果可追踪
- 方便持续优化规则
- 适合纳入正式运维流程

#### 应用上

V4 更适合以下场景：

- 每日/每周定时巡检
- 重要系统健康盘点
- 趋势型风险预警
- 运维日报、周报、专项汇报
- 面向领导或管理侧的可读性输出

一句话概括：

`V4 更像巡检系统，而不是聊天工具。`

### 5.2 Prometheus Skill 的作用和优势

#### 架构上

Prometheus skill 更轻量，核心是：

- 平台挂载 prompt / skill / 工具
- 模型基于 skill 内容理解 Prometheus 原生能力
- 工具直接面向 Prometheus HTTP API

它没有 V4 那么重的中间态管理，更适合“问一次、查一次、答一次”的链路。

#### 设计上

Prometheus skill 的设计偏“原生能力暴露”：

- 直接围绕 Prometheus API
- 支持 query / query_range / series / labels / metadata / targets / alerts
- 支持 discovery
- 支持健康检查和基础状态检查

这套设计的优势是：

- 更灵活
- 泛化能力更强
- 不容易被少量固定语义限制住
- 遇到未知指标时可以先 discovery，再查询

#### 应用上

Prometheus skill 更适合以下场景：

- 值班人员临时问诊
- 研发自助查指标
- 临时定位哪个 job / instance 有问题
- 先摸清现场有哪些真实指标
- 快速做一次 PromQL 查询或范围查询

一句话概括：

`Prometheus skill 更像问诊工具，而不是巡检系统。`

### 5.3 两者结合后的整体价值

从能力组合上看，两者刚好覆盖两个不同层面：

1. `V4`
   - 负责周期性、规范化、可汇报的巡检
2. `Prometheus skill`
   - 负责即时性、探索性、自然语言驱动的问询

组合后的价值是：

- 既能主动巡检，又能被动问诊
- 既能出正式报告，又能做临时排查
- 既能做固定规则分析，又能做开放式查询
- 既能服务运维管理，也能服务一线排障

所以从架构和应用层面看，最合理的定位不是二选一，而是：

`V4 负责标准化巡检，Prometheus skill 负责自然语言问诊。`

---

## 6. 建议的最终落地方向

基于当前验证结果，建议后续不要把所有能力强行揉成一个 agent，而是分成两条能力线长期保留。

### 方案 A：保留 V4 作为正式巡检能力

适用场景：

- 每日/每周自动巡检
- 例行风险排查
- 报告输出
- 管理汇报

特点：

- 流程固定
- 输出稳定
- 便于审计
- 便于持续优化分析规则

### 方案 B：保留 Prometheus skill 作为临时问诊能力

适用场景：

- 值班人员临时排障
- 研发同学快速查询
- 不确定指标名时先做 discovery
- 临时 PromQL 问询

特点：

- 更灵活
- 更贴近 Prometheus 原生能力
- 更适合开放式问题

### 最终组合建议

建议对老板汇报时，把整体能力定义成：

`Prometheus Agent = 巡检代理 + 问诊代理`

其中：

- `巡检代理` 基于 V4
- `问诊代理` 基于 Prometheus skill

这样表达最清楚，也最符合当前实际效果。

---

## 7. 下一步建议

下一阶段建议做 4 件事：

1. 把外部 Prometheus skill 的优点借到内部版本里
   - 增加 metadata / series / labels / targets / alerts / rules 等能力
   - 增加 PromQL 常见模板和原生 API 说明

2. 给问诊能力增加“双路模式”
   - 常见问题走固定语义模式
   - 超出固定语义的问题走 discovery / 原生查询模式

3. 持续完善 catalog
   - 根据真实 Prometheus 环境补全 node、jvm、redis、rabbitmq 关键指标

4. 继续优化巡检报告
   - 强化管理视角摘要
   - 强化风险排序
   - 强化建议项可执行性

---

## 8. 一句话总结

当前项目已经具备实际落地价值：

- `V4` 已经能稳定完成巡检和报告输出
- `Prometheus skill` 已经能稳定完成临时自然语言问询

下一步重点不是推翻重做，而是把“巡检”和“问诊”两条能力线明确分层，并把外部 skill 的原生 Prometheus 能力逐步吸收到内部方案中。
