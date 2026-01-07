"""
Tests for neo4j_utils module.
"""
import pytest
from unittest.mock import Mock, patch
import neo4j
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from blue_green_etl.neo4j_utils import get_driver


class TestNeo4jUtils:
    """Test neo4j_utils functions."""
    
    def test_get_driver_creates_driver(self):
        """Test that get_driver creates a Neo4j driver with correct configuration."""
        config = {
            'neo4j': {
                'host': 'localhost',
                'bolt_port': 7687,
                'user': 'neo4j',
                'password': 'test_password'
            }
        }
        
        with patch('blue_green_etl.neo4j_utils.neo4j.GraphDatabase.driver') as mock_driver:
            result = get_driver(config)
            
            # Verify driver was called with correct URL
            mock_driver.assert_called_once()
            call_args = mock_driver.call_args
            assert call_args[0][0] == 'bolt://localhost:7687'
            
            # Verify auth was set correctly
            auth_call = call_args[1]['auth']
            assert auth_call is not None
    
    def test_get_driver_with_different_host(self):
        """Test get_driver with different host configuration."""
        config = {
            'neo4j': {
                'host': 'remote.example.com',
                'bolt_port': 7687,
                'user': 'admin',
                'password': 'secret'
            }
        }
        
        with patch('blue_green_etl.neo4j_utils.neo4j.GraphDatabase.driver') as mock_driver:
            get_driver(config)
            
            call_args = mock_driver.call_args
            assert call_args[0][0] == 'bolt://remote.example.com:7687'
    
    def test_get_driver_with_different_port(self):
        """Test get_driver with different port configuration."""
        config = {
            'neo4j': {
                'host': 'localhost',
                'bolt_port': 9999,
                'user': 'neo4j',
                'password': 'test'
            }
        }
        
        with patch('blue_green_etl.neo4j_utils.neo4j.GraphDatabase.driver') as mock_driver:
            get_driver(config)
            
            call_args = mock_driver.call_args
            assert call_args[0][0] == 'bolt://localhost:9999'
    
    def test_get_driver_returns_driver_instance(self):
        """Test that get_driver returns the driver instance."""
        config = {
            'neo4j': {
                'host': 'localhost',
                'bolt_port': 7687,
                'user': 'neo4j',
                'password': 'test'
            }
        }
        
        mock_driver_instance = Mock()
        with patch('blue_green_etl.neo4j_utils.neo4j.GraphDatabase.driver', return_value=mock_driver_instance):
            result = get_driver(config)
            assert result is mock_driver_instance

