#!/usr/bin/env python3
"""
Simulate dropping a new snapshot by copying existing data to a new timestamp.
Useful for testing the orchestrator.
"""
import sys
import shutil
import time
from pathlib import Path
from blue_green_etl.config_loader import load_config

# Project root (one level up from scripts/)
project_root = Path(__file__).parent.parent

def simulate_snapshot(customer_id: str, source_timestamp: int, data_base_path: Path):
    """Create a new snapshot by copying an existing one with a new timestamp."""
    new_timestamp = int(time.time())
    
    source_path = data_base_path / customer_id / str(source_timestamp)
    target_path = data_base_path / customer_id / str(new_timestamp)
    
    if not source_path.exists():
        print(f"❌ Source snapshot not found: {source_path}")
        return None
    
    print(f"📦 Creating new snapshot for {customer_id}...")
    print(f"   Source: {source_path}")
    print(f"   Target: {target_path}")
    
    # Copy the snapshot
    shutil.copytree(source_path, target_path)
    
    print(f"✅ Created snapshot: {customer_id}/{new_timestamp}")
    print(f"   The orchestrator should detect this within 30 seconds")
    
    return new_timestamp


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Simulate dropping a new snapshot")
    parser.add_argument("--customer", required=True, help="Customer ID")
    parser.add_argument("--source-timestamp", type=int, help="Source timestamp to copy from")
    parser.add_argument("--data-path", default="data", help="Base data path")
    parser.add_argument("--config", default="config.yaml", help="Config file to read data path from")
    
    args = parser.parse_args()
    
    # Get data path from config if not specified
    if args.config:
        import yaml
        config_path = project_root / args.config
        if config_path.exists():
            config = load_config(config_path)
                # Resolve base_path - if relative, make it relative to project root
            base_path_str = config['dataset']['base_path']
            if Path(base_path_str).is_absolute():
                data_base_path = Path(base_path_str)
            else:
                data_base_path = project_root / base_path_str
        else:
            data_base_path = project_root / args.data_path
    else:
        data_base_path = project_root / args.data_path
    
    # Find latest existing timestamp if source not specified
    if not args.source_timestamp:
        customer_dir = data_base_path / args.customer
        if customer_dir.exists():
            timestamps = []
            for ts_dir in customer_dir.iterdir():
                if ts_dir.is_dir():
                    try:
                        timestamps.append(int(ts_dir.name))
                    except ValueError:
                        continue
            if timestamps:
                args.source_timestamp = max(timestamps)
                print(f"📋 Using latest existing timestamp: {args.source_timestamp}")
            else:
                print(f"❌ No existing snapshots found for {args.customer}")
                return
        else:
            print(f"❌ Customer directory not found: {customer_dir}")
            return
    
    simulate_snapshot(args.customer, args.source_timestamp, data_base_path)


if __name__ == "__main__":
    main()

