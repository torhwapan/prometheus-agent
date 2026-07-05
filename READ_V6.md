# Prometheus Agent V6

`V6` 的目标是把原来依赖公司平台编排的 Prometheus 巡检流程，改成一套纯 Python 自主完成的固定巡检程序。

它保留了你原来最核心的三件事：

1. 固定指标和固定 PromQL
2. 固定规则分析策略
3. 固定 HTML 报告格式

不同的是，`V6` 不再通过平台去串多个接口，而是由 Python 直接完成：

1. 连接 Prometheus
2. 发现当前有哪些受支持的 job
3. 自动匹配固定巡检 pack
4. 执行固定 PromQL 查询
5. 用固定规则完成判级和结论生成
6. 可选调用大模型接口补充说明
7. 输出最终 HTML 报告

## 运行方式

```powershell
python -m prometheus_agent_v6 --prometheus-url http://127.0.0.1:9090 --output report_v6.html
```

按实例过滤：

```powershell
python -m prometheus_agent_v6 --prometheus-url http://127.0.0.1:9090 --instance 127.0.0.1:9095 --output redis_report_v6.html
```

指定只巡检某几个固定 job：

```powershell
python -m prometheus_agent_v6 --prometheus-url http://127.0.0.1:9090 --job redis_exporter --job java_jmx
```

## 可选 AI 补充分析

AI 不是编排器，也不决定查什么、怎么判级。

AI 只做两件事：

1. 给高风险项补一句简短解释
2. 给整份报告补一段摘要

配置方式使用环境变量：

```powershell
$env:LLM_BASE_URL="https://api.openai.com/v1"
$env:LLM_API_KEY="your-key"
$env:LLM_MODEL="gpt-4.1-mini"
python -m prometheus_agent_v6 --prometheus-url http://127.0.0.1:9090
```

如果不想启用 AI：

```powershell
python -m prometheus_agent_v6 --prometheus-url http://127.0.0.1:9090 --disable-ai
```

## 当前固定巡检范围

- `node_exporter`
- `java_jmx`
- `redis_exporter`
- `rabbitmq_exporter`

这些 job 的固定指标和阈值来自你现有仓库里的成熟定义，但 `V6` 的执行链路已经独立，不再依赖公司平台的接口编排。
