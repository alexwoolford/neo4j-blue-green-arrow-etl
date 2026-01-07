"""
Tests for logging configuration.
"""
import pytest
import logging
import tempfile
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from blue_green_etl.logging_config import setup_logging, get_logger


class TestLoggingConfig:
    """Test logging configuration."""
    
    def test_setup_logging_creates_file(self, tmp_path):
        """Test that setup_logging creates a log file."""
        log_dir = tmp_path / "logs"
        setup_logging(log_dir=log_dir, console=False)
        
        logger = get_logger("test")
        logger.info("Test message")
        
        # Find the log file (it will have today's date and time)
        # Since we can't predict the exact time, we'll search for files matching the pattern
        log_files = list(log_dir.glob("blue_green_etl_*.log"))
        assert len(log_files) > 0, "At least one log file should be created"
        log_file = log_files[0]  # Use the first one found
        
        assert log_file.exists(), "Log file should be created"
        
        # Read the log file
        content = log_file.read_text()
        assert "Test message" in content, "Log message should be in file"
    
    def test_setup_logging_writes_immediately(self, tmp_path):
        """Test that logs are written immediately (not buffered)."""
        log_dir = tmp_path / "logs"
        setup_logging(log_dir=log_dir, console=False)
        
        logger = get_logger("test")
        logger.info("Immediate test message")
        
        # Force a small delay to ensure any buffering would show
        import time
        time.sleep(0.1)
        
        # Find the log file (search for files matching the pattern)
        log_files = list(log_dir.glob("blue_green_etl_*.log"))
        assert len(log_files) > 0, "At least one log file should be created"
        log_file = log_files[0]  # Use the first one found
        
        # Read immediately - should be there
        content = log_file.read_text()
        assert "Immediate test message" in content, "Log should be written immediately"
    
    def test_setup_logging_console_output(self, capsys):
        """Test that console output works when enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            setup_logging(log_dir=log_dir, console=True)
            
            logger = get_logger("test")
            logger.info("Console test message")
            
            # Check console output
            captured = capsys.readouterr()
            assert "Console test message" in captured.out
    
    def test_setup_logging_no_console_output(self, capsys):
        """Test that console output is disabled when requested."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            setup_logging(log_dir=log_dir, console=False)
            
            logger = get_logger("test")
            logger.info("No console message")
            
            # Check console output (should be empty)
            captured = capsys.readouterr()
            assert "No console message" not in captured.out
    
    def test_log_file_appends(self, tmp_path):
        """Test that log file appends to existing file."""
        log_dir = tmp_path / "logs"
        setup_logging(log_dir=log_dir, console=False)
        
        logger = get_logger("test")
        logger.info("First message")
        
        # Setup again (simulating multiple calls)
        setup_logging(log_dir=log_dir, console=False)
        logger.info("Second message")
        
        # Find the log file (search for files matching the pattern)
        log_files = list(log_dir.glob("blue_green_etl_*.log"))
        assert len(log_files) > 0, "At least one log file should be created"
        log_file = log_files[0]  # Use the first one found
        
        content = log_file.read_text()
        assert "First message" in content
        assert "Second message" in content
        # Should have both messages
        assert content.count("message") == 2
