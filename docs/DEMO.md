# Demonstration Guide

This guide shows you how to demonstrate the blue/green deployment system. The **recommended approach** uses Prefect for production-grade observability.

## Core Demo (3 Commands)

This is the primary demo workflow:

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

Before starting, ensure you have:
- Neo4j Enterprise Edition running with Arrow protocol (port 8491) and Bolt (port 7687)
- Demo data generated: `python scripts/setup_demo_data.py`
- Environment configured: `export NEO4J_PASSWORD=your_password`
- Dependencies installed: `poetry install`

## Option 1: Prefect Orchestrator (Recommended) ⭐

**Best for**: Production-grade demos with full observability

### Quick Start

```bash
# Terminal 1: Start Prefect server
poetry run prefect server start

# Terminal 2: Run the supervisor
python scripts/orchestrator_prefect.py --run

# Terminal 3: Simulate new data
python scripts/simulate_snapshot.py --customer customer1
```

### What You'll See

1. **Prefect UI** (`http://localhost:4200`):
   - Visual workflow graphs
   - Task execution timeline
   - Real-time logs
   - Retry history
   - Error details

2. **Terminal Output**:
   - Snapshot discovery
   - Loading progress
   - Alias switching
   - Cleanup operations

### Configuration

The orchestrator processes **one snapshot at a time** by default (safer for Neo4j). This is controlled in `config.yaml`:

```yaml
orchestrator:
  max_concurrent_loads: 1  # Sequential processing (one at a time)
  scan_interval: 30        # Seconds between snapshot scans
```

### Simulate Multiple Snapshots

While the orchestrator is running, you can drop multiple snapshots:

```bash
# Terminal 3: Drop snapshots for different customers
python scripts/simulate_snapshot.py --customer customer1
python scripts/simulate_snapshot.py --customer customer2
python scripts/simulate_snapshot.py --customer customer3
```

The orchestrator will process them **one at a time** (sequential), ensuring Neo4j isn't overwhelmed.

### View in Prefect UI

Open `http://localhost:4200` to see:
- All workflow runs
- Task status (running, completed, failed)
- Execution logs
- Retry attempts
- Task dependencies

## Option 2: Manual Demo (Sequential)

**Best for**: Step-by-step demonstrations, understanding the flow

This approach loads databases **one at a time** sequentially, making it easy to follow and explain.

### Run the Complete Demo

```bash
python scripts/demo_workflow.py
```

### What It Does

1. **Phase 1 - Blue Deployments**: Loads initial databases for all 3 customers and switches aliases
2. **Phase 2 - Green Deployments**: Loads new databases but **doesn't switch** aliases yet
3. **Phase 3 - Cutover**: Switches all aliases to the green (latest) deployments

### Step-by-Step Manual Demo

```bash
# 1. Load blue deployment for customer1 and switch alias
python scripts/load_with_aliases.py --customer customer1 --timestamp 1767741427

# 2. Load green deployment for customer1 (don't switch yet)
python scripts/load_with_aliases.py --customer customer1 --timestamp 1767741527 --no-switch

# 3. Verify both databases exist
python scripts/manage_aliases.py list-databases

# 4. Check current alias target
python scripts/manage_aliases.py list-aliases

# 5. Switch alias to green (cutover)
python scripts/manage_aliases.py create customer1 customer1-1767741527
```

## Option 3: Original Orchestrator (Without Prefect)

**Best for**: Simple automation without UI

The original orchestrator (without Prefect) is still available. See [docs/ORCHESTRATOR.md](docs/ORCHESTRATOR.md) for details.

```bash
# Start the orchestrator (sequential - 1 worker)
python scripts/orchestrator.py

# In another terminal, simulate dropping a new snapshot
python scripts/simulate_snapshot.py --customer customer1
```

## Sequential Processing (Default)

The orchestrator processes snapshots **one at a time** by default. This is:
- ✅ **Safer**: Won't overwhelm Neo4j
- ✅ **Easier to follow**: One thing at a time
- ✅ **Better for demos**: Clear progression
- ✅ **Prevents memory issues**: Avoids "Arrow process aborted" errors

You can increase `max_concurrent_loads` in `config.yaml` if needed, but sequential (1) is recommended for demos.

## Demonstration Scenarios

### Scenario 1: Blue/Green Cutover Demo

**Goal**: Show how to deploy new version without downtime

```bash
# 1. Start with blue deployments active
python scripts/demo_workflow.py  # This loads blue and switches aliases

# 2. In another terminal, show queries work
# Neo4j Browser: USE customer1; MATCH (n) RETURN count(n)

# 3. Load green deployments (don't switch yet)
python scripts/load_with_aliases.py --customer customer1 --timestamp 1767741527 --no-switch

# 4. Verify green is loaded but not active
python scripts/manage_aliases.py list-aliases  # Still points to blue

# 5. Test green directly (without switching alias)
# Neo4j Browser: USE customer1-1767741527; MATCH (n) RETURN count(n)

# 6. Cutover: Switch alias to green
python scripts/manage_aliases.py create customer1 customer1-1767741527

# 7. Verify queries now hit green
# Neo4j Browser: USE customer1; MATCH (n) RETURN count(n)  # Now uses green

# 8. Clean up blue when ready
# (Orchestrator does this automatically, or use cleanup_demo.py)
```

### Scenario 2: Prefect Orchestration Demo

**Goal**: Show automatic detection and loading with full observability

```bash
# 1. Start Prefect server (Terminal 1)
poetry run prefect server start

# 2. Run orchestrator (Terminal 2) - it runs continuously
python scripts/orchestrator_prefect.py --run
# Leave this running - it will keep watching for new snapshots

# 3. In Terminal 3, drop new snapshots (while orchestrator is running)
python scripts/simulate_snapshot.py --customer customer1
python scripts/simulate_snapshot.py --customer customer2
python scripts/simulate_snapshot.py --customer customer3

# 4. Watch Prefect UI (http://localhost:4200):
#    - See snapshots detected (within 30 seconds)
#    - Watch tasks execute (health check, load, switch alias, cleanup)
#    - View logs and execution timeline
#    - See retry attempts if any

# 5. Stop orchestrator when done: Press Ctrl+C in Terminal 2
```

### Scenario 3: Health Check Demo

**Goal**: Show how orchestrator handles Neo4j under pressure

```bash
# 1. Start Prefect server (Terminal 1)
poetry run prefect server start

# 2. Run orchestrator (Terminal 2) - it runs continuously
python scripts/orchestrator_prefect.py --run
# Leave this running

# 3. Manually create many databases to trigger health check
# (Or load very large datasets)

# 4. In Terminal 3, try to drop new snapshot
python scripts/simulate_snapshot.py --customer customer1

# 5. Watch Prefect UI:
#    - See snapshot detected
#    - Watch health check task fail (too many databases)
#    - See retry logic wait and retry later
#    - Eventually load when healthy

# 6. Stop orchestrator when done: Press Ctrl+C in Terminal 2
```

## Tips for Presentations

1. **Start with Prefect**: Use the 3-command demo for production-grade observability
2. **Show Prefect UI**: Demonstrate the visual workflow and task execution
3. **Show Aliases**: Use `python scripts/manage_aliases.py list-aliases` to show alias targets
4. **Query Examples**: Show queries work before and after cutover
5. **Automatic Demo**: Show how orchestrator automatically detects and processes snapshots

## Troubleshooting

### Databases Not Loading
- Check Neo4j is running: `neo4j status`
- Check Arrow protocol: Port 8491 should be open
- Check logs: `logs/blue_green_etl_*.log`

### Health Checks Failing
- Too many databases: Reduce `max_databases` in config
- Memory pressure: Increase Neo4j heap size
- Reduce workers: Use `--workers 1` for sequential loading

### Aliases Not Switching
- Check alias exists: `python scripts/manage_aliases.py list-aliases`
- Verify database is latest timestamp for that customer
- Check logs for errors

## Next Steps

- See [ORCHESTRATOR.md](ORCHESTRATOR.md) for orchestrator details
- See [../README.md](../README.md) for full documentation
- See [SHARING.md](SHARING.md) for sharing instructions

