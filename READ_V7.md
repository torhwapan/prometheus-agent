# Prometheus Agent V7

`V7` 不是再做一套新的巡检引擎，而是把已经完成的 `V6` 固定巡检能力，进一步包装成一个项目本地可复用的 skill。

它的目标很明确：

1. 让 Codex 或其他具备 skill 机制的大模型，知道这是一个“固定巡检”能力
2. 让模型不要自由发挥去查 PromQL，而是按我们预设的指标、PromQL、规则和报告格式执行
3. 让最终输出仍然保持为固定格式的 HTML 报告

所以从版本演进上看：

- `V5`：依赖公司平台来编排多步接口调用
- `V6`：去平台化，由 Python 自己完成整条巡检链路
- `V7`：在 `V6` 之上做 skill 化封装，让模型能稳定调用这套固定巡检能力

## 一、V7 的本质

`V7` 的本质不是“新增一套业务逻辑”，而是“给固定巡检能力加一个标准入口和标准使用说明”。

也就是说：

- 真正的巡检执行引擎还是 `prometheus_agent_v6/`
- `prometheus-fixed-inspection-v7/` 负责的是 skill 入口、说明、边界和调用方式

这样做的好处是：

1. 巡检逻辑和 skill 说明解耦
2. 以后改巡检规则时，主要改 `V6`
3. 以后改 skill 触发方式或使用说明时，主要改 `V7`

## 二、V7 解决了什么问题

当前 Codex 环境里已经有一个通用的 `prometheus` skill，它更适合做这些事情：

- 临时查某个 PromQL
- 自然语言探索指标
- 查看 targets、alerts、rules、metadata

但我们的场景不是这种“自由查询”，而是“固定巡检”：

1. 查哪些指标是预先定义好的
2. 每个指标对应的 PromQL 是预先定义好的
3. 分析策略是固定的
4. HTML 报告结构是固定的

这也是为什么要做 `V7`：

- 它不是通用 Prometheus 助手
- 它是固定巡检 skill

## 三、V7 的目录结构

当前 `V7` skill 放在项目根目录：

```text
prometheus-fixed-inspection-v7/
├─ SKILL.md
├─ agents/
│  └─ openai.yaml
├─ references/
│  ├─ fixed-scope.md
│  └─ report-contract.md
└─ scripts/
   └─ run_fixed_inspection.py
```

各文件职责如下：

### 1. `SKILL.md`

这是 skill 的核心说明文件。

它定义了：

- 这个 skill 是干什么的
- 什么情况下应该触发它
- 应该怎么调用脚本
- 哪些行为是允许的，哪些是不允许的

如果以后你发现模型没有正确使用这个 skill，第一优先看这里。

### 2. `agents/openai.yaml`

这是 skill 的界面元数据，主要给技能列表和默认 prompt 用。

它不负责业务逻辑，但会影响：

- UI 里怎么展示 skill
- 默认提示词是什么

### 3. `references/fixed-scope.md`

这个文件用来说明固定巡检的边界。

主要告诉模型：

- 支持哪些 job
- 这不是自由 PromQL 查询工具
- 不能让 AI 自己决定查什么

如果以后要扩充支持的 job，或者调整 skill 的边界，可以改这个文件。

### 4. `references/report-contract.md`

这个文件用来说明最终产物是什么。

在 `V7` 里，最终产物约束为：

- 只输出一个 HTML 文件
- 报告结构固定
- AI 只能补充说明，不能改变规则判级

如果以后要调整 HTML 输出合同，可以改这里，同时联动 `V6` 的 renderer。

### 5. `scripts/run_fixed_inspection.py`

这是 `V7` 的实际脚本入口。

它本身不实现巡检规则，而是负责：

1. 接收命令行参数
2. 找到项目根目录
3. 调用 `prometheus_agent_v6.service.inspect_prometheus`
4. 输出最终 HTML

你可以把它理解成：

- skill 的稳定执行入口
- `V6` 引擎的适配层

## 四、V7 的执行原理

整个执行链路如下：

1. 用户给出 `prometheus_url`
2. skill 触发 `run_fixed_inspection.py`
3. 脚本调用 `prometheus_agent_v6.service.inspect_prometheus`
4. `V6` 先发现 Prometheus 里当前有哪些受支持的 job
5. `V6` 自动匹配固定 inspection pack
6. `V6` 执行固定 PromQL
7. `V6` 用固定规则做分析
8. 如配置了大模型接口，则补充简短 AI 说明
9. `V6` 生成固定格式 HTML
10. `V7` 将 HTML 路径返回给调用方

所以 `V7` 的原则是：

- skill 负责“怎么让模型正确使用能力”
- `V6` 负责“怎么真正执行能力”

## 五、V7 对外依赖

`V7` 自己没有复杂的外部依赖，它最终依赖的其实只有两类：

### 1. Prometheus HTTP API

用于：

- 发现 job / target
- 执行 instant query
- 执行 range query

### 2. 可选的大模型接口

用于：

- 给高风险项补一句简短说明
- 给整份报告补一个摘要

注意：

- AI 不是主流程编排器
- AI 不决定查哪些指标
- AI 不决定告警等级
- AI 不能覆盖规则引擎的结论

## 六、为什么 V7 可维护

`V7` 的可维护性主要来自职责拆分比较清楚：

### 1. 需要改巡检逻辑时

优先改：

- `prometheus_agent_v6/catalog.py`
- `prometheus_agent_v6/analysis.py`
- `prometheus_agent_v6/report.py`
- `prometheus_agent_v6/service.py`

也就是说，查什么、怎么判、怎么展示，主要在 `V6`。

### 2. 需要改 skill 触发和说明时

优先改：

- `prometheus-fixed-inspection-v7/SKILL.md`
- `prometheus-fixed-inspection-v7/references/*.md`
- `prometheus-fixed-inspection-v7/agents/openai.yaml`

也就是说，模型如何理解这项能力，主要在 `V7`。

### 3. 需要改命令入口时

改：

- `prometheus-fixed-inspection-v7/scripts/run_fixed_inspection.py`

例如：

- 增加新的 CLI 参数
- 调整输出路径策略
- 适配新的运行方式

## 七、以后最常见的维护场景

### 场景 1：新增一个受支持的 job

通常要改：

1. `prometheus_agent_v6/catalog.py`
2. 必要时改 `prometheus_agent_v6/analysis.py`
3. 必要时改 `prometheus_agent_v6/report.py`
4. 更新 `prometheus-fixed-inspection-v7/references/fixed-scope.md`

### 场景 2：修改某个指标的 PromQL 或阈值

通常只需要改：

1. `prometheus_agent_v6/catalog.py`
2. 如分析逻辑变了，再改 `prometheus_agent_v6/analysis.py`

### 场景 3：调整 HTML 样式或结构

通常要改：

1. `prometheus_agent_v6/report.py`
2. `prometheus-fixed-inspection-v7/references/report-contract.md`

### 场景 4：调整 AI 的提示词或策略

通常改：

1. `prometheus_agent_v6/llm.py`

但要记住：

- 不能把 AI 变成“决定查什么”的角色
- 不能让 AI 覆盖规则判级

### 场景 5：模型没有正确触发 skill

优先检查：

1. `prometheus-fixed-inspection-v7/SKILL.md`
2. `prometheus-fixed-inspection-v7/agents/openai.yaml`

## 八、V7 的使用方式

当前本地运行命令：

```powershell
python prometheus-fixed-inspection-v7/scripts/run_fixed_inspection.py --prometheus-url http://127.0.0.1:9090 --output report_v7.html
```

按实例过滤：

```powershell
python prometheus-fixed-inspection-v7/scripts/run_fixed_inspection.py --prometheus-url http://127.0.0.1:9090 --instance 127.0.0.1:9095 --output report_v7.html
```

限制 job：

```powershell
python prometheus-fixed-inspection-v7/scripts/run_fixed_inspection.py --prometheus-url http://127.0.0.1:9090 --job redis_exporter --job java_jmx --output report_v7.html
```

关闭 AI：

```powershell
python prometheus-fixed-inspection-v7/scripts/run_fixed_inspection.py --prometheus-url http://127.0.0.1:9090 --output report_v7.html --disable-ai
```

## 九、维护建议

以后维护 `V7` 时，建议你记住一句话：

`V7` 是 skill 外壳，`V6` 是巡检引擎。

因此：

- 功能不对，先看 `V6`
- skill 不触发、触发不准、调用姿势不对，先看 `V7`

只要这个边界不乱，后面继续演进到 `V8`、`V9` 都会比较顺。
