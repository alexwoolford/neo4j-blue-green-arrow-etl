# Prefect Setup Guide

This guide shows you how to set up and use the Prefect-based orchestrator for blue/green deployments.

## Overview

The Prefect orchestrator provides:
- ✅ **Production-grade UI** - First-class observability at `http://localhost:4200`
- ✅ **Task history** - Complete audit trail of all runs
- ✅ **Visual workflows** - See task dependencies and execution flow
- ✅ **Better error handling** - Visual retry tracking
- ✅ **Team collaboration** - Multiple users can monitor workflows

## Prerequisites

1. **Install Prefect** (already in `pyproject.toml`):
   ```bash
   poetry install
   ```

2. **Prefect Server** - Can run locally or use Prefect Cloud

## Quick Start (3 Commands)

This is the core demo workflow:

```bash
# 1. Start Prefect server (Terminal 1)
poetry run prefect server start

# 2. Run the supervisor process (Terminal 2)
python scripts/orchestrator_prefect.py --run

# 3. Simulate new data arriving (Terminal 3)
python scripts/simulate_snapshot.py --customer customer1
```

**What happens:**
- The orchestrator detects the new snapshot within 30 seconds
- It loads the data into Neo4j using Arrow protocol
- It switches the alias to the new database (if it's the latest)
- It cleans up old databases
- All activity is visible in the Prefect UI at `http://localhost:4200`

## Prerequisites

Before starting:
- Install dependencies: `poetry install`
- Set up demo data: `python scripts/setup_demo_data.py`
- Configure environment: `export NEO4J_PASSWORD=your_password`
- Ensure Neo4j is running (Enterprise Edition with Arrow protocol on port 8491)

## Architecture

### Flows

1. **`watch-for-snapshots`** - Long-running flow that scans for new snapshots
   - Runs continuously
   - Scans every 30 seconds (configurable)
   - Submits each snapshot as a separate workflow run

2. **`process-snapshot`** - Processes a single snapshot
   - Health check
   - Load database
   - Switch alias (if latest)
   - Cleanup old databases

3. **`process-single-snapshot`** - Manual trigger for single snapshot
   - Useful for testing or manual runs

### Tasks

- `check-neo4j-health` - Health check before loading
- `load-database` - Load database using Arrow protocol
- `check-is-latest` - Check if timestamp is latest for customer
- `switch-alias` - Switch database alias
- `cleanup-old-databases` - Remove old databases
- `scan-for-snapshots` - Scan for new snapshot directories

## Usage

### Starting the Orchestrator

**Recommended** (with Prefect server for full UI):

```bash
# Terminal 1: Start Prefect server
poetry run prefect server start

# Terminal 2: Run watcher
python scripts/orchestrator_prefect.py --run
```

**Alternative** (without Prefect server, for testing only):

```bash
python scripts/orchestrator_prefect.py --run
```

Note: Without Prefect server, you won't get the Prefect UI benefits.

### Monitoring

1. **Prefect UI**: Open `http://localhost:4200`
   - View all workflow runs
   - See task status (running, completed, failed)
   - View execution logs
   - See retry attempts
   - View task dependencies

2. **Flow Runs**: Click on any flow run to see:
   - Task execution timeline
   - Logs for each task
   - Retry history
   - Error details

### Processing Snapshots

**Automatic**: The watcher flow automatically detects and processes new snapshots when you run `python scripts/simulate_snapshot.py --customer customer1`.

**Manual**: Process a specific snapshot manually:

```bash
python scripts/orchestrator_prefect.py \
  --customer customer1 \
  --timestamp 1767741527
```

## Configuration

The Prefect orchestrator uses the same `config.yaml` as the original orchestrator:

```yaml
neo4j:
  host: localhost
  arrow_port: 8491
  bolt_port: 7687
  user: neo4j
  password: ${NEO4J_PASSWORD}
  tls: false
  concurrency: 10

dataset:
  base_path: 'data'

orchestrator:
  max_concurrent_loads: 1  # Sequential processing (one at a time, safer for Neo4j)
  scan_interval: 30  # Seconds between snapshot scans
  max_databases: 50
  heap_threshold_percent: 85
  pagecache_threshold_percent: 90
  max_retries: 3  # Prefect handles retries
  retry_backoff_base: 2
```

## Prefect UI Features

### Dashboard
- Overview of all flows
- Recent runs
- Success/failure rates
- Active runs

### Flow Runs
- Visual workflow graph
- Task execution timeline
- Logs for each task
- Retry history
- Error details

### Task History
- Complete audit trail
- Search and filter
- Export capabilities

## Comparison: Original vs Prefect Orchestrator

| Feature | Original Orchestrator | Prefect Orchestrator |
|---------|---------------------|---------------------|
| UI | JSON status file | Production-grade web UI |
| Observability | Logs only | Visual workflows, task history |
| Retry Logic | Custom implementation | Built-in with visualization |
| Task History | No | Complete audit trail |
| Team Collaboration | No | Multiple users can monitor |
| Error Handling | Custom | Built-in with retry tracking |
| Setup | Simple (just run) | Requires Prefect server |

## Troubleshooting

### Prefect Server Won't Start

```bash
# Check if port 4200 is in use
lsof -i :4200

# Use different port
poetry run prefect server start --port 4201
```

### Prefect Command Not Found

```bash
# Use poetry run to access prefect
poetry run prefect server start

# Or activate the environment first
poetry shell
prefect server start
```

### Flows Not Appearing in UI

```bash
# Make sure you're running the watcher
python scripts/orchestrator_prefect.py --run

# Check Prefect server is running
curl http://localhost:4200/api/health
```

## Migration from Original Orchestrator

The Prefect orchestrator uses the same underlying functions:
- `load_database()` - Same function
- `set_alias()` - Same function
- `Neo4jHealthChecker` - Same class

**No changes needed to core logic** - Prefect just wraps it in workflows.

## Next Steps

1. **Start Prefect server**: `poetry run prefect server start`
2. **Run watcher**: `python scripts/orchestrator_prefect.py --run`
3. **Open UI**: `http://localhost:4200`
4. **Drop a snapshot**: `python scripts/simulate_snapshot.py --customer customer1`

Watch it appear in the Prefect UI! 🎉

