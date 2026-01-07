# Memory Monitoring for Arrow Loading

## Why Monitor Both Heap and Pagecache?

When using Neo4j Arrow loader, both memory pools are important:

### Heap Memory (JVM)
- **Used for**: Arrow protocol buffers, query execution, transaction state, JVM runtime
- **Why it matters for Arrow**: Arrow operations use heap memory for:
  - Buffering Arrow data during transfer
  - Processing Arrow batches
  - Transaction management during loading
- **OOM Risk**: If heap is exhausted, Arrow operations will fail with OutOfMemoryError

### Pagecache (Off-Heap)
- **Used for**: Caching database pages (nodes, relationships, properties, indexes)
- **Why it matters**: 
  - Stores the actual graph data in memory
  - Critical for read performance
  - During loading, new data is written to pagecache
- **Capacity Risk**: If pagecache is full, data must be evicted to disk, causing performance degradation

## Current Implementation

The health checker monitors:
1. **Heap usage** (if JMX available) - checks before each load
2. **Pagecache usage** (if JMX available) - checks before each load
3. **Database count** - simple proxy for resource pressure

## Configuration

```yaml
orchestrator:
  heap_threshold_percent: 85      # Don't load if heap > 85%
  pagecache_threshold_percent: 90 # Don't load if pagecache > 90%
```

## JMX Availability

- **Enterprise Edition**: Full JMX access via `dbms.queryJmx`
- **Community Edition**: Limited or no JMX access
- **Graceful Degradation**: If JMX not available, health check falls back to database count only

## Recommendations

1. **Heap**: Set threshold to 85% - leave headroom for Arrow operations
2. **Pagecache**: Set threshold to 90% - allows some growth but prevents exhaustion
3. **Monitor Both**: Arrow loading uses heap, but data goes into pagecache
4. **Single Worker**: Load sequentially to avoid overwhelming either memory pool

