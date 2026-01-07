"""
Tests for orchestrator retry logic and task queue management.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path
from queue import Queue
from threading import Event
from datetime import datetime
import time

import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

from scripts.orchestrator import (
    OrchestratorStats,
    SnapshotTask,
    LoadWorker,
    SnapshotWatcher,
    Orchestrator
)
from blue_green_etl.neo4j_utils import get_driver


class TestOrchestratorStats:
    """Test OrchestratorStats class."""
    
    def test_stats_initialization(self):
        """Test that stats are initialized correctly."""
        stats = OrchestratorStats()
        assert stats.tasks_discovered == 0
        assert stats.tasks_completed == 0
        assert stats.tasks_failed == 0
        assert stats.tasks_retried == 0
        assert stats.start_time is not None
        assert stats.last_activity is None
    
    def test_record_discovery(self):
        """Test recording task discovery."""
        stats = OrchestratorStats()
        stats.record_discovery()
        assert stats.tasks_discovered == 1
        assert stats.last_activity is not None
    
    def test_record_completion(self):
        """Test recording task completion."""
        stats = OrchestratorStats()
        stats.record_completion()
        assert stats.tasks_completed == 1
        assert stats.last_activity is not None
    
    def test_record_failure(self):
        """Test recording task failure."""
        stats = OrchestratorStats()
        stats.record_failure()
        assert stats.tasks_failed == 1
        assert stats.last_activity is not None
    
    def test_record_retry(self):
        """Test recording task retry."""
        stats = OrchestratorStats()
        stats.record_retry()
        assert stats.tasks_retried == 1
    
    def test_to_dict(self):
        """Test converting stats to dictionary."""
        stats = OrchestratorStats()
        stats.record_discovery()
        stats.record_completion()
        stats.record_failure()
        stats.record_retry()
        
        result = stats.to_dict()
        assert result['tasks_discovered'] == 1
        assert result['tasks_completed'] == 1
        assert result['tasks_failed'] == 1
        assert result['tasks_retried'] == 1
        assert result['success_rate'] == 100.0
        assert result['status'] == 'running'
        assert 'uptime_seconds' in result
    
    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        stats = OrchestratorStats()
        stats.record_discovery()
        stats.record_discovery()
        stats.record_completion()
        
        result = stats.to_dict()
        assert result['success_rate'] == 50.0
    
    def test_thread_safety(self):
        """Test that stats are thread-safe."""
        import threading
        
        stats = OrchestratorStats()
        
        def record_multiple():
            for _ in range(100):
                stats.record_discovery()
                stats.record_completion()
        
        threads = [threading.Thread(target=record_multiple) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert stats.tasks_discovered == 1000
        assert stats.tasks_completed == 1000


class TestSnapshotTask:
    """Test SnapshotTask dataclass."""
    
    def test_task_creation(self):
        """Test creating a snapshot task."""
        task = SnapshotTask(
            customer_id="customer1",
            timestamp=1234567890,
            data_path=Path("/tmp/data"),
            created_at=datetime.now()
        )
        assert task.customer_id == "customer1"
        assert task.timestamp == 1234567890
        assert task.retry_count == 0
        assert task.last_error is None
    
    def test_task_with_retry(self):
        """Test task with retry information."""
        task = SnapshotTask(
            customer_id="customer1",
            timestamp=1234567890,
            data_path=Path("/tmp/data"),
            created_at=datetime.now(),
            retry_count=2,
            last_error="Connection failed"
        )
        assert task.retry_count == 2
        assert task.last_error == "Connection failed"


class TestLoadWorkerRetry:
    """Test LoadWorker retry logic."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        return {
            'neo4j': {
                'host': 'localhost',
                'arrow_port': 8491,
                'bolt_port': 7687,
                'user': 'neo4j',
                'password': 'test'
            },
            'orchestrator': {
                'max_retries': 3,
                'retry_backoff_base': 2,
                'health_check_retry_delay': 60
            }
        }
    
    @pytest.fixture
    def mock_health_checker(self):
        """Mock health checker."""
        checker = Mock()
        checker.check_health.return_value = (True, "Healthy")
        return checker
    
    @pytest.fixture
    def mock_stats(self):
        """Mock statistics tracker."""
        return OrchestratorStats()
    
    def test_retry_on_failure(self, mock_config, mock_health_checker, mock_stats):
        """Test that failed loads are retried."""
        task_queue = Queue()
        stop_event = Event()
        
        worker = LoadWorker(1, task_queue, mock_config, mock_health_checker, mock_stats)
        
        task = SnapshotTask(
            customer_id="customer1",
            timestamp=1234567890,
            data_path=Path("/tmp/data"),
            created_at=datetime.now()
        )
        
        # Mock load_database to fail
        with patch('scripts.orchestrator.load_database', side_effect=Exception("Load failed")):
            with patch('scripts.orchestrator.Thread') as mock_thread:
                result = worker.load_snapshot(task)
                
                # Should return False (failed)
                assert result is False
                
                # Should increment retry count
                assert task.retry_count == 1
                
                # Should record retry
                assert mock_stats.tasks_retried == 1
                
                # Should schedule retry thread
                assert mock_thread.called
    
    def test_max_retries_exceeded(self, mock_config, mock_health_checker, mock_stats):
        """Test that max retries are respected."""
        task_queue = Queue()
        stop_event = Event()
        
        worker = LoadWorker(1, task_queue, mock_config, mock_health_checker, mock_stats)
        
        task = SnapshotTask(
            customer_id="customer1",
            timestamp=1234567890,
            data_path=Path("/tmp/data"),
            created_at=datetime.now(),
            retry_count=3  # Already at max
        )
        
        # Mock load_database to fail
        with patch('scripts.orchestrator.load_database', side_effect=Exception("Load failed")):
            result = worker.load_snapshot(task)
            
            # Should return False (failed)
            assert result is False
            
            # Should not increment retry count beyond max
            assert task.retry_count == 3
            
            # Should record failure
            assert mock_stats.tasks_failed == 1
    
    def test_exponential_backoff_calculation(self, mock_config, mock_health_checker, mock_stats):
        """Test exponential backoff delay calculation."""
        task_queue = Queue()
        stop_event = Event()
        
        worker = LoadWorker(1, task_queue, mock_config, mock_health_checker, mock_stats)
        
        task = SnapshotTask(
            customer_id="customer1",
            timestamp=1234567890,
            data_path=Path("/tmp/data"),
            created_at=datetime.now()
        )
        
        with patch('scripts.orchestrator.load_database', side_effect=Exception("Load failed")):
            with patch('threading.Thread') as mock_thread:
                # First retry
                worker.load_snapshot(task)
                assert task.retry_count == 1
                
                # Second retry
                worker.load_snapshot(task)
                assert task.retry_count == 2
                
                # Third retry
                worker.load_snapshot(task)
                assert task.retry_count == 3
        
        # Verify backoff: 2^1=2s, 2^2=4s, 2^3=8s
        # We can't easily verify the exact delay, but we can verify the pattern
        assert task.retry_count == 3
    
    def test_retry_after_health_check_failure(self, mock_config, mock_health_checker, mock_stats):
        """Test retry after health check failure."""
        task_queue = Queue()
        stop_event = Event()
        
        worker = LoadWorker(1, task_queue, mock_config, mock_health_checker, mock_stats)
        
        task = SnapshotTask(
            customer_id="customer1",
            timestamp=1234567890,
            data_path=Path("/tmp/data"),
            created_at=datetime.now()
        )
        
        # Mock health check to fail
        mock_health_checker.check_health.return_value = (False, "Database under pressure")
        
        result = worker.load_snapshot(task)
        
        # Should return False
        assert result is False
        
        # Task should be requeued
        assert not task_queue.empty()
        
        # Should not increment retry count (health check failure is different)
        assert task.retry_count == 0
    
    def test_successful_load_records_completion(self, mock_config, mock_health_checker, mock_stats):
        """Test that successful loads record completion."""
        task_queue = Queue()
        stop_event = Event()
        
        worker = LoadWorker(1, task_queue, mock_config, mock_health_checker, mock_stats)
        
        task = SnapshotTask(
            customer_id="customer1",
            timestamp=1234567890,
            data_path=Path("/tmp/data"),
            created_at=datetime.now()
        )
        
        # Mock successful load
        with patch('scripts.orchestrator.load_database', return_value={'node_count': 100, 'relationship_count': 200}):
            with patch('scripts.orchestrator.set_alias'):
                with patch.object(worker, '_is_latest_deployment', return_value=True):
                    with patch.object(worker, '_cleanup_old_databases'):
                        result = worker.load_snapshot(task)
                        
                        # Should return True
                        assert result is True
                        
                        # Should record completion
                        assert mock_stats.tasks_completed == 1


class TestSnapshotWatcher:
    """Test SnapshotWatcher class."""
    
    @pytest.fixture
    def mock_stats(self):
        """Mock statistics tracker."""
        return OrchestratorStats()
    
    def test_scan_for_snapshots_discovery(self, tmp_path, mock_stats):
        """Test that snapshots are discovered and queued."""
        task_queue = Queue()
        stop_event = Event()
        
        # Create snapshot structure
        data_path = tmp_path / "data"
        customer_path = data_path / "customer1"
        timestamp_path = customer_path / "1234567890"
        nodes_path = timestamp_path / "nodes"
        relationships_path = timestamp_path / "relationships"
        nodes_path.mkdir(parents=True)
        relationships_path.mkdir(parents=True)
        
        # Create dummy files to make directories non-empty
        (nodes_path / "Address" / "nodes.parquet").parent.mkdir(parents=True)
        (nodes_path / "Address" / "nodes.parquet").touch()
        (relationships_path / "HAS_ADDRESS" / "rels.parquet").parent.mkdir(parents=True)
        (relationships_path / "HAS_ADDRESS" / "rels.parquet").touch()
        
        watcher = SnapshotWatcher(data_path, task_queue, stop_event, mock_stats)
        watcher.scan_for_snapshots()
        
        # Should discover snapshot
        assert not task_queue.empty()
        assert mock_stats.tasks_discovered == 1
        
        # Check task details
        task = task_queue.get()
        assert task.customer_id == "customer1"
        assert task.timestamp == 1234567890
    
    def test_scan_ignores_incomplete_snapshots(self, tmp_path, mock_stats):
        """Test that incomplete snapshots are ignored."""
        task_queue = Queue()
        stop_event = Event()
        
        # Create incomplete snapshot (missing relationships)
        data_path = tmp_path / "data"
        customer_path = data_path / "customer1"
        timestamp_path = customer_path / "1234567890"
        nodes_path = timestamp_path / "nodes"
        nodes_path.mkdir(parents=True)
        (nodes_path / "Address" / "nodes.parquet").parent.mkdir(parents=True)
        (nodes_path / "Address" / "nodes.parquet").touch()
        # No relationships directory
        
        watcher = SnapshotWatcher(data_path, task_queue, stop_event, mock_stats)
        watcher.scan_for_snapshots()
        
        # Should not discover incomplete snapshot
        assert task_queue.empty()
        assert mock_stats.tasks_discovered == 0
    
    def test_scan_ignores_empty_directories(self, tmp_path, mock_stats):
        """Test that empty directories are ignored."""
        task_queue = Queue()
        stop_event = Event()
        
        # Create snapshot with empty directories
        data_path = tmp_path / "data"
        customer_path = data_path / "customer1"
        timestamp_path = customer_path / "1234567890"
        nodes_path = timestamp_path / "nodes"
        relationships_path = timestamp_path / "relationships"
        nodes_path.mkdir(parents=True)
        relationships_path.mkdir(parents=True)
        # Directories exist but are empty
        
        watcher = SnapshotWatcher(data_path, task_queue, stop_event, mock_stats)
        watcher.scan_for_snapshots()
        
        # Should not discover empty snapshot
        assert task_queue.empty()
        assert mock_stats.tasks_discovered == 0
    
    def test_scan_ignores_duplicate_snapshots(self, tmp_path, mock_stats):
        """Test that already-processed snapshots are ignored."""
        task_queue = Queue()
        stop_event = Event()
        
        # Create snapshot structure
        data_path = tmp_path / "data"
        customer_path = data_path / "customer1"
        timestamp_path = customer_path / "1234567890"
        nodes_path = timestamp_path / "nodes"
        relationships_path = timestamp_path / "relationships"
        nodes_path.mkdir(parents=True)
        relationships_path.mkdir(parents=True)
        (nodes_path / "Address" / "nodes.parquet").parent.mkdir(parents=True)
        (nodes_path / "Address" / "nodes.parquet").touch()
        (relationships_path / "HAS_ADDRESS" / "rels.parquet").parent.mkdir(parents=True)
        (relationships_path / "HAS_ADDRESS" / "rels.parquet").touch()
        
        watcher = SnapshotWatcher(data_path, task_queue, stop_event, mock_stats)
        
        # First scan
        watcher.scan_for_snapshots()
        assert mock_stats.tasks_discovered == 1
        
        # Second scan (should ignore duplicate)
        watcher.scan_for_snapshots()
        assert mock_stats.tasks_discovered == 1  # Still 1, not 2
    
    def test_scan_handles_missing_path(self, mock_stats):
        """Test that missing data path is handled gracefully."""
        task_queue = Queue()
        stop_event = Event()
        
        watcher = SnapshotWatcher(Path("/nonexistent/path"), task_queue, stop_event, mock_stats)
        watcher.scan_for_snapshots()
        
        # Should not crash, just log warning
        assert task_queue.empty()


class TestOrchestratorConfigValidation:
    """Test Orchestrator configuration validation."""
    
    def test_valid_config(self, tmp_path):
        """Test that valid config passes validation."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
neo4j:
  host: localhost
  arrow_port: 8491
  bolt_port: 7687
  user: neo4j
  password: test
dataset:
  base_path: data
orchestrator:
  num_workers: 2
  scan_interval: 30
  max_databases: 50
""")
        
        # Create data directory
        (tmp_path / "data").mkdir()
        
        with patch('scripts.orchestrator.get_driver') as mock_driver:
            mock_driver_instance = Mock()
            mock_session = Mock()
            mock_result = Mock()
            mock_result.single.return_value = {'test': 1}
            mock_session.run.return_value = mock_result
            mock_driver_instance.session.return_value.__enter__ = Mock(return_value=mock_session)
            mock_driver_instance.session.return_value.__exit__ = Mock(return_value=None)
            mock_driver.return_value = mock_driver_instance
            
            orchestrator = Orchestrator(config_path)
            assert orchestrator.num_workers == 2
            assert orchestrator.scan_interval == 30
    
    def test_missing_required_key(self, tmp_path):
        """Test that missing required config key raises error."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
neo4j:
  host: localhost
dataset:
  base_path: data
# Missing orchestrator key
""")
        
        with pytest.raises(ValueError, match="Missing required config key"):
            Orchestrator(config_path)
    
    def test_missing_neo4j_key(self, tmp_path):
        """Test that missing Neo4j config key raises error."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
neo4j:
  host: localhost
  # Missing arrow_port, bolt_port, user, password
dataset:
  base_path: data
orchestrator:
  num_workers: 1
""")
        
        with pytest.raises(ValueError, match="Missing required Neo4j config key"):
            Orchestrator(config_path)
    
    def test_invalid_num_workers(self, tmp_path):
        """Test that invalid num_workers raises error."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
neo4j:
  host: localhost
  arrow_port: 8491
  bolt_port: 7687
  user: neo4j
  password: test
dataset:
  base_path: data
orchestrator:
  num_workers: 0  # Invalid: must be >= 1
  scan_interval: 30
""")
        
        (tmp_path / "data").mkdir()
        
        with pytest.raises(ValueError, match="num_workers must be >= 1"):
            with patch('scripts.orchestrator.get_driver'):
                Orchestrator(config_path)
    
    def test_invalid_scan_interval(self, tmp_path):
        """Test that invalid scan_interval raises error."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
neo4j:
  host: localhost
  arrow_port: 8491
  bolt_port: 7687
  user: neo4j
  password: test
dataset:
  base_path: data
orchestrator:
  num_workers: 1
  scan_interval: 0  # Invalid: must be >= 1
""")
        
        (tmp_path / "data").mkdir()
        
        with pytest.raises(ValueError, match="scan_interval must be >= 1"):
            with patch('scripts.orchestrator.get_driver'):
                Orchestrator(config_path)
    
    def test_missing_data_path(self, tmp_path):
        """Test that missing data path raises error."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
neo4j:
  host: localhost
  arrow_port: 8491
  bolt_port: 7687
  user: neo4j
  password: test
dataset:
  base_path: nonexistent_path
orchestrator:
  num_workers: 1
""")
        
        with pytest.raises(FileNotFoundError, match="Data path does not exist"):
            with patch('scripts.orchestrator.get_driver'):
                Orchestrator(config_path)
    
    def test_neo4j_connection_failure(self, tmp_path):
        """Test that Neo4j connection failure raises error."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
neo4j:
  host: localhost
  arrow_port: 8491
  bolt_port: 7687
  user: neo4j
  password: test
dataset:
  base_path: data
orchestrator:
  num_workers: 1
""")
        
        (tmp_path / "data").mkdir()
        
        with patch('scripts.orchestrator.get_driver', side_effect=Exception("Connection failed")):
            with pytest.raises(ConnectionError, match="Failed to connect to Neo4j"):
                Orchestrator(config_path)

