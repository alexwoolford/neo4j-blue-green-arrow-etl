"""
Tests for neo4j_arrow_client module, focusing on error handling.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from blue_green_etl import neo4j_arrow_client as na
from blue_green_etl import neo4j_arrow_error as error
from pyarrow.flight import FlightServerError


class TestNeo4jArrowClientAbort:
    """Test the abort() method error handling."""
    
    @patch('blue_green_etl.neo4j_arrow_client.Neo4jArrowClient._client')
    @patch('blue_green_etl.neo4j_arrow_client.Neo4jArrowClient._send_action')
    def test_abort_not_found_silent(self, mock_send_action, mock_client):
        """Test that abort() doesn't log errors for NotFound exceptions."""
        # Setup
        mock_send_action.side_effect = error.NotFound("No arrow process with name `test-db` is running")
        client = na.Neo4jArrowClient(
            host='localhost',
            port=8491,
            user='neo4j',
            password='test',
            database='test-db'
        )
        
        # Mock logger to verify no error was logged
        with patch.object(client.logger, 'error') as mock_log_error:
            result = client.abort('test-db')
            
            # Should return False (no process to abort)
            assert result is False
            
            # Should NOT log an error for NotFound
            mock_log_error.assert_not_called()
    
    @patch('blue_green_etl.neo4j_arrow_client.Neo4jArrowClient._client')
    @patch('blue_green_etl.neo4j_arrow_client.Neo4jArrowClient._send_action')
    def test_abort_success(self, mock_send_action, mock_client):
        """Test that abort() returns True when process is successfully aborted."""
        # Setup
        mock_send_action.return_value = {'name': 'test-db', 'status': 'aborted'}
        client = na.Neo4jArrowClient(
            host='localhost',
            port=8491,
            user='neo4j',
            password='test',
            database='test-db'
        )
        
        result = client.abort('test-db')
        
        # Should return True
        assert result is True
        assert client.state == na.ClientState.READY
    
    @patch('blue_green_etl.neo4j_arrow_client.Neo4jArrowClient._client')
    @patch('blue_green_etl.neo4j_arrow_client.Neo4jArrowClient._send_action')
    def test_abort_other_error_logs(self, mock_send_action, mock_client):
        """Test that abort() logs errors for non-NotFound exceptions."""
        # Setup
        mock_send_action.side_effect = error.InternalError("Server error")
        client = na.Neo4jArrowClient(
            host='localhost',
            port=8491,
            user='neo4j',
            password='test',
            database='test-db'
        )
        
        # Mock logger to verify error was logged
        with patch.object(client.logger, 'error') as mock_log_error:
            result = client.abort('test-db')
            
            # Should return False
            assert result is False
            
            # Should log an error for non-NotFound exceptions
            mock_log_error.assert_called_once()
            assert 'error aborting' in mock_log_error.call_args[0][0].lower()


class TestNeo4jArrowClientSendAction:
    """Test the _send_action() method error handling."""
    
    @patch('blue_green_etl.neo4j_arrow_client.Neo4jArrowClient._client')
    def test_send_action_not_found_silent(self, mock_client):
        """Test that _send_action() doesn't log errors when silent_not_found=True."""
        # Setup
        client = na.Neo4jArrowClient(
            host='localhost',
            port=8491,
            user='neo4j',
            password='test',
            database='test-db'
        )
        
        # Mock the flight client to raise a NotFound error
        mock_flight_client = MagicMock()
        mock_flight_client.do_action.side_effect = FlightServerError(
            "Flight returned not found error, with message: No arrow process with name `test-db` is running."
        )
        mock_client.return_value = mock_flight_client
        
        # Mock logger to verify no error was logged
        with patch.object(client.logger, 'error') as mock_log_error:
            try:
                client._send_action("ABORT", {"name": "test-db"}, silent_not_found=True)
            except error.NotFound:
                pass  # Expected
            
            # Should NOT log an error for NotFound when silent_not_found=True
            mock_log_error.assert_not_called()
    
    @patch('blue_green_etl.neo4j_arrow_client.Neo4jArrowClient._client')
    def test_send_action_not_found_not_silent(self, mock_client):
        """Test that _send_action() logs errors when silent_not_found=False."""
        # Setup
        client = na.Neo4jArrowClient(
            host='localhost',
            port=8491,
            user='neo4j',
            password='test',
            database='test-db'
        )
        
        # Mock the flight client to raise a NotFound error
        mock_flight_client = MagicMock()
        mock_flight_client.do_action.side_effect = FlightServerError(
            "Flight returned not found error, with message: No arrow process with name `test-db` is running."
        )
        mock_client.return_value = mock_flight_client
        
        # Mock logger to verify error was logged
        with patch.object(client.logger, 'error') as mock_log_error:
            try:
                client._send_action("ABORT", {"name": "test-db"}, silent_not_found=False)
            except error.NotFound:
                pass  # Expected
            
            # Should log an error for NotFound when silent_not_found=False
            mock_log_error.assert_called_once()
            assert 'send_action error' in mock_log_error.call_args[0][0].lower()
    
    @patch('blue_green_etl.neo4j_arrow_client.Neo4jArrowClient._client')
    def test_send_action_other_error_logs(self, mock_client):
        """Test that _send_action() logs errors for non-NotFound exceptions."""
        # Setup
        client = na.Neo4jArrowClient(
            host='localhost',
            port=8491,
            user='neo4j',
            password='test',
            database='test-db'
        )
        
        # Mock the flight client to raise a different error
        mock_flight_client = MagicMock()
        mock_flight_client.do_action.side_effect = FlightServerError(
            "INTERNAL: Server error occurred"
        )
        mock_client.return_value = mock_flight_client
        
        # Mock logger to verify error was logged
        with patch.object(client.logger, 'error') as mock_log_error:
            try:
                client._send_action("ABORT", {"name": "test-db"}, silent_not_found=True)
            except error.InternalError:
                pass  # Expected
            
            # Should log an error for non-NotFound exceptions
            mock_log_error.assert_called_once()
            assert 'send_action error' in mock_log_error.call_args[0][0].lower()
    
    @patch('blue_green_etl.neo4j_arrow_client.Neo4jArrowClient._client')
    def test_send_action_success(self, mock_client):
        """Test that _send_action() returns result on success."""
        # Setup
        client = na.Neo4jArrowClient(
            host='localhost',
            port=8491,
            user='neo4j',
            password='test',
            database='test-db'
        )
        
        # Mock the flight client to return success
        mock_flight_client = MagicMock()
        mock_result = MagicMock()
        mock_result.body.to_pybytes.return_value = b'{"name": "test-db", "status": "ok"}'
        mock_flight_client.do_action.return_value = iter([mock_result])
        mock_client.return_value = mock_flight_client
        
        result = client._send_action("ABORT", {"name": "test-db"})
        
        assert result == {"name": "test-db", "status": "ok"}
