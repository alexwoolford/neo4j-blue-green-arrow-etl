#!/usr/bin/env python3
"""
Load data using Arrow protocol and manage database aliases for blue/green deployments.

This script:
1. Loads data to a timestamped database (e.g., customer1-1767741427)
2. Creates/updates an alias pointing to that database (e.g., customer1 -> customer1-1767741427)
3. Supports blue/green deployment pattern
"""
import sys
import yaml
import time
import logging
from pathlib import Path
from typing import Optional

# Add project root and src directory to path for imports
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(project_root))

# Import from package
from blue_green_etl import neo4j_pq as npq
from blue_green_etl import neo4j_arrow_client as na
from blue_green_etl.neo4j_utils import get_driver
from blue_green_etl.logging_config import get_logger
from blue_green_etl.config_loader import load_config
import neo4j

# Set up logging
logger = get_logger(__name__)


def load_database(
    customer_id: str,
    timestamp: int,
    config: dict,
    data_path: Path
) -> dict:
    """
    Load data to a timestamped database using Arrow protocol.
    
    Returns:
        dict with node_count and relationship_count
    """
    # Database name is customer_id + timestamp (use dash, not underscore - Neo4j doesn't allow underscores)
    db_name = f"{customer_id}-{timestamp}"
    
    logger.info(f"{'='*60}")
    logger.info(f"Loading {customer_id} data to database: {db_name}")
    logger.info(f"{'='*60}")
    
    # First, try to drop existing database if it exists (using Neo4j driver directly)
    # This cleans up any stuck Arrow processes associated with the database
    # We use the Neo4j driver directly (not GDS) because GDS can't run in system database
    logger.info(f"Checking for existing database...")
    driver = get_driver(config)
    try:
        with driver.session(database="system") as session:
            # Check if database exists
            result = session.run(f"SHOW DATABASES YIELD name WHERE name = '{db_name}' RETURN name")
            if result.single():
                logger.info(f"Dropping existing database {db_name} (this will clean up any stuck Arrow processes)...")
                
                # First, check if there are any aliases pointing to this database and drop them
                alias_result = session.run("SHOW ALIASES FOR DATABASE")
                for record in alias_result:
                    alias_name = record.get('name', '')
                    alias_target = record.get('database', '')
                    if alias_target == db_name:
                        logger.info(f"  Dropping alias {alias_name} that points to {db_name}...")
                        try:
                            session.run(f"DROP ALIAS {alias_name} FOR DATABASE")
                            logger.info(f"  ✅ Dropped alias {alias_name}")
                        except Exception as e:
                            logger.warning(f"  ⚠️  Could not drop alias {alias_name}: {e}")
                
                # Now drop the database (use backticks around database name since it contains dashes)
                session.run(f"DROP DATABASE `{db_name}` IF EXISTS")
                # Give Neo4j a moment to clean up
                time.sleep(2)  # Increased wait time for cleanup
                logger.info(f"✅ Dropped existing database")
    except Exception as e:
        logger.info(f"Note: Could not check/drop database (may not exist): {e}")
    finally:
        driver.close()
    
    # Create Arrow client
    client = na.Neo4jArrowClient(
        host=config['neo4j']['host'],
        port=config['neo4j']['arrow_port'],
        user=config['neo4j']['user'],
        password=config['neo4j']['password'],
        tls=config['neo4j']['tls'],
        concurrency=config['neo4j']['concurrency'],
        database=db_name
    )
    
    # Abort any existing stuck Arrow process for this database
    # (Silently handle if no process exists)
    try:
        client.abort(db_name)
    except Exception:
        pass  # No process to abort, that's fine
    
    # Create database
    import_config = {
        "name": db_name,
        "concurrency": config['neo4j']['concurrency'],
        "high_io": True,
        "force": True,
        "record_format": "aligned",
        "id_property": "id",
        "id_type": "STRING"
    }
    
    msg = client.create_database(config=import_config)
    logger.info(f"✅ Database {db_name} created")
    
    # Load nodes
    nodes_path = data_path / "nodes"
    logger.info(f"Loading nodes from {nodes_path}...")
    node_results, node_timing = npq.fan_out(
        client,
        str(nodes_path),
        config['worker']['arrow_table_size'],
        config['worker']['concurrency']
    )
    
    total_nodes = sum([x["rows"] for x in node_results])
    total_bytes = sum([x["bytes"] for x in node_results])
    node_rate = int(total_nodes / node_timing) if node_timing > 0 else 0
    data_rate = int(total_bytes / node_timing) >> 20 if node_timing > 0 else 0
    
    logger.info(f"✅ Loaded {total_nodes:,} nodes in {round(node_timing, 2)}s "
                f"(~{node_rate:,} nodes/s, ~{data_rate} MiB/s)")
    
    # Signal nodes done
    nodes_msg = client.nodes_done()
    node_count = nodes_msg['node_count']
    logger.info(f"✅ Nodes complete: {node_count:,} nodes")
    
    # Load relationships
    relationships_path = data_path / "relationships"
    logger.info(f"Loading relationships from {relationships_path}...")
    edge_results, edge_timing = npq.fan_out(
        client,
        str(relationships_path),
        config['worker']['arrow_table_size'],
        config['worker']['concurrency']
    )
    
    total_edges = sum([x["rows"] for x in edge_results])
    total_bytes = sum([x["bytes"] for x in edge_results])
    edge_rate = int(total_edges / edge_timing) if edge_timing > 0 else 0
    data_rate = int(total_bytes / edge_timing) >> 20 if edge_timing > 0 else 0
    
    logger.info(f"✅ Loaded {total_edges:,} relationships in {round(edge_timing, 2)}s "
                f"(~{edge_rate:,} edges/s, ~{data_rate} MiB/s)")
    
    # Signal edges done
    edges_msg = client.edges_done()
    relationship_count = edges_msg['relationship_count']
    logger.info(f"✅ Relationships complete: {relationship_count:,} relationships")
    
    # Cleanup
    client.client = None
    
    return {
        "database": db_name,
        "node_count": node_count,
        "relationship_count": relationship_count
    }


def set_alias(
    alias_name: str,
    target_database: str,
    config: dict
) -> bool:
    """
    Set a database alias to point to a target database.
    Uses Neo4j driver directly (not GDS) because GDS can't run in system database.
    """
    logger.info(f"Setting alias '{alias_name}' -> '{target_database}'...")
    
    # Use Neo4j driver directly for alias management (GDS can't run in system database)
    neo4j_url = f"bolt://{config['neo4j']['host']}:{config['neo4j']['bolt_port']}"
    driver = neo4j.GraphDatabase.driver(
        neo4j_url,
        auth=neo4j.basic_auth(config['neo4j']['user'], config['neo4j']['password'])
    )
    
    try:
        with driver.session(database="system") as session:
            # Try to drop alias if it exists (ignore error if it doesn't exist)
            try:
                session.run(f"DROP ALIAS {alias_name} FOR DATABASE")
            except Exception:
                pass  # Alias doesn't exist, that's fine
            
            # Create new alias (use backticks for database names with dashes)
            create_query = f"CREATE ALIAS {alias_name} FOR DATABASE `{target_database}`"
            session.run(create_query)
        
        logger.info(f"✅ Alias '{alias_name}' now points to '{target_database}'")
        return True
    except Exception as e:
        logger.error(f"❌ Error setting alias: {e}")
        return False
    finally:
        driver.close()


def load_and_switch(
    customer_id: str,
    timestamp: int,
    config: dict,
    data_base_path: Path,
    switch_alias: bool = True
) -> dict:
    """
    Load data to timestamped database and optionally switch the alias.
    
    Args:
        customer_id: Customer identifier (e.g., "customer1")
        timestamp: Timestamp for this deployment (e.g., 1767741427)
        config: Configuration dictionary
        data_base_path: Base path containing customer/timestamp directories
        switch_alias: If True, switch the alias to point to the new database
    
    Returns:
        dict with loading results
    """
    data_path = data_base_path / customer_id / str(timestamp)
    
    if not data_path.exists():
        raise FileNotFoundError(f"Data path not found: {data_path}")
    
    # Load the database
    result = load_database(customer_id, timestamp, config, data_path)
    
    # Switch alias if requested
    if switch_alias:
        set_alias(customer_id, result["database"], config)
    
    return result


def main():
    """Main entry point for loading with aliases."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Load data with blue/green deployment aliases")
    parser.add_argument("--customer", required=True, help="Customer ID (e.g., customer1)")
    parser.add_argument("--timestamp", type=int, required=True, help="Timestamp (e.g., 1767741427)")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--data-path", default="data", help="Base data path")
    parser.add_argument("--no-switch", action="store_true", help="Don't switch alias after loading")
    
    args = parser.parse_args()
    
    # Load config (from project root)
    config_path = project_root / args.config
    config = load_config(config_path)
    
    # Data path (from project root)
    data_base_path = project_root / args.data_path
    
    # Load and switch
    result = load_and_switch(
        args.customer,
        args.timestamp,
        config,
        data_base_path,
        switch_alias=not args.no_switch
    )
    
    logger.info(f"{'='*60}")
    logger.info(f"✅ Complete! Database: {result['database']}")
    logger.info(f"   Nodes: {result['node_count']:,}")
    logger.info(f"   Relationships: {result['relationship_count']:,}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    main()

