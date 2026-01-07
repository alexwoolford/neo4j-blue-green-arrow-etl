# Project Structure

This document describes the organization of the neo4j-blue-green-arrow-etl project.

## Directory Layout

```
neo4j-blue-green-arrow-etl/
├── src/
│   └── blue_green_etl/          # Core package (reusable modules)
│       ├── __init__.py
│       ├── neo4j_arrow_client.py
│       ├── neo4j_arrow_error.py
│       ├── neo4j_pq.py
│       ├── neo4j_utils.py
│       └── logging_config.py
│
├── scripts/                      # Executable scripts/CLI tools
│   ├── setup_demo_data.py
│   ├── load_with_aliases.py
│   ├── manage_aliases.py
│   ├── cleanup_demo.py
│   ├── simulate_snapshot.py
│   ├── demo_workflow.py
│   └── orchestrator.py
│
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_neo4j_arrow_client.py
│   ├── test_neo4j_arrow_error.py
│   ├── test_neo4j_utils.py
│   ├── test_logging_config.py
│   └── test_orchestrator_health.py
│
├── docs/                         # Documentation
│   ├── SETUP.md
│   ├── DEMO.md
│   ├── ORCHESTRATOR.md
│   ├── SHARING.md
│   ├── ALIASES.md
│   ├── CODE_REVIEW.md
│   ├── ENHANCEMENT_PLAN.md
│   └── MEMORY_MONITORING.md
│
├── data/                         # Generated demo data (gitignored)
│   └── {customer}/{timestamp}/
│
├── source_data/                  # Source Parquet files (tracked via Git LFS)
│   ├── nodes/
│   └── relationships/
│
├── logs/                         # Log files (gitignored)
│
├── htmlcov/                      # Coverage reports (gitignored)
│
├── config.yaml                   # Configuration file
├── pyproject.toml               # Poetry configuration
├── poetry.lock                   # Locked dependencies
├── environment.yml               # Conda environment
├── pytest.ini                    # Pytest configuration
├── setup.sh                      # Setup script
└── README.md                     # Main documentation
```

## Organization Principles

### 1. **Package Structure** (`src/blue_green_etl/`)
- Contains reusable, importable modules
- Follows Python package conventions
- Can be installed as a package via Poetry
- Modules are imported as: `from blue_green_etl import ...`

### 2. **Scripts** (`scripts/`)
- Executable CLI tools and workflows
- Each script is standalone and can be run directly
- Scripts import from the package: `from blue_green_etl import ...`
- Scripts also import from each other when needed: `from scripts.load_with_aliases import ...`

### 3. **Tests** (`tests/`)
- Test suite for the package and scripts
- Uses pytest framework
- Imports from package: `from blue_green_etl import ...`
- Imports from scripts: `from scripts.orchestrator import ...`

### 4. **Documentation** (`docs/`)
- All documentation files (except README.md)
- README.md stays in root for GitHub visibility

### 5. **Data**
- `source_data/`: Original Parquet files (tracked in git via LFS)
- `data/`: Generated demo data (gitignored, created by `setup_demo_data.py`)

## Running Scripts

All scripts are in the `scripts/` directory. Run them from the project root:

```bash
# From project root
python scripts/setup_demo_data.py
python scripts/load_with_aliases.py --customer customer1 --timestamp 1767741427
python scripts/orchestrator.py
```

Or add scripts to PATH or create symlinks if preferred.

## Import Patterns

### In Package Modules (`src/blue_green_etl/`)
```python
# Use relative imports for package-internal imports
from . import neo4j_arrow_client as na
from . import neo4j_arrow_error as error
```

### In Scripts (`scripts/`)
```python
# Add project root to path
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import from package
from blue_green_etl import neo4j_arrow_client as na
from blue_green_etl.neo4j_utils import get_driver

# Import from other scripts if needed
from scripts.load_with_aliases import load_database
```

### In Tests (`tests/`)
```python
# Add project root to path
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import from package
from blue_green_etl.neo4j_utils import get_driver

# Import from scripts
from scripts.orchestrator import Neo4jHealthChecker
```

## Path References

All path references in scripts are relative to the **project root**, not the script location:

```python
# Correct: Use project_root
project_root = Path(__file__).parent.parent
config_path = project_root / "config.yaml"
data_path = project_root / "data"

# Incorrect: Don't use script's parent
# config_path = Path(__file__).parent / "config.yaml"  # Wrong!
```

## Benefits of This Structure

1. **Clear Separation**: Package code vs. scripts vs. tests
2. **Reusability**: Package can be imported by other projects
3. **Maintainability**: Easy to find and organize code
4. **Scalability**: Easy to add new modules or scripts
5. **Standard**: Follows Python packaging best practices

