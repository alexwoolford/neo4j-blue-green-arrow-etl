# Orchestration Service

The orchestrator provides a production-ready service for managing blue/green deployments automatically.

> **Note**: The **Prefect orchestrator** (`orchestrator_prefect.py`) is recommended for demos and production use. It provides a production-grade UI and full observability. See [docs/PREFECT_SETUP.md](PREFECT_SETUP.md) for the Prefect-based orchestrator.

This document describes the original orchestrator (`orchestrator.py`) which runs without Prefect.

## Features

1. **File Watcher**: Continuously monitors for new snapshot directories
2. **Queue Management**: Queues loading tasks to avoid overwhelming the instance
3. **Concurrency Control**: Configurable number of worker threads
4. **Health Checks**: Verifies Neo4j is healthy before loading
5. **Automatic Cleanup**: Keeps newest 2 databases per customer, removes older ones
6. **Auto-Switch**: Automatically switches aliases to latest deployments

## How It Works

```
┌─────────────┐
│ File Watcher│───scans every 30s───┐
└─────────────┘                      │
                                     ▼
                              ┌──────────────┐
                              │  Task Queue  │
                              └──────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
              ┌──────────┐    ┌──────────┐    ┌──────────┐
              │ Worker 1 │    │ Worker 2 │    │ Worker N │
              └──────────┘    └──────────┘    └──────────┘
                    │                │                │
                    └────────────────┼────────────────┘
                                     ▼
                              ┌──────────────┐
                              │ Load & Switch│
                              │   & Cleanup  │
                              └──────────────┘
```

## Usage

### Start the Orchestrator

```bash
python scripts/orchestrator.py
```

**The orchestrator runs continuously** until you stop it with `Ctrl+C`. It will keep watching for new snapshots and processing them automatically.

**To stop**: Press `Ctrl+C` in the terminal running the orchestrator.

### With Custom Settings

```bash
python scripts/orchestrator.py --workers 3 --scan-interval 60
```

This starts the orchestrator with 3 workers and scans every 60 seconds instead of 30.

### Simulate Snapshot Drop

**While the orchestrator is running**, create a new snapshot directory in another terminal:

```bash
# Copy data to a new timestamp
cp -r data/customer1/1767741427 data/customer1/$(date +%s)

# Or use the helper script:
python scripts/simulate_snapshot.py --customer customer1
```

**The orchestrator will automatically** (within 30 seconds, or your configured scan_interval):
1. Detect the new snapshot
2. Queue it for loading
3. Load it when a worker is available
4. Switch alias if it's the latest
5. Clean up old databases

**You can drop multiple snapshots** while the orchestrator is running - it will process them all in order!

## Configuration

In `config.yaml`:

```yaml
orchestrator:
  num_workers: 1          # Concurrent load workers (1 = sequential, safer for large loads)
  scan_interval: 30        # Seconds between scans
  max_databases: 50       # Health check threshold
```

## Benefits for Production

### Addresses OOM Issues

- **Arrow Loader**: Much more efficient than transactional loading
- **Drip-Feed**: Controlled concurrency prevents overwhelming the instance
- **Queue Management**: Tasks wait instead of all running at once

### Addresses Long Load Times

- **Arrow Performance**: Significantly faster than traditional methods
- **Parallel Loading**: Multiple workers can process different customers
- **Health Checks**: Prevents loading when system is under stress

### Automatic Management

- **No Manual Intervention**: Just drop snapshots, orchestrator handles the rest
- **Automatic Cleanup**: Old databases removed automatically
- **Latest Always Active**: Aliases automatically point to newest deployment

## Example Workflow

1. **ETL Process** creates snapshot: `data/customer1/1767741527/`
2. **Orchestrator** detects it within 30 seconds
3. **Worker** picks up task when available
4. **Health Check** verifies Neo4j can handle the load
5. **Load** using Arrow (fast, efficient)
6. **Switch** alias to new database (if latest)
7. **Cleanup** old databases (keep newest 2)

## Monitoring

The orchestrator logs all activities:
- Snapshot discovery
- Task queuing
- Loading progress
- Health check results
- Cleanup operations

## Next Steps: Prefect Integration

For better visibility and monitoring, this can be enhanced with Prefect:

- **Flow Visualization**: See the entire pipeline as a DAG
- **Task Monitoring**: Track each load task
- **Retry Logic**: Automatic retries on failure
- **Scheduling**: Built-in scheduling capabilities
- **Dashboard**: Web UI for monitoring

