# Prefect Orchestrator - Quick Start

Get the Prefect orchestrator running in 3 commands.

## The 3 Commands

```bash
# 1. Start Prefect server (Terminal 1)
poetry run prefect server start

# 2. Run the supervisor process (Terminal 2)
python scripts/orchestrator_prefect.py --run

# 3. Simulate new data arriving (Terminal 3)
python scripts/simulate_snapshot.py --customer customer1
```

**That's it!** The orchestrator will automatically detect, load, and process the snapshot.

## Prerequisites

Before starting:
- Install dependencies: `poetry install`
- Set up demo data: `python scripts/setup_demo_data.py`
- Configure environment: `export NEO4J_PASSWORD=your_password`
- Ensure Neo4j is running (Enterprise Edition with Arrow protocol on port 8491)

## View in UI

Open `http://localhost:4200` to see:
- All workflow runs
- Task status and logs
- Retry attempts
- Execution timeline
- Visual workflow graphs

## What You Get

✅ **Production-grade UI** - Not demo-ware, but first-class orchestration  
✅ **Task history** - Complete audit trail  
✅ **Visual workflows** - See execution flow  
✅ **Better error handling** - Visual retry tracking  
✅ **Team collaboration** - Multiple users can monitor  

## Process Single Snapshot (Manual)

To process a specific snapshot manually:

```bash
python scripts/orchestrator_prefect.py \
  --customer customer1 \
  --timestamp 1767741527
```

See [PREFECT_SETUP.md](PREFECT_SETUP.md) for detailed documentation.

