# JVM Core Metrics

## Core

- Heap usage percent: memory pressure. Use `jvm_memory`.
- Old generation usage if available: long-lived object pressure. Use `jvm_memory`.
- GC pause time rate: application pause risk. Use `jvm_gc`.
- Full GC count or rate: severe memory pressure signal. Use `jvm_gc`.
- Live thread count: thread leak or traffic pressure signal. Use `threshold_trend`.

## Secondary

- Non-heap/metaspace usage.
- Class loading/unloading churn.
- Direct buffer usage if exported.

## Interpretation Notes

Heap usage can rise and fall because of GC, so persistent post-GC growth is more meaningful than a single high sample. If only generic heap usage is available, report trend confidence as medium.
