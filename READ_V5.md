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


namespace和application维度的：
jvm_buffer_count_buffers{application="System1", cluster="b248b1e7", cluster_name="prod-System1", endpoint="tcp-9000", id="direct", instance="19.19.19.19:8080", job="system-actuator-prometheus", k8s_cluster_name="prod-System1", namespace="test", pod="system1-8bcb965dd", prometheus="insight-system/insight-agent-kube-prometh-prometheus", service="system-actuator-prometheus"}




你这个场景，其实非常适合引入 Agent，但前提是思路要对。
核心判断是：你们 OnCall 的痛点，通常不是“不会处理问题”，而是“信息分散、判断链条长、重复劳动多、跨系统切换太重”。所以 Agent 最适合先做的，不是替人拍板，也不是一上来自动改系统，而是先把运维同事从“找资料、拼上下文、跑标准检查、整理沟通信息”这些高频杂事里解放出来。
核心思路
先把 Agent 定位成 OnCall Copilot，而不是 Autonomous Operator。
它的目标应该是 4 件事：
自动理解 case：这单子更像用户不熟流程、系统报错、配置问题、权限问题，还是跨部门沟通问题。
自动拉上下文：把日志、相关代码、DB 记录、需求文档、历史 case、runbook 一次性聚合给工程师。
自动给排查路径：告诉运维“先看哪几个点、先问谁、先查哪张表、哪些现象最像历史哪个 case”。
自动沉淀经验：每个 case 处理完，反向形成知识资产，而不是靠人脑记忆。
所以第一阶段最有价值的，不是“让 Agent 解决问题”，而是“让 Agent 帮人更快进入问题”。
建议的落地顺序
我建议你们按 3 个阶段推进。
第一阶段：知识助手
先做一个能“查得到”的 Agent。
接入这些数据源：
历史 case 单
SOP / runbook
需求文档 / 流程说明
常见报错码说明
系统日志检索入口
DB schema 和常用查询模板
代码仓库的只读检索能力
这阶段 Agent 的能力是：
用户贴一个 case 编号或报错信息
Agent 自动总结问题
找出相似历史 case
给出可能原因排序
输出建议排查清单
草拟回复给产线或其他团队的话术
这一阶段就已经能明显降低新人上手难度，也能减少 senior 被反复打断。
第二阶段：工具型 Agent
让 Agent 不只是“回答”，而是能“帮你做检查”。
例如给它受控工具权限：
查日志
查指定 DB 只读信息
查工单系统
查配置中心
查发布记录
查某条流程的状态流转
对照需求文档解释当前卡控逻辑
这时它的输出不再只是建议，而是：
“我已经查了 A/B/C，发现这单最像 X”
“这个 lot 卡在步骤 Y，原因疑似是规则 Z 未满足”
“最近 24 小时同类 case 增长了 3 倍，可能不是个例”
“和上周版本发布存在时间重合，建议优先确认变更影响”
这一步是最容易真正提升 MTTA/MTTR 的。
第三阶段：半自动处置
只有当你们前两阶段的数据质量和流程边界足够清楚，才考虑让 Agent 做受控动作。
例如：
自动生成标准 SQL / 查询脚本，人工确认后执行
自动触发低风险诊断脚本
自动通知对应 owner
自动补充 case 必填信息
自动创建跨团队协作单
一开始不要让 Agent 直接改配置、改数据、重跑关键流程。半导体产线场景里，误动作成本太高，必须坚持 human-in-the-loop。
最值得优先做的 5 类场景
如果你问“第一批从哪里下手”，我会优先挑这些：
相似 case 检索
价值最大，因为你们很多经验其实已经存在，只是找不到。

报错解释 + 排查路径推荐
把 senior 的思路结构化给所有人复用。

跨系统上下文聚合
把 case、日志、DB、代码、文档串起来，减少切屏和信息遗漏。

标准化沟通辅助
自动生成给产线、开发、产品、其他支持团队的沟通摘要和追问清单。

结案沉淀
每个 case 自动抽取“现象-原因-处理-验证-预防”，形成知识库闭环。

你们要先补的基础，不是模型，而是“知识和流程结构化”
很多团队做 Agent 失败，不是模型不行，而是底层材料太乱。你们至少要整理出下面这些东西：
case 分类体系
常见问题的标准排查路径
各系统的只读查询接口
历史 case 的质量分级
关键字段统一命名
哪些动作允许 Agent 做，哪些绝对不允许
升级/escalation 规则
如果这些不先整理，Agent 只会把混乱放大。
组织上要注意的一点
不要把它当成“AI 项目”，要把它当成“运维知识生产线重构”。
真正要解决的是：
经验过度依赖少数老人
case 处理质量不稳定
新人培养慢
跨部门沟通成本高
同类问题重复劳动严重
Agent 只是承载这个能力的形式。
衡量是否做对了
建议盯这几个指标，而不是只看“回答像不像”：
首次响应时间是否下降
平均定位时间是否下降
同类 case 的重复处理时间是否下降
新人独立处理率是否上升
senior 介入比例是否下降
Agent 建议的采纳率和误导率
case 结案知识沉淀率
一句话总结
你们最适合的切入点，不是“让 Agent 代替 OnCall”，而是先做一个懂你们流程、能跨日志/DB/代码/文档/历史 case 拉通上下文的 OnCall Copilot。先辅助判断，再辅助操作，最后才考虑有限自动化。
如果你愿意，我下一步可以直接帮你把这个思路落成一份更实战的方案，比如：
你们 OnCall Agent 的 MVP 功能清单
一套适合半导体运维的 Agent 架构图
怎么从历史 case 数据开始做第一版知识库
你如果想继续，我建议我们下一步直接做第 1 个：把 MVP 范围收出来，这样最容易落地。


