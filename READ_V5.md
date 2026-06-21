# Prometheus Agent V5 设计说明

## 1. 定位

V5 不再定义成一套新的 Python 服务。

V5 的定位是：

- 一组给公司 AI 平台使用的提示词
- 一组约束自然语言问诊行为的 skill
- 用于把用户临时提问稳定地转成结构化意图

也就是说，V5 只负责两件事：

1. 理解用户问题
2. 规范模型输出

真正的查询、分析、筛选、报表生成，继续复用现有的 Python 执行层能力，例如：

- V4 的固定巡检能力
- 你们后续新增的 Prometheus 查询工具
- 你们后续新增的条件筛选工具

这样拆分更合适，因为你们平台本身就负责：

- 串联大模型
- 调用工具
- 编排执行顺序

V5 没必要再额外做一层独立服务。

## 2. 目录结构

当前 V5 建议保持成下面这样的资产目录：

```text
prompts_v5/
  README.md
  intent_extraction.md
  result_explanation.md
  skills/
    prometheus-v5-dialog/
      SKILL.md

READ_V5.md
```

说明：

- `prompts_v5/`：V5 的主体目录
- `intent_extraction.md`：意图抽取提示词
- `result_explanation.md`：结果解释提示词
- `skills/prometheus-v5-dialog/SKILL.md`：给模型补充问诊约束、语义映射和抽取规则
- `READ_V5.md`：V5 的设计说明

这个目录结构的核心意思很明确：

- V5 是一套“提示词资产包”
- skill 也是 V5 资产的一部分
- 不再单独维护 `skills_v5/`
- 不再单独维护 `prometheus_agent_v5/`

## 3. 每个文件的作用

### 3.1 `prompts_v5/intent_extraction.md`

作用：

- 把用户自然语言问题抽取成结构化 JSON
- 只做信息识别，不做 PromQL 生成

主要输出字段包括：

- `prometheus_url`
- `job`
- `instance`
- `intent_type`
- `semantic_hint`
- `range_hours`
- `step_seconds`
- `current_window`
- `comparison`
- `threshold`
- `top_n`

这个提示词适合放在平台的第一步。

### 3.2 `prompts_v5/skills/prometheus-v5-dialog/SKILL.md`

作用：

- 约束模型不要自由发挥
- 告诉模型有哪些固定语义类别
- 告诉模型常见中文问法应该映射到什么结构化意图

它本质上不是执行逻辑，而是模型的行为边界说明。

### 3.3 `prompts_v5/result_explanation.md`

作用：

- 在 Python 工具已经返回确定性结果之后
- 让模型生成一段短结论和建议

这个提示词是可选的。

如果平台只想直接展示 Python 返回的表格结果，可以不调用它。

## 4. V5 的职责边界

V5 负责：

- 理解“用户想查什么”
- 识别目标 Prometheus 地址
- 识别 job 类型
- 识别筛选条件、阈值、时间范围
- 输出稳定 JSON

V5 不负责：

- 直接生成 PromQL
- 直接查询 Prometheus
- 维护执行计划
- 存储批次数据
- 生成 HTML 巡检报告

这些事情都应该继续放在执行层工具里。

## 5. 推荐调用链路

推荐把平台编排成下面这样：

```text
用户输入自然语言问题
  -> 大模型 + prompts_v5/intent_extraction.md
  -> 同时挂载 prompts_v5/skills/prometheus-v5-dialog/SKILL.md
  -> 输出结构化意图 JSON
  -> 平台调用现有 Python 工具执行查询 / 巡检 / 条件筛选
  -> 如有需要，再调用 prompts_v5/result_explanation.md
  -> 返回最终结果给用户
```

## 6. 三类典型问法

### 6.1 巡检类

例如：

```text
帮我看下 10.22.23.24 上的 redis 有没有异常
```

适合抽成：

- `intent_type = inspection`
- `job = redis`
- `semantic_hint = redis-health`

然后交给现有巡检型 Python 工具执行。

### 6.2 条件筛选类

例如：

```text
帮我查询下内存使用率超过了 70% 的服务器
```

适合抽成：

- `intent_type = metric_filter`
- `job = node`
- `semantic_hint = node-memory-usage`
- `comparison = >`
- `threshold = 70`

然后交给条件查询工具执行。

### 6.3 排名类

例如：

```text
CPU 最高的 10 台服务器
```

适合抽成：

- `intent_type = metric_topn`
- `job = node`
- `semantic_hint = node-cpu-top`
- `top_n = 10`

然后交给排序查询工具执行。

## 7. 为什么这样拆更合理

原因很简单：

1. 你们平台已经负责流程编排
2. 大模型能力偏弱，不适合直接自由生成 PromQL
3. 临时问诊最关键的是“意图稳定抽取”，不是“再写一套后端服务”
4. skill 和 prompt 更适合沉淀问诊经验、映射规则和输出约束

所以 V5 更适合定义成：

- 一套提示词
- 一个问诊 skill
- 一套面向平台编排的规范

而不是一套新的服务代码。

## 8. 后续扩展方式

如果后面要继续扩展 V5，建议优先扩的是下面这些内容：

1. 扩展 `intent_extraction.md` 的样例
2. 扩展 `SKILL.md` 里的语义类别
3. 扩展更多常见问法的中文别名
4. 让执行层 Python 工具支持更多固定查询模板

不要优先做的事情是：

- 让模型自由写 PromQL
- 把任意开放式查询都交给大模型生成

那样会把稳定性拉低。

## 9. 当前结论

当前 V5 的目录和定位，应当理解为：

- `V4`：固定流程巡检 + 文件批次 + HTML 报告
- `V5`：自然语言临时问诊的提示词和 skill 资产

这两个版本是并列关系，不要混在一起。
