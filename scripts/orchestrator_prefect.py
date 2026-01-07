#!/usr/bin/env python3
"""
Prefect-based orchestration service for blue/green deployments.

This provides a production-grade UI and observability for the blue/green
deployment system using Prefect workflows.

Usage:
    1. Start Prefect server: poetry run prefect server start
    2. Run watcher: python scripts/orchestrator_prefect.py --run
    3. Or serve flows: python scripts/orchestrator_prefect.py --serve
    4. View in UI: http://localhost:4200
"""
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime

# Add project root and src directory to path for imports
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(project_root))

from prefect import flow, task
from prefect.tasks import task_input_hash
import threading

from scripts.load_with_aliases import load_database, set_alias
from scripts.orchestrator import Neo4jHealthChecker
from blue_green_etl.logging_config import setup_logging, get_logger
from blue_green_etl.config_loader import load_config
from blue_green_etl.neo4j_utils import get_driver

# Set up logging
setup_logging()
logger = get_logger(__name__)


@task(
    name="check-neo4j-health",
    retries=0,
    log_prints=True
)
def check_health_task(config: dict) -> Tuple[bool, str]:
    """
    Check Neo4j health before loading.
    
    Returns:
        (is_healthy, message)
    """
    checker = Neo4jHealthChecker(config)
    try:
        is_healthy, message = checker.check_health()
        return is_healthy, message
    finally:
        checker.close()


@task(
    name="load-database",
    retries=3,
    retry_delay_seconds=2,
    log_prints=True,
    cache_key_fn=task_input_hash,
    cache_expiration=None  # Don't cache - always load fresh
)
def load_database_task(
    customer_id: str,
    timestamp: int,
    config: dict,
    data_path: Path
) -> dict:
    """
    Load a database using Arrow protocol.
    
    This wraps the existing load_database function as a Prefect task.
    """
    logger.info(f"Loading database for {customer_id}/{timestamp}")
    result = load_database(customer_id, timestamp, config, data_path)
    logger.info(f"✅ Loaded {result['database']}: {result['node_count']:,} nodes, {result['relationship_count']:,} relationships")
    return result


@task(
    name="switch-alias",
    retries=2,
    retry_delay_seconds=1,
    log_prints=True
)
def switch_alias_task(
    alias_name: str,
    target_database: str,
    config: dict
) -> bool:
    """
    Switch a database alias to point to a target database.
    """
    logger.info(f"Switching alias '{alias_name}' -> '{target_database}'")
    result = set_alias(alias_name, target_database, config)
    return result


@task(
    name="check-is-latest",
    log_prints=True
)
def check_is_latest_task(
    customer_id: str,
    timestamp: int,
    config: dict
) -> bool:
    """
    Check if this timestamp is the latest for this customer.
    """
    driver = get_driver(config)
    try:
        with driver.session(database="system") as session:
            result = session.run(
                f"SHOW DATABASES YIELD name WHERE name STARTS WITH '{customer_id}-' RETURN name"
            )
            customer_timestamps = []
            for record in result:
                db_name = record['name']
                try:
                    db_timestamp = int(db_name.split('-')[-1])
                    customer_timestamps.append(db_timestamp)
                except (ValueError, IndexError):
                    continue
            
            is_latest = timestamp == max(customer_timestamps) if customer_timestamps else True
            logger.info(f"Timestamp {timestamp} is {'latest' if is_latest else 'not latest'} for {customer_id}")
            return is_latest
    finally:
        driver.close()


@task(
    name="cleanup-old-databases",
    log_prints=True
)
def cleanup_old_databases_task(
    customer_id: str,
    keep_count: int,
    config: dict
) -> int:
    """
    Remove old databases, keeping only the newest N.
    
    Returns:
        Number of databases cleaned up
    """
    driver = get_driver(config)
    cleaned_count = 0
    try:
        with driver.session(database="system") as session:
            # Get all databases for this customer with their timestamps
            result = session.run(
                f"SHOW DATABASES YIELD name WHERE name STARTS WITH '{customer_id}-' RETURN name"
            )
            databases = []
            for record in result:
                db_name = record['name']
                try:
                    db_timestamp = int(db_name.split('-')[-1])
                    databases.append((db_timestamp, db_name))
                except (ValueError, IndexError):
                    continue
            
            # Sort by timestamp (newest first)
            databases.sort(reverse=True)
            
            # Drop databases beyond keep_count
            for db_timestamp, db_name in databases[keep_count:]:
                # Check if alias points to it first
                alias_result = session.run("SHOW ALIASES FOR DATABASE")
                has_alias = False
                for alias_record in alias_result:
                    if alias_record.get('database') == db_name:
                        has_alias = True
                        break
                
                if not has_alias:
                    logger.info(f"🗑️  Dropping old database {db_name}")
                    try:
                        session.run(f"DROP DATABASE `{db_name}` IF EXISTS")
                        cleaned_count += 1
                    except Exception as e:
                        logger.warning(f"⚠️  Could not drop {db_name}: {e}")
    finally:
        driver.close()
    
    return cleaned_count


@flow(
    name="process-snapshot",
    log_prints=True
)
def process_snapshot_flow(
    customer_id: str,
    timestamp: int,
    config: dict,
    data_path: Path
) -> dict:
    """
    Process a single snapshot: load database, switch alias if latest, cleanup.
    
    This is the main workflow that processes each snapshot.
    Visible in Prefect UI as a workflow run.
    """
    db_name = f"{customer_id}-{timestamp}"
    logger.info(f"🔄 Processing snapshot: {customer_id}/{timestamp}")
    
    # Step 0: Check if database already exists (prevent duplicate loads)
    # This is a critical check to prevent race conditions when multiple threads
    # try to process the same snapshot simultaneously
    db_exists = check_database_exists_task(customer_id, timestamp, config)
    if db_exists:
        logger.info(f"⏭️  Skipping {customer_id}/{timestamp} - database already exists (checked at process start)")
        # Return a dummy result indicating it was skipped
        return {
            "database": db_name,
            "node_count": 0,
            "relationship_count": 0,
            "skipped": True
        }
    
    # Step 1: Health check
    is_healthy, health_message = check_health_task(config)
    if not is_healthy:
        raise Exception(f"Health check failed: {health_message}. Database under pressure - will retry later.")
    
    # Step 2: Load database
    result = load_database_task(customer_id, timestamp, config, data_path)
    
    # Step 3: Check if this is the latest deployment
    is_latest = check_is_latest_task(customer_id, timestamp, config)
    
    # Step 4: Switch alias if latest
    if is_latest:
        logger.info(f"🔄 Switching {customer_id} alias to {db_name} (latest)")
        switch_alias_task(customer_id, db_name, config)
    
    # Step 5: Cleanup old databases (keep newest 2)
    cleaned_count = cleanup_old_databases_task(customer_id, keep_count=2, config=config)
    if cleaned_count > 0:
        logger.info(f"🗑️  Cleaned up {cleaned_count} old database(s)")
    
    logger.info(f"✅ Completed processing snapshot: {customer_id}/{timestamp}")
    return result


@task(
    name="check-database-exists",
    log_prints=True
)
def check_database_exists_task(
    customer_id: str,
    timestamp: int,
    config: dict
) -> bool:
    """
    Check if database already exists in Neo4j.
    
    Returns:
        True if database exists, False otherwise
    """
    db_name = f"{customer_id}-{timestamp}"
    driver = get_driver(config)
    try:
        with driver.session(database="system") as session:
            result = session.run(f"SHOW DATABASES YIELD name WHERE name = '{db_name}' RETURN name")
            exists = result.single() is not None
            if exists:
                logger.debug(f"Database {db_name} already exists in Neo4j")
            return exists
    except Exception as e:
        # If we can't check (e.g., Neo4j not running), assume it doesn't exist
        logger.debug(f"Could not check if database exists: {e}")
        return False
    finally:
        driver.close()


@task(
    name="scan-for-snapshots",
    log_prints=True
)
def scan_for_snapshots_task(
    data_base_path: Path,
    processed_snapshots: set,
    config: dict
) -> list:
    """
    Scan for new snapshot directories.
    
    Returns:
        List of (customer_id, timestamp, data_path) tuples for new snapshots
    """
    new_snapshots = []
    
    if not data_base_path.exists():
        logger.warning(f"Data path does not exist: {data_base_path}")
        return new_snapshots
    
    for customer_dir in data_base_path.iterdir():
        if not customer_dir.is_dir():
            continue
        
        customer_id = customer_dir.name
        
        # Look for timestamp directories
        for timestamp_dir in customer_dir.iterdir():
            if not timestamp_dir.is_dir():
                continue
            
            try:
                timestamp = int(timestamp_dir.name)
            except ValueError:
                continue
            
            # Check if we've already processed this (in-memory check)
            snapshot_key = (customer_id, timestamp)
            if snapshot_key in processed_snapshots:
                continue
            
            # Check if snapshot is complete (has nodes and relationships)
            nodes_path = timestamp_dir / "nodes"
            relationships_path = timestamp_dir / "relationships"
            
            if nodes_path.exists() and relationships_path.exists():
                # Check if nodes and relationships directories have content
                has_nodes = any(nodes_path.iterdir())
                has_relationships = any(relationships_path.iterdir())
                
                if has_nodes and has_relationships:
                    # Check if database already exists in Neo4j (persistent check)
                    # This prevents reloading existing databases after restart
                    db_exists = check_database_exists_task(customer_id, timestamp, config)
                    if db_exists:
                        logger.info(f"⏭️  Skipping {customer_id}/{timestamp} - database already exists")
                        processed_snapshots.add(snapshot_key)  # Mark as processed
                        continue
                    
                    # Don't add to processed_snapshots yet - only add when we actually start processing
                    # This allows deferred snapshots (due to concurrency limits) to be picked up later
                    new_snapshots.append((customer_id, timestamp, timestamp_dir))
                    logger.info(f"📦 Discovered new snapshot: {customer_id}/{timestamp}")
    
    return new_snapshots


@flow(
    name="watch-for-snapshots",
    log_prints=True
)
def watch_for_snapshots_flow(
    config_path: Optional[Path] = None,
    scan_interval: int = 30
):
    """
    Long-running flow that watches for new snapshots and processes them.
    
    This flow runs continuously, scanning for new snapshots every scan_interval seconds.
    Each discovered snapshot is processed as a separate workflow run.
    """
    if config_path is None:
        config_path = project_root / "config.yaml"
    
    config = load_config(config_path)
    
    # Resolve data path
    base_path_str = config['dataset']['base_path']
    if Path(base_path_str).is_absolute():
        data_base_path = Path(base_path_str)
    else:
        data_base_path = project_root / base_path_str
    
    if not data_base_path.exists():
        raise FileNotFoundError(f"Data path does not exist: {data_base_path}")
    
    logger.info(f"👀 Watching for snapshots in {data_base_path} (scan every {scan_interval}s)")
    
    processed_snapshots = set()
    # Thread-safe tracking of snapshots currently being processed
    processing_lock = threading.Lock()
    active_snapshots = set()  # Track snapshots currently being processed
    # Limit concurrent loads to prevent overwhelming Neo4j
    # Default to 1 (sequential) for safety - can be increased if needed
    max_concurrent_loads = config.get('orchestrator', {}).get('max_concurrent_loads', 1)
    
    while True:
        try:
            # Scan for new snapshots
            new_snapshots = scan_for_snapshots_task(data_base_path, processed_snapshots, config)
            
            # Process each new snapshot as a separate workflow run
            for customer_id, timestamp, data_path in new_snapshots:
                snapshot_key = (customer_id, timestamp)
                
                # Check if already being processed and limit concurrency (thread-safe)
                with processing_lock:
                    if snapshot_key in active_snapshots:
                        logger.debug(f"⏭️  Skipping {customer_id}/{timestamp} - already being processed")
                        continue
                    if len(active_snapshots) >= max_concurrent_loads:
                        logger.info(f"⏳ Deferring {customer_id}/{timestamp} - {len(active_snapshots)} loads already in progress (max: {max_concurrent_loads})")
                        # Don't mark as processed - allow it to be picked up in next scan
                        continue
                    active_snapshots.add(snapshot_key)
                    # Only mark as processed when we actually start processing
                    processed_snapshots.add(snapshot_key)
                
                logger.info(f"🚀 Submitting snapshot for processing: {customer_id}/{timestamp}")
                # In Prefect 3.x, call flow directly in a thread to run asynchronously
                # Each call creates a new flow run visible in Prefect UI
                def run_snapshot_flow(snap_key):
                    try:
                        process_snapshot_flow(
                            customer_id,
                            timestamp,
                            config,
                            data_path
                        )
                    except Exception as e:
                        logger.error(f"Error processing snapshot {customer_id}/{timestamp}: {e}")
                    finally:
                        # Remove from active set when done
                        with processing_lock:
                            active_snapshots.discard(snap_key)
                
                # Run in background thread so watcher continues
                thread = threading.Thread(target=run_snapshot_flow, args=(snapshot_key,), daemon=True)
                thread.start()
            
            # Wait before next scan
            time.sleep(scan_interval)
            
        except KeyboardInterrupt:
            logger.info("🛑 Stopping snapshot watcher")
            break
        except Exception as e:
            logger.error(f"Error in watch loop: {e}")
            time.sleep(scan_interval)  # Continue on error


@flow(
    name="process-single-snapshot",
    log_prints=True
)
def process_single_snapshot_flow(
    customer_id: str,
    timestamp: int,
    config_path: Optional[Path] = None
) -> dict:
    """
    Process a single snapshot by customer_id and timestamp.
    
    Useful for manual triggering or testing.
    """
    if config_path is None:
        config_path = project_root / "config.yaml"
    
    config = load_config(config_path)
    
    # Resolve data path
    base_path_str = config['dataset']['base_path']
    if Path(base_path_str).is_absolute():
        data_base_path = Path(base_path_str)
    else:
        data_base_path = project_root / base_path_str
    
    data_path = data_base_path / customer_id / str(timestamp)
    
    if not data_path.exists():
        raise FileNotFoundError(f"Data path not found: {data_path}")
    
    return process_snapshot_flow(customer_id, timestamp, config, data_path)


def serve_flows():
    """
    Serve flows using Prefect 3.x API.
    
    In Prefect 3.x, flows are served rather than deployed.
    Use flow.serve() to run flows as a service.
    """
    logger.info("Serving flows with Prefect 3.x...")
    logger.info("")
    logger.info("For Prefect 3.x, use one of these approaches:")
    logger.info("")
    logger.info("Option 1: Run flows directly (recommended for demos):")
    logger.info("  python scripts/orchestrator_prefect.py --run")
    logger.info("")
    logger.info("Option 2: Use flow.serve() in code:")
    logger.info("  watch_for_snapshots_flow.serve(name='watch-for-snapshots')")
    logger.info("")
    logger.info("Option 3: Use Prefect CLI (if using Prefect Cloud):")
    logger.info("  prefect deploy scripts/orchestrator_prefect.py:watch_for_snapshots_flow")
    logger.info("")
    logger.info("The --run option is simplest for local demos and testing.")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Prefect-based orchestrator for blue/green deployments")
    parser.add_argument("--deploy", action="store_true", help="Show deployment options (Prefect 3.x uses flow.serve() or CLI)")
    parser.add_argument("--serve", action="store_true", help="Serve flows using flow.serve() (Prefect 3.x)")
    parser.add_argument("--run", action="store_true", help="Run watch flow directly (for testing)")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--scan-interval", type=int, default=30, help="Scan interval in seconds")
    parser.add_argument("--customer", help="Process single snapshot: customer ID")
    parser.add_argument("--timestamp", type=int, help="Process single snapshot: timestamp")
    
    args = parser.parse_args()
    
    if args.deploy or args.serve:
        serve_flows()
        if args.serve:
            # Actually serve the flows
            logger.info("Starting flow service...")
            watch_for_snapshots_flow.serve(
                name="watch-for-snapshots",
                parameters={
                    "config_path": str(project_root / args.config),
                    "scan_interval": args.scan_interval
                }
            )
    elif args.customer and args.timestamp:
        # Process single snapshot
        config_path = project_root / args.config
        result = process_single_snapshot_flow(
            args.customer,
            args.timestamp,
            config_path
        )
        logger.info(f"✅ Processed snapshot: {result}")
    elif args.run:
        # Run watch flow directly (for testing, not production)
        config_path = project_root / args.config
        watch_for_snapshots_flow(config_path, args.scan_interval)
    else:
        parser.print_help()
        print("\nTo get started:")
        print("  1. Start Prefect server: poetry run prefect server start")
        print("  2. Run watcher: python scripts/orchestrator_prefect.py --run")
        print("  3. Or serve flows: python scripts/orchestrator_prefect.py --serve")
        print("\nView in UI: http://localhost:4200")
        print("\nFor single snapshot:")
        print("  python scripts/orchestrator_prefect.py --customer customer1 --timestamp 1767741527")


if __name__ == "__main__":
    main()

