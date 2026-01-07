"""
Tests for neo4j_arrow_error module.
"""
import pytest
from pyarrow.flight import FlightServerError
from pyarrow.lib import ArrowException
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from blue_green_etl import neo4j_arrow_error as error


class TestErrorInterpretation:
    """Test error interpretation logic."""
    
    def test_interpret_not_found_uppercase(self):
        """Test that NOT_FOUND (uppercase) is interpreted correctly."""
        e = Exception("NOT_FOUND: Database not found")
        result = error.interpret(e)
        assert isinstance(result, error.NotFound)
        assert result.message == "NOT_FOUND: Database not found"
    
    def test_interpret_not_found_lowercase_arrow_process(self):
        """Test that 'not found' with 'arrow process' is interpreted correctly."""
        e = Exception("Flight returned not found error, with message: No arrow process with name `test-db` is running. Available processes are [].")
        result = error.interpret(e)
        assert isinstance(result, error.NotFound)
    
    def test_interpret_not_found_lowercase_variations(self):
        """Test various lowercase 'not found' messages with arrow process."""
        test_cases = [
            "Flight returned not found error, with message: No arrow process with name `test` is running. Available processes are []",
            "arrow process not found",
            "Arrow process test-db not found",
            "No arrow process with name test-db is running. Available processes are []. This is a not found error",
        ]
        
        for message in test_cases:
            e = Exception(message)
            result = error.interpret(e)
            assert isinstance(result, error.NotFound), f"Failed for message: {message}"
    
    def test_interpret_already_exists(self):
        """Test that ALREADY_EXISTS is interpreted correctly."""
        e = Exception("ALREADY_EXISTS: Database already exists")
        result = error.interpret(e)
        assert isinstance(result, error.AlreadyExists)
    
    def test_interpret_invalid_argument(self):
        """Test that INVALID_ARGUMENT is interpreted correctly."""
        e = Exception("INVALID_ARGUMENT: Invalid parameter")
        result = error.interpret(e)
        assert isinstance(result, error.InvalidArgument)
    
    def test_interpret_internal_error(self):
        """Test that INTERNAL is interpreted correctly."""
        e = Exception("INTERNAL: Server error")
        result = error.interpret(e)
        assert isinstance(result, error.InternalError)
    
    def test_interpret_unknown_error(self):
        """Test that UNKNOWN is interpreted correctly."""
        e = Exception("UNKNOWN: Unknown error")
        result = error.interpret(e)
        assert isinstance(result, error.UnknownError)
    
    def test_interpret_unhandled_error(self):
        """Test that unhandled errors are returned as-is."""
        e = Exception("Some random error message")
        result = error.interpret(e)
        assert result is e  # Should return the original exception
    
    def test_interpret_flight_server_error(self):
        """Test that FlightServerError is handled."""
        e = FlightServerError("NOT_FOUND: Process not found")
        result = error.interpret(e)
        assert isinstance(result, error.NotFound)
    
    def test_interpret_arrow_exception(self):
        """Test that ArrowException is handled."""
        e = ArrowException("NOT_FOUND: Arrow error")
        result = error.interpret(e)
        assert isinstance(result, error.NotFound)


class TestNotFoundException:
    """Test NotFound exception class."""
    
    def test_not_found_creation(self):
        """Test creating a NotFound exception."""
        exc = error.NotFound("Process not found")
        assert exc.message == "Process not found"
        assert isinstance(exc, error.Neo4jArrowException)
    
    def test_not_found_str(self):
        """Test string representation of NotFound."""
        exc = error.NotFound("Process not found")
        assert "Process not found" in str(exc)
