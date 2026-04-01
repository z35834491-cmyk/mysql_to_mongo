-- 分钟聚合长期存储（ReplacingMergeTree：同一 source_id+bucket_start 多版本时保留 ver 最新）
CREATE DATABASE IF NOT EXISTS traffic;

CREATE TABLE IF NOT EXISTS traffic.traffic_minute_rollup
(
    bucket_start DateTime,
    source_id String,
    requests UInt64,
    sum_latency_ms UInt64,
    count_latency UInt32,
    status_2xx UInt32,
    status_4xx UInt32,
    status_5xx UInt32,
    p50_ms Nullable(Float64),
    p95_ms Nullable(Float64),
    p99_ms Nullable(Float64),
    geo_counts String,
    top_paths String,
    ver DateTime
)
ENGINE = ReplacingMergeTree(ver)
ORDER BY (source_id, bucket_start);
