#!/usr/bin/env python3
"""
Setup demo data for blue/green deployment demo.
Copies source data to multiple customer/timestamp locations.

Source data is stored in source_data/ directory (tracked in git).
This script copies it to data/{customer}/{timestamp}/ for simulation.
"""
import shutil
import os
import sys
import yaml
from pathlib import Path

# Project root (one level up from scripts/)
project_root = Path(__file__).parent.parent

# Source data is in source_data/ directory (in project root)
SOURCE_DATA = project_root / "source_data"
SOURCE_NODES = SOURCE_DATA / "nodes"
SOURCE_RELATIONSHIPS = SOURCE_DATA / "relationships"

# Target base directory (in project root)
TARGET_BASE = project_root / "data"

# Demo configuration: 3 customers, 2 timestamps each
CUSTOMERS = ["customer1", "customer2", "customer3"]
TIMESTAMPS = [1767741427, 1767741527]  # Unix timestamps for demo


def copy_data(customer_id: str, timestamp: int):
    """Copy source data to customer/timestamp directory structure."""
    if not SOURCE_NODES.exists() or not SOURCE_RELATIONSHIPS.exists():
        raise FileNotFoundError(
            f"Source data not found. Expected:\n"
            f"  - {SOURCE_NODES}\n"
            f"  - {SOURCE_RELATIONSHIPS}\n"
            f"\nPlease ensure source_data/ directory exists with the required Parquet files."
        )
    
    target_dir = TARGET_BASE / customer_id / str(timestamp)
    target_nodes = target_dir / "nodes"
    target_relationships = target_dir / "relationships"
    
    # Create directories
    target_nodes.mkdir(parents=True, exist_ok=True)
    target_relationships.mkdir(parents=True, exist_ok=True)
    
    # Copy nodes
    print(f"Copying nodes for {customer_id}/{timestamp}...")
    for node_type_dir in SOURCE_NODES.iterdir():
        if node_type_dir.is_dir():
            target_node_type = target_nodes / node_type_dir.name
            target_node_type.mkdir(exist_ok=True)
            for parquet_file in node_type_dir.glob("*.parquet"):
                shutil.copy2(parquet_file, target_node_type / parquet_file.name)
    
    # Copy relationships
    print(f"Copying relationships for {customer_id}/{timestamp}...")
    for rel_type_dir in SOURCE_RELATIONSHIPS.iterdir():
        if rel_type_dir.is_dir():
            target_rel_type = target_relationships / rel_type_dir.name
            target_rel_type.mkdir(exist_ok=True)
            for parquet_file in rel_type_dir.glob("*.parquet"):
                shutil.copy2(parquet_file, target_rel_type / parquet_file.name)
    
    print(f"✅ Completed {customer_id}/{timestamp}")


def main():
    """Create all demo data copies."""
    print("Setting up blue/green deployment demo data...")
    print(f"Source: {SOURCE_DATA}")
    print(f"Target: {TARGET_BASE}")
    print(f"Creating {len(CUSTOMERS)} customers × {len(TIMESTAMPS)} timestamps = {len(CUSTOMERS) * len(TIMESTAMPS)} datasets\n")
    
    for customer_id in CUSTOMERS:
        for timestamp in TIMESTAMPS:
            copy_data(customer_id, timestamp)
    
    print(f"\n✅ Demo data setup complete!")
    print(f"Created {len(CUSTOMERS) * len(TIMESTAMPS)} datasets in {TARGET_BASE}")


if __name__ == "__main__":
    main()

