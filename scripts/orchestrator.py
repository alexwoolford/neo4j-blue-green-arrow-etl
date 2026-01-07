#!/usr/bin/env python3
"""
Orchestration service for blue/green deployments.

This service:
1. Watches for new snapshot directories
2. Queues and loads them with concurrency control
3. Automatically switches aliases to latest deployments
4. Cleans up old databases (keeps newest 2, removes older)
5. Checks Neo4j health before loading
"""
import time
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from queue import Queue, Empty
from threading import Thread, Event, Lock
import json
import traceback

# Add project root and src directory to path for imports
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(project_root))

from scripts.load_with_aliases import load_database, set_alias
from blue_green_etl.logging_config import setup_logging, get_logger
from blue_green_etl.neo4j_utils import get_driver
from blue_green_etl.config_loader import load_config

# Set up logging with file output
setup_logging()
logger = get_logger(__name__)


@dataclass
class SnapshotTask:
    """Represents a snapshot loading task."""
    customer_id: str
    timestamp: int
    data_path: Path
    created_at: datetime
    retry_count: int = 0
    last_error: Optional[str] = None


class Neo4jHealthChecker:
    """Checks Neo4j instance health before loading."""
    
    def __init__(self, config: dict):
        self.config = config
        self.neo4j_url = f"bolt://{config['neo4j']['host']}:{config['neo4j']['bolt_port']}"
        self.driver = get_driver(config)
    
    def check_health(self) -> Tuple[bool, str]:
        """
        Check if Neo4j is healthy and ready for loading.
        Returns (is_healthy, message)
        """
        try:
            with self.driver.session() as session:
                # Simple health check - can we query?
                result = session.run("RETURN 1 AS health")
                result.single()
                
                # Check database count (too many might indicate resource pressure)
                result = self.driver.session(database="system").run(
                    "SHOW DATABASES YIELD name WHERE name <> 'system' RETURN count(*) AS db_count"
                )
                db_count = result.single()['db_count']
                
                max_databases = self.config.get('orchestrator', {}).get('max_databases', 50)
                if db_count >= max_databases:
                    return False, f"Too many databases ({db_count} >= {max_databases})"
                
                # Check JVM memory usage (if available via JMX)
                memory_status = self._check_memory()
                if memory_status:
                    is_healthy, msg = memory_status
                    if not is_healthy:
                        return False, msg
                
                return True, "Healthy"
        except Exception as e:
            return False, f"Health check failed: {e}"
    
    def _check_memory(self) -> Optional[Tuple[bool, str]]:
        """
        Check both heap and pagecache memory usage via JMX query.
        
        For Arrow loading:
        - Heap: Used for Arrow protocol buffers, query execution, transaction state
        - Pagecache: Used for caching database pages (off-heap, managed by Neo4j)
        
        Returns None if JMX not available, or (is_healthy, message) if available.
        """
        try:
            # Try to query JMX for memory usage
            # This requires Enterprise Edition or specific JMX configuration
            with self.driver.session(database="system") as session:
                issues = []
                
                # Check heap memory (critical for Arrow operations)
                try:
                    result = session.run(
                        "CALL dbms.queryJmx('java.lang:type=Memory') YIELD attributes "
                        "WITH attributes['HeapMemoryUsage'] AS heap "
                        "RETURN heap.used AS used, heap.max AS max, heap.committed AS committed"
                    )
                    record = result.single()
                    if record:
                        used = record['used']
                        max_heap = record['max']
                        if max_heap and max_heap > 0:
                            heap_usage_percent = (used / max_heap) * 100
                            
                            # Get threshold from config (default 85%)
                            heap_threshold = self.config.get('orchestrator', {}).get('heap_threshold_percent', 85)
                            
                            if heap_usage_percent >= heap_threshold:
                                issues.append(f"heap: {heap_usage_percent:.1f}% (threshold: {heap_threshold}%)")
                            
                            logger.debug(f"JVM heap usage: {heap_usage_percent:.1f}% ({used:,} / {max_heap:,} bytes)")
                except Exception:
                    # Heap check not available - this is OK
                    pass
                
                # Check pagecache (important for database capacity)
                # Note: Pagecache monitoring via JMX is complex and varies by Neo4j version
                # For now, we rely on heap monitoring as the primary indicator
                # Pagecache is off-heap and managed separately by Neo4j
                # If heap is healthy, pagecache is typically fine for Arrow loading
                # Future enhancement: Parse pagecache metrics when structure is known
                try:
                    # Try to query pagecache - structure varies by version
                    result = session.run(
                        "CALL dbms.queryJmx('org.neo4j:instance=kernel#0,name=Page cache') YIELD attributes "
                        "RETURN attributes"
                    )
                    record = result.single()
                    if record:
                        # Log that we found pagecache metrics (for future parsing)
                        logger.debug(f"Pagecache metrics available (not yet parsed): {record}")
                except Exception:
                    # Pagecache check not available - this is OK, heap check is primary
                    pass
                
                # If we found issues, return failure
                if issues:
                    return False, f"Memory usage too high - {', '.join(issues)}"
                
                return True, "Memory healthy"
        except Exception:
            # JMX querying not available - this is OK for Community Edition
            pass
        
        return None  # Memory check not available, but that's OK
    
    def close(self):
        self.driver.close()


class OrchestratorStats:
    """Track orchestrator statistics."""
    
    def __init__(self):
        self.lock = Lock()
        self.tasks_discovered = 0
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.tasks_retried = 0
        self.start_time = datetime.now()
        self.last_activity = None
        
    def record_discovery(self):
        with self.lock:
            self.tasks_discovered += 1
            self.last_activity = datetime.now()
    
    def record_completion(self):
        with self.lock:
            self.tasks_completed += 1
            self.last_activity = datetime.now()
    
    def record_failure(self):
        with self.lock:
            self.tasks_failed += 1
            self.last_activity = datetime.now()
    
    def record_retry(self):
        with self.lock:
            self.tasks_retried += 1
    
    def to_dict(self) -> dict:
        with self.lock:
            uptime = (datetime.now() - self.start_time).total_seconds()
            return {
                'uptime_seconds': int(uptime),
                'tasks_discovered': self.tasks_discovered,
                'tasks_completed': self.tasks_completed,
                'tasks_failed': self.tasks_failed,
                'tasks_retried': self.tasks_retried,
                'success_rate': (self.tasks_completed / max(self.tasks_discovered, 1)) * 100,
                'queue_size': 0,  # Will be set by orchestrator
                'last_activity': self.last_activity.isoformat() if self.last_activity else None,
                'status': 'running'
            }


class SnapshotWatcher:
    """Watches for new snapshot directories and creates loading tasks."""
    
    def __init__(self, data_base_path: Path, task_queue: Queue, stop_event: Event, stats: OrchestratorStats):
        self.data_base_path = data_base_path
        self.task_queue = task_queue
        self.stop_event = stop_event
        self.stats = stats
        self.processed_snapshots: set = set()  # Track (customer_id, timestamp) we've seen
    
    def scan_for_snapshots(self):
        """Scan for new snapshot directories."""
        if not self.data_base_path.exists():
            logger.warning(f"Data path does not exist: {self.data_base_path}")
            return
        
        for customer_dir in self.data_base_path.iterdir():
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
                
                # Check if we've already processed this
                snapshot_key = (customer_id, timestamp)
                if snapshot_key in self.processed_snapshots:
                    continue
                
                # Check if snapshot is complete (has nodes and relationships)
                nodes_path = timestamp_dir / "nodes"
                relationships_path = timestamp_dir / "relationships"
                
                if nodes_path.exists() and relationships_path.exists():
                    # Check if nodes and relationships directories have content
                    has_nodes = any(nodes_path.iterdir())
                    has_relationships = any(relationships_path.iterdir())
                    
                    if has_nodes and has_relationships:
                        task = SnapshotTask(
                            customer_id=customer_id,
                            timestamp=timestamp,
                            data_path=timestamp_dir,
                            created_at=datetime.now(),
                            retry_count=0
                        )
                        self.task_queue.put(task)
                        self.processed_snapshots.add(snapshot_key)
                        self.stats.record_discovery()
                        logger.info(f"📦 Discovered new snapshot: {customer_id}/{timestamp}")
    
    def run(self, scan_interval: int = 30):
        """Continuously watch for new snapshots."""
        logger.info(f"👀 Watching for snapshots in {self.data_base_path} (scan every {scan_interval}s)")
        
        while not self.stop_event.is_set():
            try:
                self.scan_for_snapshots()
            except Exception as e:
                logger.error(f"Error scanning for snapshots: {e}")
            
            # Wait for next scan or stop signal
            self.stop_event.wait(scan_interval)


class LoadWorker:
    """Worker thread that processes loading tasks."""
    
    def __init__(self, worker_id: int, task_queue: Queue, config: dict, health_checker: Neo4jHealthChecker, stats: OrchestratorStats):
        self.worker_id = worker_id
        self.task_queue = task_queue
        self.config = config
        self.health_checker = health_checker
        self.stats = stats
        self.stop_event = Event()
    
    def load_snapshot(self, task: SnapshotTask) -> bool:
        """Load a snapshot and switch alias if it's the latest."""
        customer_id = task.customer_id
        timestamp = task.timestamp
        db_name = f"{customer_id}-{timestamp}"
        
        logger.info(f"🔄 Worker {self.worker_id}: Loading {customer_id}/{timestamp} (attempt {task.retry_count + 1})...")
        
        try:
            # Check health before loading - don't start if database is under pressure
            is_healthy, message = self.health_checker.check_health()
            if not is_healthy:
                logger.warning(f"⚠️  Worker {self.worker_id}: Health check failed: {message}. Database under pressure - will retry later")
                # Put task back in queue so it can be retried
                self.task_queue.put(task)
                return False
            
            # Load the database (data_path is the timestamp directory)
            result = load_database(customer_id, timestamp, self.config, task.data_path)
            logger.info(f"✅ Worker {self.worker_id}: Loaded {db_name} ({result['node_count']:,} nodes, {result['relationship_count']:,} relationships)")
            
            # Check if this is the latest timestamp for this customer
            if self._is_latest_deployment(customer_id, timestamp):
                logger.info(f"🔄 Worker {self.worker_id}: Switching {customer_id} alias to {db_name} (latest)")
                set_alias(customer_id, db_name, self.config)
            
            # Cleanup old databases (keep newest 2)
            self._cleanup_old_databases(customer_id)
            
            self.stats.record_completion()
            return True
            
        except Exception as e:
            error_msg = str(e)
            error_trace = traceback.format_exc()
            task.last_error = error_msg
            
            logger.error(f"❌ Worker {self.worker_id}: Failed to load {db_name}: {error_msg}")
            logger.debug(f"Full traceback:\n{error_trace}")
            
            # Retry logic with exponential backoff
            max_retries = self.config.get('orchestrator', {}).get('max_retries', 3)
            retry_backoff_base = self.config.get('orchestrator', {}).get('retry_backoff_base', 2)
            
            if task.retry_count < max_retries:
                task.retry_count += 1
                backoff_seconds = retry_backoff_base ** task.retry_count
                logger.info(f"🔄 Worker {self.worker_id}: Retrying {db_name} in {backoff_seconds}s (attempt {task.retry_count + 1}/{max_retries + 1})")
                self.stats.record_retry()
                
                # Schedule retry with exponential backoff
                def delayed_retry():
                    time.sleep(backoff_seconds)
                    if not self.stop_event.is_set():
                        self.task_queue.put(task)
                
                retry_thread = Thread(target=delayed_retry, daemon=True)
                retry_thread.start()
            else:
                logger.error(f"❌ Worker {self.worker_id}: Max retries exceeded for {db_name}. Marking as failed.")
                self.stats.record_failure()
            
            return False
    
    def _is_latest_deployment(self, customer_id: str, timestamp: int) -> bool:
        """Check if this timestamp is the latest for this customer."""
        # Get all databases for this customer
        driver = get_driver(self.config)
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
                
                return timestamp == max(customer_timestamps) if customer_timestamps else True
        finally:
            driver.close()
    
    def _cleanup_old_databases(self, customer_id: str, keep_count: int = 2):
        """Remove old databases, keeping only the newest N."""
        driver = get_driver(self.config)
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
                        logger.info(f"🗑️  Worker {self.worker_id}: Dropping old database {db_name}")
                        try:
                            session.run(f"DROP DATABASE `{db_name}` IF EXISTS")
                        except Exception as e:
                            logger.warning(f"⚠️  Could not drop {db_name}: {e}")
        finally:
            driver.close()
    
    def run(self):
        """Process tasks from the queue."""
        logger.info(f"🚀 Worker {self.worker_id} started")
        
        while not self.stop_event.is_set():
            try:
                # Get task with timeout to allow checking stop_event
                task = self.task_queue.get(timeout=1)
                
                # Try to load the snapshot
                success = self.load_snapshot(task)
                
                # Mark task as done
                # Note: If health check failed, task was requeued in load_snapshot()
                # but we still mark the original get() as done
                self.task_queue.task_done()
                
                # If health check failed, wait before trying next task
                if not success:
                    retry_delay = self.config.get('orchestrator', {}).get('health_check_retry_delay', 60)
                    logger.info(f"Worker {self.worker_id}: Waiting {retry_delay}s before next task (database under pressure)")
                    self.stop_event.wait(retry_delay)
                    
            except Empty:
                continue
            except Exception as e:
                logger.error(f"❌ Worker {self.worker_id}: Error processing task: {e}")
                if 'task' in locals():
                    self.task_queue.task_done()
        
        logger.info(f"🛑 Worker {self.worker_id} stopped")


class Orchestrator:
    """Main orchestration service."""
    
    def __init__(self, config_path: Path):
        self.config = load_config(config_path)
        
        # Validate configuration
        self._validate_config()
        
        # Resolve base_path - if relative, make it relative to project root
        base_path_str = self.config['dataset']['base_path']
        if Path(base_path_str).is_absolute():
            self.data_base_path = Path(base_path_str)
        else:
            # Relative path - resolve relative to project root
            project_root = config_path.parent
            self.data_base_path = project_root / base_path_str
        
        # Verify data path exists
        if not self.data_base_path.exists():
            raise FileNotFoundError(f"Data path does not exist: {self.data_base_path}")
        
        self.task_queue = Queue()
        self.stop_event = Event()
        self.stats = OrchestratorStats()
        self.status_file = project_root / "orchestrator_status.json"
        
        orchestrator_config = self.config.get('orchestrator', {})
        self.num_workers = orchestrator_config.get('num_workers', 1)
        self.scan_interval = orchestrator_config.get('scan_interval', 30)
        self.max_retries = orchestrator_config.get('max_retries', 3)
        self.retry_backoff_base = orchestrator_config.get('retry_backoff_base', 2)
        
        # Test Neo4j connection before starting
        self._test_neo4j_connection()
        
        self.health_checker = Neo4jHealthChecker(self.config)
        self.watcher = SnapshotWatcher(self.data_base_path, self.task_queue, self.stop_event, self.stats)
        self.workers: List[LoadWorker] = []
        self.status_update_thread = None
    
    def _validate_config(self):
        """Validate configuration values."""
        required_keys = ['neo4j', 'dataset', 'orchestrator']
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Missing required config key: {key}")
        
        # Validate Neo4j config
        neo4j_config = self.config['neo4j']
        required_neo4j = ['host', 'arrow_port', 'bolt_port', 'user', 'password']
        for key in required_neo4j:
            if key not in neo4j_config:
                raise ValueError(f"Missing required Neo4j config key: {key}")
        
        # Validate orchestrator config
        orch_config = self.config.get('orchestrator', {})
        if orch_config.get('num_workers', 1) < 1:
            raise ValueError("num_workers must be >= 1")
        if orch_config.get('scan_interval', 30) < 1:
            raise ValueError("scan_interval must be >= 1")
        if orch_config.get('max_databases', 50) < 1:
            raise ValueError("max_databases must be >= 1")
    
    def _test_neo4j_connection(self):
        """Test Neo4j connection before starting."""
        logger.info("Testing Neo4j connection...")
        try:
            driver = get_driver(self.config)
            with driver.session() as session:
                result = session.run("RETURN 1 AS test")
                result.single()
            driver.close()
            logger.info("✅ Neo4j connection successful")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Neo4j: {e}. Please check your configuration.")
    
    def _write_status_file(self):
        """Write current status to JSON file for monitoring."""
        try:
            status = self.stats.to_dict()
            status['queue_size'] = self.task_queue.qsize()
            status['workers'] = self.num_workers
            status['scan_interval'] = self.scan_interval
            status['data_path'] = str(self.data_base_path)
            
            with open(self.status_file, 'w') as f:
                json.dump(status, f, indent=2)
        except Exception as e:
            logger.debug(f"Could not write status file: {e}")
    
    def start(self):
        """Start the orchestration service."""
        logger.info("="*70)
        logger.info("BLUE/GREEN DEPLOYMENT ORCHESTRATOR")
        logger.info("="*70)
        logger.info(f"Data path: {self.data_base_path}")
        logger.info(f"Workers: {self.num_workers}")
        logger.info(f"Scan interval: {self.scan_interval}s")
        logger.info("="*70)
        
        # Start watcher thread
        watcher_thread = Thread(target=self.watcher.run, args=(self.scan_interval,), daemon=True)
        watcher_thread.start()
        
        # Start worker threads
        for i in range(self.num_workers):
            worker = LoadWorker(i + 1, self.task_queue, self.config, self.health_checker, self.stats)
            self.workers.append(worker)
            worker_thread = Thread(target=worker.run, daemon=True)
            worker_thread.start()
        
        # Start status update thread
        self.status_update_thread = Thread(target=self._status_update_loop, daemon=True)
        self.status_update_thread.start()
        
        logger.info("✅ Orchestrator started. Press Ctrl+C to stop.")
        logger.info(f"📊 Status file: {self.status_file}")
        
        try:
            # Keep main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\n🛑 Shutting down orchestrator...")
            self.stop()
    
    def _status_update_loop(self):
        """Periodically update status file."""
        while not self.stop_event.is_set():
            try:
                self._write_status_file()
            except Exception as e:
                logger.debug(f"Error updating status file: {e}")
            self.stop_event.wait(5)  # Update every 5 seconds
    
    def stop(self):
        """Stop the orchestration service."""
        logger.info("Stopping orchestrator...")
        self.stop_event.set()
        
        # Update status to stopping
        try:
            status = self.stats.to_dict()
            status['status'] = 'stopping'
            status['queue_size'] = self.task_queue.qsize()
            with open(self.status_file, 'w') as f:
                json.dump(status, f, indent=2)
        except Exception:
            pass
        
        # Wait for workers to finish current tasks (with timeout)
        shutdown_timeout = self.config.get('orchestrator', {}).get('shutdown_timeout', 300)  # 5 minutes default
        queue_size = self.task_queue.qsize()
        logger.info(f"Waiting for {queue_size} queued tasks to complete (timeout: {shutdown_timeout}s)...")
        
        # Use threading-based timeout (works on all platforms)
        import threading
        
        timeout_occurred = threading.Event()
        
        def timeout_handler():
            timeout_occurred.wait(shutdown_timeout)
            if not timeout_occurred.is_set() and self.task_queue.qsize() > 0:
                logger.warning("⚠️  Shutdown timeout reached. Some tasks may not have completed.")
                timeout_occurred.set()
        
        timeout_thread = threading.Thread(target=timeout_handler, daemon=True)
        timeout_thread.start()
        
        try:
            # Wait for queue to empty or timeout
            while self.task_queue.qsize() > 0 and not timeout_occurred.is_set():
                time.sleep(0.5)
            
            if timeout_occurred.is_set():
                logger.warning("⚠️  Shutdown timeout reached. Some tasks may not have completed.")
            else:
                logger.info("✅ All tasks completed")
        except KeyboardInterrupt:
            logger.warning("⚠️  Forced shutdown - some tasks may be incomplete")
        finally:
            timeout_occurred.set()  # Signal timeout thread to stop
        
        self.health_checker.close()
        
        # Final status update
        try:
            status = self.stats.to_dict()
            status['status'] = 'stopped'
            status['queue_size'] = 0
            with open(self.status_file, 'w') as f:
                json.dump(status, f, indent=2)
        except Exception:
            pass
        
        logger.info("✅ Orchestrator stopped")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Orchestrate blue/green deployments")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--workers", type=int, help="Number of worker threads")
    parser.add_argument("--scan-interval", type=int, help="Snapshot scan interval (seconds)")
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    config_path = project_root / args.config
    orchestrator = Orchestrator(config_path)
    
    if args.workers:
        orchestrator.num_workers = args.workers
    if args.scan_interval:
        orchestrator.scan_interval = args.scan_interval
    
    orchestrator.start()


if __name__ == "__main__":
    main()

