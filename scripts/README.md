# Scripts Directory

This directory contains all executable scripts for the blue/green deployment demo.

## Available Scripts

### Data Setup
- **`setup_demo_data.py`** - Generates demo data by copying source Parquet files to multiple customer/timestamp locations

### Data Loading
- **`load_with_aliases.py`** - Loads data to Neo4j and manages database aliases
- **`orchestrator.py`** - Production-ready orchestration service that watches for new snapshots

### Alias Management
- **`manage_aliases.py`** - Create, list, and manage database aliases
- **`cleanup_demo.py`** - Clean up demo databases and aliases

### Demo & Testing
- **`demo_workflow.py`** - Complete demo workflow showing blue/green deployment
- **`simulate_snapshot.py`** - Simulate dropping a new snapshot for testing

## Usage

All scripts should be run from the **project root** directory:

```bash
# From project root
python scripts/setup_demo_data.py
python scripts/load_with_aliases.py --customer customer1 --timestamp 1767741427
python scripts/orchestrator.py
```

## Quick Reference

```bash
# Setup demo data
python scripts/setup_demo_data.py

# Load a database
python scripts/load_with_aliases.py --customer customer1 --timestamp 1767741427

# Run complete demo
python scripts/demo_workflow.py

# Start orchestrator
python scripts/orchestrator.py

# Manage aliases
python scripts/manage_aliases.py list-aliases
python scripts/manage_aliases.py create customer1 customer1-1767741427

# Cleanup
python scripts/cleanup_demo.py
```

