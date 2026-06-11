# RabbitMQ PromQL Patterns

Metric names vary by RabbitMQ exporter version. Preserve `queue`, `vhost`, `job`, and `instance` labels.

## Queue Ready Messages

```promql
rabbitmq_queue_messages_ready
```

Use `queue_backlog`, `higher_is_bad`.

## Queue Unacked Messages

```promql
rabbitmq_queue_messages_unacked
```

Use `queue_backlog`, `higher_is_bad`.

## Publish Rate

```promql
rate(rabbitmq_queue_messages_published_total[5m])
```

Use `rate_change`.

## Deliver Rate

```promql
rate(rabbitmq_queue_messages_delivered_total[5m])
```

Use `rate_change`.

## Consumer Count

```promql
rabbitmq_queue_consumers
```

Use `availability`, `lower_is_bad` for queues that must have consumers.

## Backlog Growth Approximation

Use ready messages as the primary backlog series. Compare publish and deliver rates when both counters exist:

```promql
rate(rabbitmq_queue_messages_published_total[5m]) - rate(rabbitmq_queue_messages_delivered_total[5m])
```
