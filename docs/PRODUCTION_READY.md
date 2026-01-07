# Production-Ready Orchestrator

The orchestrator has been enhanced with production-grade features for reliability, monitoring, and ease of use.

## ✅ New Features

### 1. **Retry Logic with Exponential Backoff**
- Failed loads are automatically retried (configurable: `max_retries`)
- Exponential backoff prevents overwhelming the system (2s, 4s, 8s delays)
- Configurable in `config.yaml`:
  ```yaml
  orchestrator:
    max_retries: 3  # Maximum retry attempts
    retry_backoff_base: 2  # Base for exponential backoff
  ```

### 2. **Statistics Tracking**
- Tracks all task metrics: discovered, completed, failed, retried
- Calculates success rate automatically
- Thread-safe statistics collection

### 3. **Status File for Monitoring**
- JSON status file: `orchestrator_status.json`
- Updated every 5 seconds
- Contains:
  - Uptime
  - Task statistics (discovered, completed, failed, retried)
  - Success rate
  - Queue size
  - Worker count
  - Last activity timestamp
  - Current status (running/stopping/stopped)

**Example status file:**
```json
{
  "uptime_seconds": 3600,
  "tasks_discovered": 10,
  "tasks_completed": 9,
  "tasks_failed": 1,
  "tasks_retried": 2,
  "success_rate": 90.0,
  "queue_size": 0,
  "workers": 1,
  "scan_interval": 30,
  "data_path": "/path/to/data",
  "last_activity": "2026-01-06T22:30:00",
  "status": "running"
}
```

### 4. **Configuration Validation**
- Validates all required config keys at startup
- Tests Neo4j connection before starting
- Verifies data paths exist
- Clear error messages for configuration issues

### 5. **Improved Error Handling**
- Detailed error logging with full tracebacks
- Error context preserved in tasks
- Distinguishes between retryable and permanent failures

### 6. **Graceful Shutdown**
- Configurable shutdown timeout (default: 5 minutes)
- Waits for current tasks to complete
- Updates status file during shutdown
- Clear shutdown progress messages

## Configuration

All new settings in `config.yaml`:

```yaml
orchestrator:
  num_workers: 1
  scan_interval: 30
  max_databases: 50
  heap_threshold_percent: 85
  pagecache_threshold_percent: 90
  health_check_retry_delay: 60
  max_retries: 3              # NEW: Max retry attempts for failed loads
  retry_backoff_base: 2        # NEW: Exponential backoff base (2s, 4s, 8s)
  shutdown_timeout: 300        # NEW: Shutdown timeout in seconds (5 minutes)
```

## Monitoring

### Status File
Monitor the orchestrator by reading the status file:
```bash
cat orchestrator_status.json | jq
```

### Logs
All activity is logged to `logs/blue_green_etl_YYYYMMDD_HHMMSS.log`

### Key Metrics to Monitor
- **Success Rate**: Should be > 95% in production
- **Queue Size**: Should stay low (< 10)
- **Tasks Failed**: Monitor for trends
- **Uptime**: Track service availability

## Error Recovery

### Automatic Retries
- Transient errors (network, temporary Neo4j issues) are automatically retried
- Exponential backoff prevents system overload
- Max retries configurable per environment

### Health Check Retries
- Health check failures are retried after `health_check_retry_delay`
- Tasks are requeued, not lost
- Prevents loading when Neo4j is under pressure

## Production Deployment

### Recommended Settings

**For Production:**
```yaml
orchestrator:
  num_workers: 2              # Parallel loading for throughput
  scan_interval: 30           # Balance between responsiveness and overhead
  max_retries: 3              # Retry transient failures
  retry_backoff_base: 2       # Exponential backoff
  shutdown_timeout: 600       # 10 minutes for large loads
```

**For High-Volume:**
```yaml
orchestrator:
  num_workers: 4              # More parallel workers
  scan_interval: 15           # Faster detection
  max_retries: 5              # More retries for reliability
```

**For Conservative/Safe:**
```yaml
orchestrator:
  num_workers: 1              # Sequential loading
  scan_interval: 60           # Less frequent scans
  max_retries: 2              # Fewer retries
```

## Monitoring Integration

### External Monitoring Tools
The status file can be consumed by:
- **Prometheus**: Use file-based exporter
- **Nagios/Icinga**: Check status file age and metrics
- **Custom Scripts**: Parse JSON for alerts

### Example Monitoring Script
```bash
#!/bin/bash
STATUS_FILE="orchestrator_status.json"

if [ ! -f "$STATUS_FILE" ]; then
    echo "CRITICAL: Status file not found"
    exit 2
fi

STATUS=$(cat "$STATUS_FILE" | jq -r '.status')
SUCCESS_RATE=$(cat "$STATUS_FILE" | jq -r '.success_rate')
QUEUE_SIZE=$(cat "$STATUS_FILE" | jq -r '.queue_size')

if [ "$STATUS" != "running" ]; then
    echo "WARNING: Orchestrator status is $STATUS"
    exit 1
fi

if (( $(echo "$SUCCESS_RATE < 95" | bc -l) )); then
    echo "WARNING: Success rate is ${SUCCESS_RATE}%"
    exit 1
fi

if [ "$QUEUE_SIZE" -gt 10 ]; then
    echo "WARNING: Queue size is $QUEUE_SIZE"
    exit 1
fi

echo "OK: Orchestrator healthy"
exit 0
```

## Trust & Reliability

### What Makes It Trustworthy

1. **Validation**: Config and connections validated at startup
2. **Retry Logic**: Automatic recovery from transient failures
3. **Health Checks**: Won't load when Neo4j is under pressure
4. **Statistics**: Full visibility into operations
5. **Graceful Shutdown**: Clean shutdown with task completion
6. **Error Context**: Detailed error information for debugging
7. **Status Monitoring**: Real-time status for external monitoring

### Best Practices

1. **Monitor the Status File**: Set up alerts on success rate and queue size
2. **Review Logs Regularly**: Check for error patterns
3. **Tune Retry Settings**: Adjust based on your failure patterns
4. **Set Appropriate Timeouts**: Balance between safety and responsiveness
5. **Use Health Checks**: Let the orchestrator protect Neo4j from overload

## Next Steps

See [PRODUCTION_IMPROVEMENTS.md](PRODUCTION_IMPROVEMENTS.md) for additional improvement ideas and roadmap.

