"""
Centralized logging configuration for blue/green deployment tools.
"""
import logging
import sys
from pathlib import Path
from datetime import datetime


class FlushingFileHandler(logging.StreamHandler):
    """
    A file handler that flushes after each write to ensure immediate disk writes.
    """
    def __init__(self, filename, mode='a', encoding=None, delay=False):
        # Open file with line buffering (buffering=1) for immediate writes
        self.baseFilename = str(filename)
        if delay:
            self.stream = None
        else:
            # Use text mode with line buffering for immediate writes
            self.stream = open(filename, mode, buffering=1, encoding=encoding)
        logging.StreamHandler.__init__(self, self.stream)
        # Set the handler to not buffer
        self.stream.reconfigure(line_buffering=True) if hasattr(self.stream, 'reconfigure') else None
    
    def emit(self, record):
        """Emit a record and flush immediately."""
        logging.StreamHandler.emit(self, record)
        if self.stream:
            # Force immediate write to disk
            self.stream.flush()
            # Also sync to disk on Unix systems - this is critical for immediate visibility
            try:
                import os
                os.fsync(self.stream.fileno())
            except (OSError, AttributeError):
                # Not all file objects support fsync, or not on this OS
                pass
            # Double-check: ensure the file is actually written
            try:
                self.stream.flush()
            except:
                pass


def setup_logging(log_dir: Path = None, log_level: int = logging.INFO, console: bool = True):
    """
    Set up logging with file and optional console output.
    
    Args:
        log_dir: Directory for log files (default: logs/ in project root)
        log_level: Logging level (default: INFO)
        console: Whether to output to console (default: True)
    """
    if log_dir is None:
        log_dir = Path(__file__).parent / "logs"
    
    log_dir.mkdir(exist_ok=True)
    
    # Create log filename with timestamp (date + time)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"blue_green_etl_{timestamp}.log"
    
    # Format for log messages
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # File handler (always)
    # Use custom FlushingFileHandler to ensure logs are written immediately to disk
    file_handler = FlushingFileHandler(log_file, mode='a')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))
    root_logger.addHandler(file_handler)
    
    # Console handler (optional)
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(logging.Formatter(log_format, date_format))
        root_logger.addHandler(console_handler)
    
    return root_logger


def get_logger(name: str):
    """Get a logger instance with the given name."""
    return logging.getLogger(name)

