# Prometheus Agent V6

`V6` 的目标，是把原来依赖公司平台编排的 Prometheus 巡检流程，改造成一套由 Python 自主执行的固定巡检程序。

它保留了原先最核心的三件事情：

1. 固定指标和固定 PromQL
2. 固定规则分析策略
3. 固定 HTML 报告格式

和旧版本最大的区别在于，`V6` 不再依赖公司平台去串多个接口，而是由 Python 自己完成完整巡检链路。

## 一、V6 的定位

从版本演进上看：

- `V5`：依赖公司平台来编排不同接口，最终完成巡检
- `V6`：不再依赖公司平台，由 Python 本地执行整条巡检流程

所以 `V6` 的定位不是“再做一个接口层”，而是“一个真正能独立运行的巡检引擎”。

只要给出一个 Prometheus 地址，`V6` 就可以自己完成：

1. 发现 Prometheus 当前有哪些受支持的 job
2. 匹配固定 inspection pack
3. 查询固定 PromQL
4. 执行固定规则分析
5. 可选调用大模型接口补充说明
6. 输出最终 HTML 报告

## 二、V6 为什么这样设计

之所以这么设计，是因为你的实际需求并不是一个自由 PromQL 查询助手，而是一个“固定巡检系统”。

这意味着：

- 查哪些指标，应该是预先定义好的
- 每个指标的 PromQL，应该是预先定义好的
- 分析方法和判级规则，应该是固定的
- 输出格式，也应该是固定的

这样做有几个明显好处：

1. 结果稳定，不会因为模型表达不同而改变巡检口径
2. 可维护，巡检逻辑都收敛在 Python 代码中
3. 可复用，任何能运行 Python 的环境都能调用
4. 可扩展，后面做 `V7 skill` 或继续做 `V8` 都有明确基础

## 三、V6 的目录职责

`V6` 当前放在：

```text
prometheus_agent_v6/
```

核心模块职责如下：

### 1. `catalog.py`

这里定义固定巡检指标目录和固定 inspection pack。

主要负责：

- 支持哪些 job
- 每个 job 需要巡检哪些指标
- 每个指标对应什么 PromQL
- 每个指标的阈值、方向、单位等元信息

如果以后你要新增一个 job、调整某个指标的 PromQL、修改阈值，通常先改这里。

### 2. `prometheus.py`

这是 `V6` 的 Prometheus HTTP API 客户端。

负责：

- instant query
- range query
- 基础 GET / POST 请求封装
- Prometheus 错误处理

也就是说，所有对外 Prometheus 通信都在这里收口。

### 3. `discovery.py`

这个模块负责对 Prometheus 做发现。

主要做：

- 获取 job 列表
- 获取 targets
- 归一化当前环境中可巡检的 job 和实例

这一步的意义是：用户只给一个 Prometheus 地址时，系统也能知道应该巡检哪些固定 pack。

### 4. `planner.py`

这个模块负责把“固定巡检 pack”转成“具体查询任务”。

主要做：

- 根据时间范围生成 query task
- 把 PromQL 中的窗口参数替换成实际值
- 在需要时附加 instance 过滤

你可以把它理解成“巡检任务拆解器”。

### 5. `analysis.py`

这个模块是 `V6` 的规则分析引擎。

负责：

- 当前值阈值判断
- 趋势判断
- 突增 / 突降判断
- 持续恶化判断
- 到达上限时间预估
- 最终 severity 判定

这个模块必须保持“规则优先、结果稳定”的原则。

也就是说：

- AI 不能替代这里
- AI 不能覆盖这里的 severity

### 6. `llm.py`

这是可选的大模型补充分析模块。

它的职责非常克制，只做两件事：

1. 给高风险项补一句简短解释
2. 给整份报告补一段摘要

它不负责：

- 决定查什么
- 决定怎么判级
- 改写固定规则结论

### 7. `report.py`

这个模块负责生成固定格式 HTML 报告。

主要职责：

- 报告头部摘要
- 巡检范围信息
- 固定 inspection pack 展示
- findings 表格输出
- AI 补充说明展示

如果以后你想改 HTML 结构、样式、颜色、字段顺序，主要改这里。

### 8. `service.py`

这是 `V6` 的总编排入口。

它负责串起完整流程：

1. Prometheus 发现
2. pack 匹配
3. query plan 生成
4. Prometheus 查询执行
5. 固定规则分析
6. 可选 AI 补充
7. HTML 输出

对外如果只想“一次调用完成巡检”，通常直接走这里。

### 9. `cli.py` / `__main__.py`

这两个文件负责命令行入口。

所以你可以直接运行：

```powershell
python -m prometheus_agent_v6 --prometheus-url http://127.0.0.1:9090 --output report_v6.html
```

## 四、V6 的执行原理

用户给出一个 Prometheus 地址后，`V6` 的执行过程大致如下：

1. 连接 Prometheus
2. 查询当前环境里的 job 和 target 信息
3. 找出当前支持的固定巡检 job
4. 按 job 匹配固定 inspection pack
5. 为每个指标生成 current query 和 range query
6. 执行查询
7. 对每个结果做固定规则分析
8. 合并成全局巡检结论
9. 如有 LLM 配置，则补充 AI 摘要和短评论
10. 输出固定 HTML 报告

也就是说，`V6` 已经不需要公司平台来做多步编排了。

## 五、V6 对外依赖

`V6` 本质上只依赖两类外部能力：

### 1. Prometheus 接口

这是主依赖。

用来做：

- 指标发现
- instant query
- range query

### 2. 可选的大模型接口

这是增强依赖，不是主依赖。

只有在你提供了：

- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`

时，`V6` 才会执行 AI 补充分析。

如果没有配置，巡检依然可以完整执行，只是没有 AI 摘要和补充评论。

## 六、为什么 V6 结果更稳定

`V6` 稳定的核心原因是“AI 退后，规则前置”。

它不是让 AI 来决定整个巡检流程，而是让 Python 代码先把这些事情固定下来：

1. 查哪些指标
2. 每个指标用什么 PromQL
3. 什么条件算 warning
4. 什么条件算 critical
5. 最终 HTML 长什么样

AI 只在最后做可选补充。

这样做比平台编排 + AI 主导更可控，也更适合做正式巡检系统。

## 七、常见维护场景

### 场景 1：新增一个固定巡检 job

通常需要改：

1. `prometheus_agent_v6/catalog.py`
2. 必要时 `prometheus_agent_v6/analysis.py`
3. 必要时 `prometheus_agent_v6/report.py`

### 场景 2：修改某个指标的 PromQL 或阈值

通常先改：

1. `prometheus_agent_v6/catalog.py`

如果分析逻辑也跟着变，再改：

2. `prometheus_agent_v6/analysis.py`

### 场景 3：调整 HTML 报告样式或结构

改：

1. `prometheus_agent_v6/report.py`

### 场景 4：调整 AI 提示词或补充策略

改：

1. `prometheus_agent_v6/llm.py`

但要始终保持这个边界：

- AI 只能补充解释
- AI 不能决定 severity

### 场景 5：需要更换调用方式

如果只是改命令行参数或脚本入口，通常改：

1. `prometheus_agent_v6/cli.py`
2. `prometheus_agent_v6/__main__.py`

## 八、V6 的运行方式

默认运行：

```powershell
python -m prometheus_agent_v6 --prometheus-url http://127.0.0.1:9090 --output report_v6.html
```

按实例过滤：

```powershell
python -m prometheus_agent_v6 --prometheus-url http://127.0.0.1:9090 --instance 127.0.0.1:9095 --output redis_report_v6.html
```

只巡检某几个固定 job：

```powershell
python -m prometheus_agent_v6 --prometheus-url http://127.0.0.1:9090 --job redis_exporter --job java_jmx
```

关闭 AI：

```powershell
python -m prometheus_agent_v6 --prometheus-url http://127.0.0.1:9090 --disable-ai
```

## 九、当前固定巡检范围

目前内置支持的 job 有：

- `node_exporter`
- `java_jmx`
- `redis_exporter`
- `rabbitmq_exporter`

这些 job 的固定指标、PromQL 和阈值，来自当前仓库中已经比较成熟的定义，但 `V6` 的执行链路本身已经完全独立，不再依赖公司平台的接口编排。

## 十、维护时最重要的一句话

如果只记一句话，建议记这个：

`V6` 是一个独立的固定巡检引擎，不是平台接口转发层。

理解了这一点，后面无论是继续增强 `V6`，还是像现在这样继续做 `V7 skill`，都会顺很多。
