#!/usr/bin/env python3
"""
Cleanup script for blue/green deployment demo.
Drops aliases and databases created by the demo.
"""
import sys
import yaml
import argparse
from pathlib import Path
import neo4j

# Add project root and src directory to path for imports
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(project_root))

from blue_green_etl.neo4j_utils import get_driver
from blue_green_etl.config_loader import load_config

# Configuration
CUSTOMERS = ["customer1", "customer2", "customer3"]
TIMESTAMPS = [1767741427, 1767741527]


def drop_alias(alias_name: str, driver):
    """Drop a database alias."""
    try:
        with driver.session(database="system") as session:
            session.run(f"DROP ALIAS {alias_name} FOR DATABASE")
        print(f"  ✅ Dropped alias: {alias_name}")
        return True
    except Exception as e:
        # Alias might not exist
        if "not found" in str(e).lower() or "does not exist" in str(e).lower():
            print(f"  ⚠️  Alias {alias_name} does not exist (skipping)")
        else:
            print(f"  ❌ Error dropping alias {alias_name}: {e}")
        return False


def drop_database(db_name: str, driver):
    """Drop a database."""
    try:
        with driver.session(database="system") as session:
            session.run(f"DROP DATABASE `{db_name}` IF EXISTS")
        print(f"  ✅ Dropped database: {db_name}")
        return True
    except Exception as e:
        print(f"  ❌ Error dropping database {db_name}: {e}")
        return False


def cleanup_all(config: dict, drop_aliases: bool = True, drop_databases: bool = True):
    """Clean up all demo aliases and databases."""
    driver = get_driver(config)
    
    try:
        print("="*70)
        print("CLEANUP: Blue/Green Deployment Demo")
        print("="*70)
        
        if drop_aliases:
            print("\n📋 Dropping aliases...")
            for customer_id in CUSTOMERS:
                drop_alias(customer_id, driver)
        
        if drop_databases:
            print("\n🗄️  Dropping databases...")
            for customer_id in CUSTOMERS:
                for timestamp in TIMESTAMPS:
                    db_name = f"{customer_id}-{timestamp}"
                    drop_database(db_name, driver)
        
        print("\n" + "="*70)
        print("✅ Cleanup complete!")
        print("="*70)
        
    finally:
        driver.close()


def cleanup_customer(config: dict, customer_id: str, drop_alias_flag: bool = True):
    """Clean up a specific customer's aliases and databases."""
    driver = get_driver(config)
    
    try:
        print(f"\n🧹 Cleaning up {customer_id}...")
        
        if drop_alias_flag:
            drop_alias(customer_id, driver)
        
        for timestamp in TIMESTAMPS:
            db_name = f"{customer_id}-{timestamp}"
            drop_database(db_name, driver)
        
        print(f"✅ {customer_id} cleanup complete")
        
    finally:
        driver.close()


def main():
    parser = argparse.ArgumentParser(description="Cleanup blue/green deployment demo")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--customer", help="Clean up specific customer only")
    parser.add_argument("--no-aliases", action="store_true", help="Don't drop aliases")
    parser.add_argument("--no-databases", action="store_true", help="Don't drop databases")
    parser.add_argument("--list", action="store_true", help="List aliases and databases only")
    
    args = parser.parse_args()
    
    # Load config (from project root)
    config_path = project_root / args.config
    config = load_config(config_path)
    
    driver = get_driver(config)
    
    if args.list:
        print("\n📋 Current aliases:")
        print("-" * 70)
        try:
            with driver.session(database="system") as session:
                result = session.run("SHOW ALIASES FOR DATABASE")
                records = list(result)
                if not records:
                    print("  (none)")
                else:
                    for record in records:
                        print(f"  {record.get('name', ''):20} -> {record.get('database', '')}")
        except Exception as e:
            print(f"  Error: {e}")
        
        print("\n🗄️  Demo databases:")
        print("-" * 70)
        try:
            with driver.session(database="system") as session:
                result = session.run("SHOW DATABASES YIELD name WHERE name <> 'system' AND name <> 'neo4j' RETURN name ORDER BY name")
                records = list(result)
                demo_dbs = [r['name'] for r in records if any(c in r['name'] for c in CUSTOMERS)]
                if not demo_dbs:
                    print("  (none)")
                else:
                    for db_name in demo_dbs:
                        print(f"  {db_name}")
        except Exception as e:
            print(f"  Error: {e}")
        
        driver.close()
        return
    
    try:
        if args.customer:
            cleanup_customer(config, args.customer, not args.no_aliases)
        else:
            cleanup_all(config, not args.no_aliases, not args.no_databases)
    finally:
        driver.close()


if __name__ == "__main__":
    main()

