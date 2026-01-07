# Testing

This directory contains unit tests for the neo4j-blue-green-arrow-etl project.

## Running Tests

### Run all tests
```bash
poetry run pytest
```

### Run with coverage report
```bash
poetry run pytest --cov=. --cov-report=html
```

### Run specific test file
```bash
poetry run pytest tests/test_neo4j_arrow_error.py
```

### Run specific test
```bash
poetry run pytest tests/test_neo4j_arrow_error.py::TestErrorInterpretation::test_interpret_not_found_uppercase
```

### Run with verbose output
```bash
poetry run pytest -v
```

## Test Structure

- `test_neo4j_arrow_error.py` - Tests for error interpretation and exception handling
- `test_neo4j_arrow_client.py` - Tests for Neo4j Arrow client error handling
- `conftest.py` - Shared pytest fixtures and configuration

## Coverage

Coverage reports are generated in:
- Terminal: `--cov-report=term-missing`
- HTML: `htmlcov/index.html`
- XML: `coverage.xml` (for CI/CD integration)

Current coverage focuses on the error handling modules we've recently fixed. As we add more tests, coverage will increase.

## Writing New Tests

1. Create test files with `test_*.py` naming convention
2. Use pytest fixtures from `conftest.py` when available
3. Mark tests appropriately:
   - `@pytest.mark.unit` - Fast unit tests (no external dependencies)
   - `@pytest.mark.integration` - Integration tests (may require Neo4j)
   - `@pytest.mark.slow` - Tests that take a long time

Example:
```python
import pytest
from unittest.mock import Mock, patch

@pytest.mark.unit
def test_my_function():
    """Test description."""
    # Test code here
    assert True
```
