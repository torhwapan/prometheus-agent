# RabbitMQ And MQ Core Metrics

## Core

- Queue ready messages: backlog pressure. Use `queue_backlog`.
- Queue unacked messages: consumer processing or acknowledgement risk. Use `queue_backlog`.
- Consumer count: missing consumer risk. Use `availability`.
- Publish rate: producer traffic. Use `rate_change`.
- Deliver/consume rate: consumer throughput. Use `rate_change`.
- Backlog growth rate: expected time to threshold. Use `queue_backlog`.

## Secondary

- Node memory and disk alarms.
- Connection and channel counts.
- Redelivered messages rate.

## Interpretation Notes

Backlog is risky when it is sustained or growing faster than consumption. A large backlog with high consumption may be less urgent than a smaller backlog with zero consumers.
