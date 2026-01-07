#!/usr/bin/env python3
"""
Complete demo workflow for blue/green deployments.
Loads all 6 datasets and demonstrates alias switching.
"""
import sys
import yaml
import logging
from pathlib import Path

# Add project root and src directory to path for imports
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(project_root))

from scripts.load_with_aliases import load_and_switch, set_alias
from blue_green_etl.logging_config import setup_logging, get_logger
from blue_green_etl.config_loader import load_config

# Set up logging
setup_logging()
logger = get_logger(__name__)

# Configuration
CUSTOMERS = ["customer1", "customer2", "customer3"]
TIMESTAMPS = [1767741427, 1767741527]

def main():
    """Run complete demo workflow."""
    # Load config (from project root)
    config_path = project_root / "config.yaml"
    config = load_config(config_path)
    
    data_base_path = project_root / "data"
    
    logger.info("="*70)
    logger.info("BLUE/GREEN DEPLOYMENT DEMO")
    logger.info("="*70)
    logger.info(f"Loading {len(CUSTOMERS)} customers × {len(TIMESTAMPS)} timestamps")
    logger.info(f"Total: {len(CUSTOMERS) * len(TIMESTAMPS)} databases")
    
    # Phase 1: Load initial deployments (blue) with aliases
    logger.info("="*70)
    logger.info("PHASE 1: Initial Deployments (Blue)")
    logger.info("="*70)
    
    for customer_id in CUSTOMERS:
        timestamp = TIMESTAMPS[0]  # First timestamp = blue
        logger.info(f"📦 Loading {customer_id} (blue deployment)...")
        result = load_and_switch(
            customer_id,
            timestamp,
            config,
            data_base_path,
            switch_alias=True
        )
        logger.info(f"   ✅ {customer_id} alias now points to {result['database']}")
    
    # Phase 2: Load new deployments (green) without switching
    logger.info("="*70)
    logger.info("PHASE 2: New Deployments (Green) - Loaded but not active")
    logger.info("="*70)
    
    for customer_id in CUSTOMERS:
        timestamp = TIMESTAMPS[1]  # Second timestamp = green
        logger.info(f"📦 Loading {customer_id} (green deployment)...")
        result = load_and_switch(
            customer_id,
            timestamp,
            config,
            data_base_path,
            switch_alias=False  # Don't switch yet
        )
        logger.info(f"   ✅ {result['database']} loaded (alias still points to blue)")
    
    # Phase 3: Demonstrate cutover - switch all aliases to latest (highest timestamp) deployments
    logger.info("="*70)
    logger.info("PHASE 3: Cutover - Switching All Aliases to Latest Deployments")
    logger.info("="*70)
    
    for customer_id in CUSTOMERS:
        latest_db = f"{customer_id}-{TIMESTAMPS[1]}"  # Highest timestamp = latest
        logger.info(f"Switching {customer_id} alias to latest deployment ({latest_db})...")
        set_alias(customer_id, latest_db, config)
    
    # Get actual alias targets and database statuses from Neo4j
    import neo4j
    neo4j_url = f"bolt://{config['neo4j']['host']}:{config['neo4j']['bolt_port']}"
    driver = neo4j.GraphDatabase.driver(
        neo4j_url,
        auth=neo4j.basic_auth(config['neo4j']['user'], config['neo4j']['password'])
    )
    
    alias_targets = {}
    db_statuses = {}
    try:
        with driver.session(database="system") as session:
            # Get alias targets
            result = session.run("SHOW ALIASES FOR DATABASE")
            for record in result:
                alias_name = record.get('name', '')
                target_db = record.get('database', '')
                alias_targets[alias_name] = target_db
            
            # Get database statuses (online/offline)
            result = session.run("SHOW DATABASES YIELD name, currentStatus WHERE name <> 'system' RETURN name, currentStatus")
            for record in result:
                db_name = record.get('name', '')
                status = record.get('currentStatus', '')
                db_statuses[db_name] = status
    finally:
        driver.close()
    
    logger.info("="*70)
    logger.info("SUMMARY")
    logger.info("="*70)
    logger.info("Databases created:")
    for customer_id in CUSTOMERS:
        for timestamp in TIMESTAMPS:
            db_name = f"{customer_id}-{timestamp}"
            # Check if this database is the target of an alias AND is online
            is_alias_target = alias_targets.get(customer_id) == db_name
            is_online = db_statuses.get(db_name) == 'online'
            is_active = is_alias_target and is_online
            status = "🟢 ACTIVE" if is_active else "🔵 INACTIVE"
            logger.info(f"  {db_name:30} {status}")
    
    logger.info("Aliases:")
    for customer_id in CUSTOMERS:
        active_db = alias_targets.get(customer_id, "(not found)")
        logger.info(f"  {customer_id:30} -> {active_db}")
    
    logger.info("="*70)
    logger.info("✅ Demo complete!")
    logger.info("="*70)
    logger.info("You can now:")
    logger.info("  1. Query using aliases: USE customer1, customer2, customer3")
    logger.info("  2. Switch aliases (recommended - use manage_aliases.py):")
    logger.info("     python scripts/manage_aliases.py create customer1 customer1-1767741527")
    logger.info("  3. Or switch using Python (alternative method):")
    logger.info("     python -c \"import sys; sys.path.insert(0, 'src'); from scripts.load_with_aliases import set_alias; from blue_green_etl.config_loader import load_config; from pathlib import Path; config = load_config(Path('config.yaml')); set_alias('customer1', 'customer1-1767741527', config)\"")
    logger.info("  4. Clean up old databases: python scripts/cleanup_demo.py")


if __name__ == "__main__":
    main()

