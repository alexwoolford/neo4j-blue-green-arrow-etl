#!/usr/bin/env python3
"""
Utility script for managing database aliases.
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


def list_aliases(config: dict):
    """List all database aliases."""
    driver = get_driver(config)
    try:
        with driver.session(database="system") as session:
            # SHOW ALIASES FOR DATABASE shows all aliases
            result = session.run("SHOW ALIASES FOR DATABASE")
            records = list(result)
            if not records:
                print("No aliases found.")
            else:
                print("\nCurrent aliases:")
                print("-" * 60)
                for record in records:
                    # SHOW ALIASES FOR DATABASE returns: name, database, location
                    alias_name = record.get('name', '')
                    target_db = record.get('database', '')
                    print(f"  {alias_name:20} -> {target_db}")
            return records
    finally:
        driver.close()


def create_alias(alias_name: str, target_database: str, config: dict):
    """Create or update a database alias."""
    driver = get_driver(config)
    try:
        with driver.session(database="system") as session:
            # Try to drop if exists (ignore error if it doesn't exist)
            try:
                session.run(f"DROP ALIAS {alias_name} FOR DATABASE")
            except Exception:
                pass  # Alias doesn't exist, that's fine
            
            # Create new alias (use backticks for database names with dashes)
            session.run(f"CREATE ALIAS {alias_name} FOR DATABASE `{target_database}`")
        
        print(f"✅ Alias '{alias_name}' -> '{target_database}'")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        driver.close()


def drop_alias(alias_name: str, config: dict):
    """Drop a database alias."""
    driver = get_driver(config)
    try:
        with driver.session(database="system") as session:
            session.run(f"DROP ALIAS {alias_name} FOR DATABASE")
        print(f"✅ Alias '{alias_name}' dropped")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        driver.close()


def list_databases(config: dict):
    """List all databases."""
    driver = get_driver(config)
    try:
        with driver.session(database="system") as session:
            result = session.run("""
                SHOW DATABASES
                YIELD name, currentStatus, default
                WHERE name <> 'system'
                RETURN name, currentStatus, default
                ORDER BY name
            """)
            records = list(result)
            if not records:
                print("No databases found.")
            else:
                print("\nDatabases:")
                print("-" * 60)
                for record in records:
                    default = " (default)" if record['default'] else ""
                    print(f"  {record['name']:30} {record['currentStatus']}{default}")
            return records
    finally:
        driver.close()


def main():
    parser = argparse.ArgumentParser(description="Manage Neo4j database aliases")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # List aliases
    subparsers.add_parser("list-aliases", help="List all aliases")
    
    # List databases
    subparsers.add_parser("list-databases", help="List all databases")
    
    # Create alias
    create_parser = subparsers.add_parser("create", help="Create an alias")
    create_parser.add_argument("alias", help="Alias name")
    create_parser.add_argument("database", help="Target database name")
    
    # Drop alias
    drop_parser = subparsers.add_parser("drop", help="Drop an alias")
    drop_parser.add_argument("alias", help="Alias name")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Load config (from project root)
    config_path = project_root / args.config
    config = load_config(config_path)
    
    # Execute command
    if args.command == "list-aliases":
        list_aliases(config)
    elif args.command == "list-databases":
        list_databases(config)
    elif args.command == "create":
        create_alias(args.alias, args.database, config)
    elif args.command == "drop":
        drop_alias(args.alias, config)


if __name__ == "__main__":
    main()

