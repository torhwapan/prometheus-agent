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

## 10. 当前巡检指标补充说明

结合当前实现，`V4` 中重点巡检项补充如下：

### 10.1 node exporter

- CPU 使用率
- 内存使用率
- 分区使用率
- 分区 inode 使用率
- 磁盘 IO 使用率
- 磁盘读取带宽
- 磁盘写入带宽
- 网络下载带宽
- 网络上传带宽

### 10.2 jvm

- JVM 进程 CPU 使用率
- JVM Heap 使用率
- GC Time
- GC Count Increase
- Thread Used
- 文件句柄使用率



todo：
1,公司调用http请求是通过bash工具来完成的，skill需要更新
2，http接口的参数必须要填对，但是ai只会根据用户提供来猜测参数值是什么，必须先让ai知道，这些参数的值可以是什么。 比如我问ai：帮我查下http://127.0.0.1:9090这个prometheus上监控的jvm堆使用率，它并不知道堆使用率该用jvm_heap_usage，它根据中文名拼出的是jvm-heap-usage
3，缺乏基本的指标查询功能。 我让ai查询"帮我查下http://127.0.0.1:9090这个prometheus上监控的jvm堆使用率",它执行的curl命令是这样的：curl -X POST 'http://10.27.92.82:8050/v5/query/inspection' -H 'Content-Type: application/json' -d '{"prometheus_url": "http://127.0.0.1:9090", "semantic_key": "jvm-memory-risk", "job": "java_jmx"}， semantic_key它给的是jvm-memory-risk，把主要的jvm数据查了出来。
4，node节点缺少cpu使用率
5，总体使用效果不如这个skill:https://github.com/julianobarbosa/claude-code-skills/tree/main/skills/prometheus
6，RabbitMQ Queue Consumer Utilisation 这个指标有问题，报错： timeout。
7，node exporter监控项： cpu使用率，内存使用率，分区使用率，磁盘读取，磁盘写入，下载带宽，上传带宽； 
jvm监控项：gc count 增加，参考（increase(jvm_gc_collection_seconds_count{job="$job",instance=~"$instance"}[$__interval])），GC time， Thread used 参考（jvm_threads_current{job="$job",instance="$instance"}），
8，帮忙写个ppt吧




好的，我需要帮助用户查询Prometheus实例上的jobs。用户提供的地址是http://127.0.0.1:9090。首先，我应该确认用户的需求是获取所有配置的job列表。
根据可用的skills，有一个名为prometheus的技能，用于查询Prometheus的HTTP API。因此，我需要使用这个skill来执行查询。Prometheus的API通常提供一个/api/v1/status/config端点，可以返回配置信息，包括jobs。
接下来，我需要调用prometheus skill，并指定查询Prometheus的配置。用户可能需要的是targets信息，但根据问题，用户明确询问jobs，所以可能是指配置中的job列表。不过，Prometheus的API中，/api/v1/targets会返回当前抓取的目标，按job分组。而配置中的jobs可能在/api/v1/status/config中。因此，可能需要先获取配置，然后解析其中的scrape配置部分。
或者，可能直接通过Prometheus API的某个端点获取所有job名称。例如，/api/v1/labels/job会返回所有存在的job标签值。但需要确认Prometheus的API是否支持这个路径。或者，用户可能需要的是当前正在运行的jobs，比如在targets中的状态。
但用户的问题比较直接，所以可能需要调用Prometheus API的/api/v1/targets来获取所有job的名称。这个端点返回的数据结构中包含各个job及其目标的状态信息。
因此，正确的做法是使用prometheus skill，发送GET请求到http://127.0.0.1:9090/api/v1/targets，然后解析返回的JSON数据中的job名称列表。
不过，用户可能需要的是配置中的job定义，而不是当前的目标状态。这时候需要访问/api/v1/status/config，然后解析其中的scrape_configs部分。但访问配置可能需要权限，并且配置可能很大，包含敏感信息，所以用户可能更倾向于获取当前的目标列表。
综合来看，用户的问题更可能是指当前Prometheus实例中配置的job名称，因此通过查询/api/v1/targets来获取所有job名称是合适的。因此，我需要使用prometheus skill来执行这个查询，并返回结果给用户。
好的，我现在需要帮用户查询Prometheus实例上的jobs。用户提供的地址是http://127.0.0.1:9090。用户之前尝试使用"prometheus"技能，但系统提示该技能不可用。现在我要找出正确的解决方法。
首先，检查可用的工具列表。用户提到的skills中的prometheus技能对应的工具可能没有被正确识别，或者需要通过其他方式调用。根据用户提供的工具列表，现有的工具包括bash、curl等，但并没有直接提到Prometheus的API调用工具。不过，用户可能想通过bash执行curl命令来访问Prometheus的API。
用户之前调用了名为"prometheus"的工具，但系统提示无效。可能因为该工具未被正确配置或不在可用工具列表中。现在需要手动构造请求。Prometheus的API中，获取targets信息通常通过/api/v1/targets端点，所以正确的URL应该是http://127.0.0.1:9090/api/v1/targets。
接下来，我需要使用bash工具执行curl命令来获取这个端点的数据。因此，应该使用bash函数，参数是curl命令，例如：curl -X GET http://127.0.0.1:9090/api/v1/targets。这样就能获取到Prometheus的targets信息，其中包括各个job的状态和配置。
需要确认用户是否有权限访问该地址，以及是否需要认证。如果存在认证问题，可能需要用户提供更多信息，比如用户名和密码，或者使用OAuth2授权。但根据用户的问题，暂时没有提到认证需求，所以先尝试直接访问。
因此，正确的工具调用应该是使用bash执行curl命令访问指定的API端点，从而获取jobs信息。
好的，用户让我查询Prometheus实例上的jobs，我之前尝试直接使用prometheus技能，但发现无效，于是改用bash命令执行curl请求。现在得到了响应，需要解析结果。首先看输出中的data.activeTargets数组，每个目标都有job字段。
观察到的jobs有java_jmx、node_exporter、prometheus、rabbitmq_exporter、redis_exporter和thread_pool_exporter。需要注意的是，虽然java_jmx出现了多次，但可能属于同一个job的不同实例。需要整理出唯一的job名称，并列出对应的实例地址和状态。
另外，所有目标的健康状态都是down，错误原因包括连接被拒绝和磁盘空间不足。需要将这些信息整理成用户友好的格式，说明每个job的实例和问题所在。同时，用户可能关心如何解决这些问题，比如检查端口是否开放或清理磁盘空间。但用户当前的需求主要是列出jobs，所以先聚焦在结果上，再简要提及可能的问题。
