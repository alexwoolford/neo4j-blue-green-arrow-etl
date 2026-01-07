"""
Tests for load_database() and alias management functionality.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path
from datetime import datetime

import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

from scripts.load_with_aliases import load_database, set_alias
from blue_green_etl.neo4j_utils import get_driver


class TestLoadDatabase:
    """Test load_database() function."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        return {
            'neo4j': {
                'host': 'localhost',
                'arrow_port': 8491,
                'bolt_port': 7687,
                'user': 'neo4j',
                'password': 'test',
                'tls': False,
                'concurrency': 10
            },
            'worker': {
                'arrow_table_size': 100000,
                'concurrency': 10
            }
        }
    
    @pytest.fixture
    def mock_data_path(self, tmp_path):
        """Create mock data path structure."""
        data_path = tmp_path / "data" / "customer1" / "1234567890"
        nodes_path = data_path / "nodes"
        relationships_path = data_path / "relationships"
        nodes_path.mkdir(parents=True)
        relationships_path.mkdir(parents=True)
        
        # Create dummy Parquet files
        (nodes_path / "Address" / "nodes.parquet").parent.mkdir(parents=True)
        (nodes_path / "Address" / "nodes.parquet").touch()
        (relationships_path / "HAS_ADDRESS" / "rels.parquet").parent.mkdir(parents=True)
        (relationships_path / "HAS_ADDRESS" / "rels.parquet").touch()
        
        return data_path
    
    def test_load_database_success(self, mock_config, mock_data_path):
        """Test successful database load."""
        customer_id = "customer1"
        timestamp = 1234567890
        db_name = f"{customer_id}-{timestamp}"
        
        # Mock Neo4j driver
        mock_driver = Mock()
        mock_session = Mock()
        mock_result = Mock()
        mock_result.single.return_value = None  # Database doesn't exist
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=None)
        
        # Mock Arrow client
        mock_client = Mock()
        mock_client.abort.return_value = True
        mock_client.create_database.return_value = {"name": db_name}
        mock_client.nodes_done.return_value = {"node_count": 100}
        mock_client.edges_done.return_value = {"relationship_count": 200}
        
        with patch('scripts.load_with_aliases.get_driver', return_value=mock_driver):
            with patch('scripts.load_with_aliases.na.Neo4jArrowClient', return_value=mock_client):
                with patch('scripts.load_with_aliases.npq.fan_out', return_value=([{"rows": 100, "bytes": 1000}], 1.0)):
                    result = load_database(customer_id, timestamp, mock_config, mock_data_path)
                    
                    assert result['database'] == db_name
                    assert result['node_count'] == 100
                    assert result['relationship_count'] == 200
                    
                    # Verify database was created
                    mock_client.create_database.assert_called_once()
                    # Verify nodes and edges were processed
                    assert mock_client.nodes_done.called
                    assert mock_client.edges_done.called
    
    def test_load_database_drops_existing(self, mock_config, mock_data_path):
        """Test that existing database is dropped before loading."""
        customer_id = "customer1"
        timestamp = 1234567890
        db_name = f"{customer_id}-{timestamp}"
        
        # Mock Neo4j driver - database exists
        mock_driver = Mock()
        mock_session = Mock()
        mock_db_result = Mock()
        mock_db_result.single.return_value = {"name": db_name}  # Database exists
        mock_alias_result = Mock()
        mock_alias_result.__iter__ = Mock(return_value=iter([]))  # No aliases
        mock_session.run.side_effect = [
            mock_db_result,  # SHOW DATABASES
            mock_alias_result  # SHOW ALIASES
        ]
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=None)
        
        # Mock Arrow client
        mock_client = Mock()
        mock_client.abort.return_value = True
        mock_client.create_database.return_value = {"name": db_name}
        mock_client.nodes_done.return_value = {"node_count": 100}
        mock_client.edges_done.return_value = {"relationship_count": 200}
        
        with patch('scripts.load_with_aliases.get_driver', return_value=mock_driver):
            with patch('scripts.load_with_aliases.na.Neo4jArrowClient', return_value=mock_client):
                with patch('scripts.load_with_aliases.npq.fan_out', return_value=([{"rows": 100, "bytes": 1000}], 1.0)):
                    with patch('time.sleep'):  # Speed up test
                        result = load_database(customer_id, timestamp, mock_config, mock_data_path)
                        
                        # Verify database was dropped
                        drop_calls = [call for call in mock_session.run.call_args_list 
                                     if 'DROP DATABASE' in str(call)]
                        assert len(drop_calls) > 0
    
    def test_load_database_drops_aliases(self, mock_config, mock_data_path):
        """Test that aliases pointing to database are dropped."""
        customer_id = "customer1"
        timestamp = 1234567890
        db_name = f"{customer_id}-{timestamp}"
        
        # Mock Neo4j driver - database exists with alias
        mock_driver = Mock()
        mock_session = Mock()
        mock_db_result = Mock()
        mock_db_result.single.return_value = {"name": db_name}
        
        # Mock alias pointing to database
        alias_record = {"name": "customer1", "database": db_name}
        mock_alias_result = Mock()
        mock_alias_result.__iter__ = Mock(return_value=iter([alias_record]))
        
        mock_session.run.side_effect = [
            mock_db_result,  # SHOW DATABASES
            mock_alias_result,  # SHOW ALIASES
            Mock(),  # DROP ALIAS
            Mock()  # DROP DATABASE
        ]
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=None)
        
        # Mock Arrow client
        mock_client = Mock()
        mock_client.abort.return_value = True
        mock_client.create_database.return_value = {"name": db_name}
        mock_client.nodes_done.return_value = {"node_count": 100}
        mock_client.edges_done.return_value = {"relationship_count": 200}
        
        with patch('scripts.load_with_aliases.get_driver', return_value=mock_driver):
            with patch('scripts.load_with_aliases.na.Neo4jArrowClient', return_value=mock_client):
                with patch('scripts.load_with_aliases.npq.fan_out', return_value=([{"rows": 100, "bytes": 1000}], 1.0)):
                    with patch('time.sleep'):  # Speed up test
                        result = load_database(customer_id, timestamp, mock_config, mock_data_path)
                        
                        # Verify alias was dropped
                        drop_alias_calls = [call for call in mock_session.run.call_args_list 
                                          if 'DROP ALIAS' in str(call)]
                        assert len(drop_alias_calls) > 0
    
    def test_load_database_handles_abort_failure(self, mock_config, mock_data_path):
        """Test that abort failures are handled gracefully."""
        customer_id = "customer1"
        timestamp = 1234567890
        
        # Mock Neo4j driver
        mock_driver = Mock()
        mock_session = Mock()
        mock_result = Mock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=None)
        
        # Mock Arrow client - abort fails
        mock_client = Mock()
        mock_client.abort.side_effect = Exception("Abort failed")
        mock_client.create_database.return_value = {"name": f"{customer_id}-{timestamp}"}
        mock_client.nodes_done.return_value = {"node_count": 100}
        mock_client.edges_done.return_value = {"relationship_count": 200}
        
        with patch('scripts.load_with_aliases.get_driver', return_value=mock_driver):
            with patch('scripts.load_with_aliases.na.Neo4jArrowClient', return_value=mock_client):
                with patch('scripts.load_with_aliases.npq.fan_out', return_value=([{"rows": 100, "bytes": 1000}], 1.0)):
                    # Should not raise exception
                    result = load_database(customer_id, timestamp, mock_config, mock_data_path)
                    assert result is not None
    
    def test_load_database_handles_driver_error(self, mock_config, mock_data_path):
        """Test that driver errors are handled gracefully."""
        customer_id = "customer1"
        timestamp = 1234567890
        
        # Mock driver to raise exception
        mock_driver = Mock()
        mock_driver.session.side_effect = Exception("Connection failed")
        
        # Mock Arrow client
        mock_client = Mock()
        mock_client.abort.return_value = True
        mock_client.create_database.return_value = {"name": f"{customer_id}-{timestamp}"}
        mock_client.nodes_done.return_value = {"node_count": 100}
        mock_client.edges_done.return_value = {"relationship_count": 200}
        
        with patch('scripts.load_with_aliases.get_driver', return_value=mock_driver):
            with patch('scripts.load_with_aliases.na.Neo4jArrowClient', return_value=mock_client):
                with patch('scripts.load_with_aliases.npq.fan_out', return_value=([{"rows": 100, "bytes": 1000}], 1.0)):
                    # Should not raise exception, should log and continue
                    result = load_database(customer_id, timestamp, mock_config, mock_data_path)
                    assert result is not None


class TestSetAlias:
    """Test set_alias() function."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        return {
            'neo4j': {
                'host': 'localhost',
                'bolt_port': 7687,
                'user': 'neo4j',
                'password': 'test'
            }
        }
    
    def test_set_alias_creates_new(self, mock_config):
        """Test creating a new alias."""
        alias_name = "customer1"
        target_database = "customer1-1234567890"
        
        # Mock Neo4j driver
        mock_driver = Mock()
        mock_session = Mock()
        mock_session.run.return_value = None  # CREATE ALIAS succeeds
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=None)
        
        with patch('scripts.load_with_aliases.neo4j.GraphDatabase.driver', return_value=mock_driver):
            result = set_alias(alias_name, target_database, mock_config)
            
            assert result is True
            # Verify CREATE ALIAS was called
            assert mock_session.run.call_count >= 1
    
    def test_set_alias_updates_existing(self, mock_config):
        """Test updating an existing alias."""
        alias_name = "customer1"
        target_database = "customer1-1234567890"
        
        # Mock Neo4j driver - alias exists
        mock_driver = Mock()
        mock_session = Mock()
        # DROP ALIAS may raise exception (alias doesn't exist), CREATE ALIAS succeeds
        mock_session.run.side_effect = [None, None]  # DROP (may fail), CREATE
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=None)
        
        with patch('scripts.load_with_aliases.neo4j.GraphDatabase.driver', return_value=mock_driver):
            result = set_alias(alias_name, target_database, mock_config)
            
            assert result is True
            # Verify multiple calls were made (drop, create)
            assert mock_session.run.call_count >= 1
    
    def test_set_alias_handles_errors(self, mock_config):
        """Test that alias errors are handled gracefully."""
        alias_name = "customer1"
        target_database = "customer1-1234567890"
        
        # Mock Neo4j driver to raise exception
        mock_driver = Mock()
        mock_driver.session.side_effect = Exception("Connection failed")
        
        with patch('scripts.load_with_aliases.neo4j.GraphDatabase.driver', return_value=mock_driver):
            result = set_alias(alias_name, target_database, mock_config)
            
            # Should return False on error
            assert result is False
    
    def test_set_alias_handles_missing_database(self, mock_config):
        """Test that missing target database is handled."""
        alias_name = "customer1"
        target_database = "nonexistent-db"
        
        # Mock Neo4j driver - database doesn't exist
        mock_driver = Mock()
        mock_session = Mock()
        mock_session.run.side_effect = Exception("Database does not exist")
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=None)
        
        with patch('scripts.load_with_aliases.neo4j.GraphDatabase.driver', return_value=mock_driver):
            result = set_alias(alias_name, target_database, mock_config)
            
            # Should return False on error
            assert result is False

