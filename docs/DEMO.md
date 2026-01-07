# Demonstration Guide

This guide shows you how to demonstrate the blue/green deployment system in two ways:

1. **Manual Demo** (`demo_workflow.py`) - Sequential, controlled, good for presentations
2. **Orchestrator Demo** (`orchestrator.py`) - Automatic, can be parallel, production-like

## Prerequisites

Before starting, ensure you have:
- Neo4j running with Arrow protocol (port 8491) and Bolt (port 7687)
- Demo data generated: `python scripts/setup_demo_data.py`
- Environment activated: `conda activate neo4j-blue-green-arrow-etl`

## Option 1: Manual Demo (Sequential)

**Best for**: Presentations, controlled demonstrations, understanding the flow

This approach loads databases **one at a time** sequentially, making it easy to follow and explain.

### Run the Complete Demo

```bash
python scripts/demo_workflow.py
```

### What It Does

1. **Phase 1 - Blue Deployments**: Loads initial databases for all 3 customers and switches aliases
   - `customer1-1767741427` → alias `customer1`
   - `customer2-1767741427` → alias `customer2`
   - `customer3-1767741427` → alias `customer3`

2. **Phase 2 - Green Deployments**: Loads new databases but **doesn't switch** aliases yet
   - `customer1-1767741527` (loaded, but alias still points to blue)
   - `customer2-1767741527` (loaded, but alias still points to blue)
   - `customer3-1767741527` (loaded, but alias still points to blue)

3. **Phase 3 - Cutover**: Switches all aliases to the green (latest) deployments
   - All aliases now point to the `-1767741527` databases

### Step-by-Step Manual Demo

If you want to demonstrate each step manually:

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

# 6. Query using alias (now points to green)
# In Neo4j Browser: USE customer1
```

### Verify the Demo

```bash
# List all databases and their status
python scripts/manage_aliases.py list-databases

# List aliases and their targets
python scripts/manage_aliases.py list-aliases
```

## Option 2: Orchestrator Demo (Automatic, Can Be Parallel)

**Best for**: Production-like scenarios, testing automatic behavior, parallel loading

The orchestrator can load databases **in parallel** if you configure multiple workers.

### Current Configuration

In `config.yaml`:
```yaml
orchestrator:
  num_workers: 1  # Sequential loading (one at a time)
```

**With 1 worker**: Loads one database at a time (sequential, safer for large loads)

**With multiple workers**: Can load multiple databases in parallel (faster, but more resource-intensive)

### Run Orchestrator (Sequential - 1 Worker)

```bash
# Uses config.yaml setting (1 worker = sequential)
python scripts/orchestrator.py
```

**The orchestrator runs continuously** until you stop it with `Ctrl+C`. It will:
- **Continuously watch** for new snapshots every 30 seconds
- Queue them for loading
- Load them one at a time (because num_workers=1)
- Automatically switch aliases to latest deployments
- Clean up old databases (keeps newest 2)

**To stop**: Press `Ctrl+C` in the terminal running the orchestrator.

### Run Orchestrator (Parallel - Multiple Workers)

```bash
# Override config to use 3 workers (parallel loading)
python scripts/orchestrator.py --workers 3
```

With 3 workers, the orchestrator can load **up to 3 databases simultaneously**:
- Worker 1 might load `customer1-1767741427`
- Worker 2 might load `customer2-1767741427`
- Worker 3 might load `customer3-1767741427`

All happening **at the same time**!

### Simulate New Snapshot Drop

**The orchestrator runs continuously**, so you can demonstrate live snapshot detection:

1. **Start the orchestrator** in one terminal (it will keep running):
   ```bash
   python scripts/orchestrator.py
   ```
   You'll see: `✅ Orchestrator started. Press Ctrl+C to stop.`

2. **In another terminal**, drop a new snapshot:
   ```bash
   # Create a new snapshot by copying existing one
   python scripts/simulate_snapshot.py --customer customer1
   
   # Or manually:
   cp -r data/customer1/1767741427 data/customer1/$(date +%s)
   ```

3. **Watch the orchestrator terminal** - within 30 seconds (or your scan_interval), you'll see:
   - `📦 Discovered new snapshot: customer1/1767763140`
   - `🔄 Worker X: Loading...`
   - `✅ Worker X: Loaded...`
   - `🔄 Worker X: Switching alias...`
   - `🗑️ Worker X: Dropping old database...`

The orchestrator will:
1. Detect the new snapshot within 30 seconds (at the next scan)
2. Queue it for loading
3. Load it when a worker is available
4. Switch alias if it's the latest
5. Clean up old databases

**You can drop multiple snapshots** while the orchestrator is running, and it will process them all!

### Monitor the Orchestrator

Watch the logs to see:
- Snapshot discovery
- Task queuing
- Worker activity
- Loading progress
- Health checks
- Cleanup operations

Logs are in `logs/blue_green_etl_YYYYMMDD_HHMMSS.log`

## Comparison: Sequential vs Parallel

### Sequential (num_workers: 1)
- ✅ **Safer**: Won't overwhelm Neo4j
- ✅ **Easier to follow**: One thing at a time
- ✅ **Better for demos**: Clear progression
- ❌ **Slower**: Takes longer to load all databases

### Parallel (num_workers: 3+)
- ✅ **Faster**: Multiple databases load simultaneously
- ✅ **Production-like**: Real-world scenarios
- ✅ **Efficient**: Better resource utilization
- ⚠️ **Resource-intensive**: Requires more memory/CPU
- ⚠️ **Harder to follow**: Multiple things happening at once

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

### Scenario 2: Automatic Orchestration Demo

**Goal**: Show automatic detection and loading

```bash
# 1. Start orchestrator with 2 workers (parallel) - it runs continuously
python scripts/orchestrator.py --workers 2
# Leave this running - it will keep watching for new snapshots

# 2. In another terminal, drop new snapshots (while orchestrator is running)
python scripts/simulate_snapshot.py --customer customer1
python scripts/simulate_snapshot.py --customer customer2
python scripts/simulate_snapshot.py --customer customer3

# 3. Watch orchestrator terminal automatically:
#    - Detect snapshots (within 30 seconds)
#    - Queue them
#    - Load them in parallel (2 at a time)
#    - Switch aliases
#    - Clean up old databases

# 4. Stop orchestrator when done: Press Ctrl+C in the orchestrator terminal
```

### Scenario 3: Health Check Demo

**Goal**: Show how orchestrator handles Neo4j under pressure

```bash
# 1. Start orchestrator (runs continuously)
python scripts/orchestrator.py
# Leave this running

# 2. Manually create many databases to trigger health check
# (Or load very large datasets)

# 3. In another terminal, try to drop new snapshot
python scripts/simulate_snapshot.py --customer customer1

# 4. Watch orchestrator terminal:
#    - Detect snapshot
#    - Queue it
#    - Health check fails (too many databases)
#    - Wait and retry later (after health_check_retry_delay)
#    - Eventually load when healthy

# 5. Stop orchestrator when done: Press Ctrl+C
```

## Tips for Presentations

1. **Start Simple**: Use `demo_workflow.py` for clear, sequential demonstration
2. **Show Aliases**: Use `python scripts/manage_aliases.py list-aliases` to show alias targets
3. **Query Examples**: Show queries work before and after cutover
4. **Parallel Demo**: Use `--workers 3` to show parallel loading capability
5. **Automatic Demo**: Use orchestrator to show production-like automation

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

