# Host Core Metrics

## Core

- CPU usage percent: capacity pressure and noisy workload risk. Use `threshold_trend`.
- Memory usage percent: memory pressure and OOM risk. Use `threshold_trend`.
- Filesystem usage percent: capacity exhaustion risk. Use `growth_to_limit`.
- Inode usage percent: file creation exhaustion risk. Use `growth_to_limit`.
- Target availability: scrape or service availability. Use `availability`.

## Secondary

- Load average per CPU core.
- Network receive/transmit rate.
- Disk IO utilization and latency if exporter exposes them.

## Labels To Preserve

Keep `instance`, `job`, `mountpoint`, and `device` for filesystem metrics.
