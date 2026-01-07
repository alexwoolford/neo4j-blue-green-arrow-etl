"""
Tests for orchestrator health checking functionality.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from contextlib import contextmanager
import neo4j
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.orchestrator import Neo4jHealthChecker


class TestNeo4jHealthChecker:
    """Test Neo4jHealthChecker class."""
    
    @pytest.fixture
    def config(self):
        """Standard test configuration."""
        return {
            'neo4j': {
                'host': 'localhost',
                'bolt_port': 7687,
                'user': 'neo4j',
                'password': 'test'
            },
            'orchestrator': {
                'max_databases': 50,
                'heap_threshold_percent': 85,
                'pagecache_threshold_percent': 90
            }
        }
    
    @pytest.fixture
    def mock_driver(self):
        """Mock Neo4j driver."""
        driver = Mock()
        return driver
    
    def _create_session_context(self, session_mock):
        """Helper to create a context manager for session."""
        context = MagicMock()
        context.__enter__ = Mock(return_value=session_mock)
        context.__exit__ = Mock(return_value=None)
        return context
    
    def _create_record_mock(self, data_dict):
        """Helper to create a mock record that supports dict-like access."""
        # Use a simple class that behaves like a dict
        class Record:
            def __init__(self, data):
                self._data = data
            def __getitem__(self, key):
                return self._data[key]
            def __setitem__(self, key, value):
                self._data[key] = value
            def get(self, key, default=None):
                return self._data.get(key, default)
            def __contains__(self, key):
                return key in self._data
            def keys(self):
                return self._data.keys()
            def values(self):
                return self._data.values()
            def items(self):
                return self._data.items()
        
        return Record(data_dict)
    
    def test_check_health_success(self, config, mock_driver):
        """Test successful health check."""
        with patch('scripts.orchestrator.get_driver', return_value=mock_driver):
            checker = Neo4jHealthChecker(config)
            
            # Mock successful session - basic health check
            mock_session = Mock()
            mock_health_result = Mock()
            health_record = self._create_record_mock({'health': 1})
            mock_health_result.single = Mock(return_value=health_record)
            mock_session.run.return_value = mock_health_result
            
            # Mock database count check - system session
            # Note: The code calls self.driver.session(database="system").run(...) directly
            # This means the context manager itself needs a .run() method
            mock_system_context = Mock()
            mock_db_result = Mock()
            db_record = self._create_record_mock({'db_count': 10})
            mock_db_result.single = Mock(return_value=db_record)
            mock_system_context.run.return_value = mock_db_result
            
            # First call: default session (used in 'with' statement)
            # Second call: system session (called directly with .run() on context manager)
            def session_side_effect(database=None):
                if database == "system":
                    # Return a context manager that has a .run() method
                    return mock_system_context
                else:
                    # Return a context manager that yields the default session
                    return self._create_session_context(mock_session)
            
            mock_driver.session.side_effect = session_side_effect
            
            is_healthy, message = checker.check_health()
            
            assert is_healthy is True
            assert message == "Healthy"
            checker.close()
    
    def test_check_health_too_many_databases(self, config, mock_driver):
        """Test health check fails when too many databases."""
        with patch('scripts.orchestrator.get_driver', return_value=mock_driver):
            checker = Neo4jHealthChecker(config)
            
            # Mock successful basic check
            mock_session = Mock()
            mock_health_result = Mock()
            mock_health_result.single.return_value = {'health': 1}
            mock_session.run.return_value = mock_health_result
            
            # Mock database count check - too many databases
            mock_system_context = Mock()
            mock_db_result = Mock()
            db_record = self._create_record_mock({'db_count': 60})  # Exceeds max of 50
            mock_db_result.single = Mock(return_value=db_record)
            mock_system_context.run.return_value = mock_db_result
            
            def session_side_effect(database=None):
                if database == "system":
                    return mock_system_context
                else:
                    return self._create_session_context(mock_session)
            
            mock_driver.session.side_effect = session_side_effect
            
            is_healthy, message = checker.check_health()
            
            assert is_healthy is False
            assert "Too many databases" in message
            checker.close()
    
    def test_check_health_heap_too_high(self, config, mock_driver):
        """Test health check fails when heap usage is too high."""
        with patch('scripts.orchestrator.get_driver', return_value=mock_driver):
            checker = Neo4jHealthChecker(config)
            
            # Mock successful basic check
            mock_session = Mock()
            mock_health_result = Mock()
            health_record = self._create_record_mock({'health': 1})
            mock_health_result.single = Mock(return_value=health_record)
            mock_session.run = Mock(return_value=mock_health_result)
            
            # Mock database count check - OK (below threshold)
            # Use the same pattern as the working test
            mock_system_context = Mock()
            mock_db_result = Mock()
            db_record = self._create_record_mock({'db_count': 10})
            mock_db_result.single = Mock(return_value=db_record)
            mock_system_context.run.return_value = mock_db_result
            
            # Mock heap memory check - too high (exactly at threshold)
            # Note: _check_memory() creates its own system session with context manager
            heap_data = {
                'used': 85000000,  # 85MB (exactly 85% of 100MB)
                'max': 100000000,  # 100MB max
                'committed': 100000000
            }
            heap_record = self._create_record_mock(heap_data)
            mock_heap_result = Mock()
            mock_heap_result.single = Mock(return_value=heap_record)
            
            mock_memory_session = Mock()
            mock_memory_session.run = Mock(return_value=mock_heap_result)
            
            # Track calls to session() - need to handle both direct .run() and context manager
            # Use the same pattern as the working test
            def session_side_effect(database=None):
                if database == "system":
                    # First call: direct .run() for db_count
                    # Second call: context manager for _check_memory()
                    # We need to track which call this is
                    if not hasattr(session_side_effect, 'call_count'):
                        session_side_effect.call_count = 0
                    session_side_effect.call_count += 1
                    if session_side_effect.call_count == 1:
                        return mock_system_context
                    else:
                        return self._create_session_context(mock_memory_session)
                else:
                    return self._create_session_context(mock_session)
            
            mock_driver.session.side_effect = session_side_effect
            
            is_healthy, message = checker.check_health()
            
            assert is_healthy is False
            assert "heap" in message.lower() or "memory" in message.lower()
            checker.close()
    
    def test_check_health_heap_ok(self, config, mock_driver):
        """Test health check passes when heap usage is acceptable."""
        with patch('scripts.orchestrator.get_driver', return_value=mock_driver):
            checker = Neo4jHealthChecker(config)
            
            # Mock successful basic check
            mock_session = Mock()
            mock_health_result = Mock()
            mock_health_result.single.return_value = {'health': 1}
            mock_session.run.return_value = mock_health_result
            
            # Mock database count check - OK
            mock_system_session = Mock()
            mock_db_result = Mock()
            db_record = self._create_record_mock({'db_count': 10})
            mock_db_result.single = Mock(return_value=db_record)
            
            # Mock heap memory check - OK (below threshold)
            mock_heap_result = Mock()
            heap_data = {
                'used': 50000000,  # 50MB (50% of 100MB, below 85% threshold)
                'max': 100000000,  # 100MB max
                'committed': 100000000
            }
            heap_record = self._create_record_mock(heap_data)
            mock_heap_result.single.return_value = heap_record
            
            # First call returns db_count, second call returns heap
            def system_session_run(query, **kwargs):
                if 'SHOW DATABASES' in query:
                    return mock_db_result
                elif 'queryJmx' in query:
                    return mock_heap_result
                return mock_db_result
            
            mock_system_context = Mock()
            mock_system_context.run.side_effect = system_session_run
            
            def session_side_effect(database=None):
                if database == "system":
                    return mock_system_context
                else:
                    return self._create_session_context(mock_session)
            
            mock_driver.session.side_effect = session_side_effect
            
            is_healthy, message = checker.check_health()
            
            assert is_healthy is True
            checker.close()
    
    def test_check_health_jmx_not_available(self, config, mock_driver):
        """Test health check gracefully handles missing JMX."""
        with patch('scripts.orchestrator.get_driver', return_value=mock_driver):
            checker = Neo4jHealthChecker(config)
            
            # Mock successful basic check
            mock_session = Mock()
            mock_health_result = Mock()
            mock_health_result.single.return_value = {'health': 1}
            mock_session.run.return_value = mock_health_result
            
            # Mock database count check - OK
            mock_system_session = Mock()
            mock_db_result = Mock()
            db_record = self._create_record_mock({'db_count': 10})
            mock_db_result.single = Mock(return_value=db_record)
            
            # Mock JMX query failure (JMX not available)
            def system_session_run(query, **kwargs):
                if 'SHOW DATABASES' in query:
                    return mock_db_result
                elif 'queryJmx' in query:
                    raise Exception("JMX not available")
                return mock_db_result
            
            mock_system_context = Mock()
            mock_system_context.run.side_effect = system_session_run
            
            def session_side_effect(database=None):
                if database == "system":
                    return mock_system_context
                else:
                    return self._create_session_context(mock_session)
            
            mock_driver.session.side_effect = session_side_effect
            
            # Should still pass (JMX not available is OK)
            is_healthy, message = checker.check_health()
            
            assert is_healthy is True
            checker.close()
    
    def test_check_health_connection_failure(self, config, mock_driver):
        """Test health check handles connection failures."""
        with patch('scripts.orchestrator.get_driver', return_value=mock_driver):
            checker = Neo4jHealthChecker(config)
            
            # Mock connection failure
            mock_driver.session.side_effect = Exception("Connection failed")
            
            is_healthy, message = checker.check_health()
            
            assert is_healthy is False
            assert "failed" in message.lower()
            checker.close()

