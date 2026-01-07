"""
Pytest configuration and shared fixtures.
"""
import sys
from pathlib import Path
import pytest
from unittest.mock import Mock, MagicMock

# Add project root and src directory to Python path for imports
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@pytest.fixture
def mock_config():
    """Mock configuration dictionary."""
    return {
        'neo4j': {
            'host': 'localhost',
            'arrow_port': 8491,
            'bolt_port': 7687,
            'user': 'neo4j',
            'password': 'test_password',
            'tls': False,
            'concurrency': 10
        },
        'dataset': {
            'base_path': 'data'
        },
        'worker': {
            'arrow_table_size': 100000,
            'concurrency': 10
        }
    }


@pytest.fixture
def project_root():
    """Return the project root directory."""
    return Path(__file__).parent.parent
