# Blue/Green Deployment Demo

This project demonstrates blue/green database deployments using Neo4j Arrow loader with database aliases.

**This is a self-contained package** - all required files are included in this directory and it can be shared as a complete unit.

> 💡 **Project Structure**: See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for details on how the project is organized.

> 💡 **Sharing this package?** See [docs/SHARING.md](docs/SHARING.md) for instructions on creating a standalone repository or package.

## Prerequisites

- **Conda** (Miniconda or Anaconda) - [Install here](https://docs.conda.io/en/latest/miniconda.html)
- **Neo4j Enterprise Edition** - This solution uses Neo4j Enterprise Edition features:
  - **Multi-database support** - Each customer deployment is a separate database
  - **Database aliases** - Enable zero-downtime blue/green deployments
  - **Arrow protocol** - High-performance bulk loading (port 8491)
  - **Online backups** - Available via `neo4j-admin database backup`
  - **Clustering support** - Fully cluster-compatible (all operations use Bolt protocol)
- **Git LFS** (Large File Storage) - Required for cloning Parquet files. [Install here](https://git-lfs.github.com/)

> **📘 Enterprise Features**: This solution uses **only** native Neo4j Enterprise Edition features. No third-party plugins or workarounds. See [docs/ENTERPRISE_REVIEW.md](docs/ENTERPRISE_REVIEW.md) for details.

## Quick Demo (3 Commands)

This is the core demo workflow:

```bash
# 1. Start Prefect server (Terminal 1)
poetry run prefect server start

# 2. Run the supervisor process (Terminal 2)
python scripts/orchestrator_prefect.py --run

# 3. Simulate new data arriving (Terminal 3)
python scripts/simulate_snapshot.py --customer customer1
```

**That's it!** The orchestrator will automatically:
- Detect the new snapshot within 30 seconds
- Load it into Neo4j using Arrow protocol
- Switch the alias to the new database (if it's the latest)
- Clean up old databases

View the Prefect UI at `http://localhost:4200` to see the workflow in action.

> **Prerequisites**: Before running the demo, ensure:
> - Dependencies installed: `poetry install`
> - Neo4j is running (Enterprise Edition with Arrow protocol on port 8491)
> - Demo data is set up: `python scripts/setup_demo_data.py`
> - Environment is configured: `export NEO4J_PASSWORD=your_password`

See [docs/DEMO.md](docs/DEMO.md) for detailed demonstration scenarios.

## Initial Setup

This project uses **Conda** for environment management and **Poetry** for Python dependency management. 

> **Note**: This repository uses **Git LFS** to store Parquet files (~726MB total). After cloning, run `git lfs pull` to download the actual files, or they will be downloaded automatically when you run `setup_demo_data.py`.

> **🔐 Secrets Management**: This project uses environment variables for secrets. See [docs/SECRETS.md](docs/SECRETS.md) for details. Quick start: `export NEO4J_PASSWORD=your_password`  
> **🛡️ Secret Scanning**: Pre-commit hooks use detect-secrets (Yelp) to prevent committing secrets. See [docs/GIT_HOOKS.md](docs/GIT_HOOKS.md) for details.

To set up the project:

### Quick Setup (Recommended)

Run the automated setup script:

```bash
./setup.sh
```

This will:
1. Create a conda environment named `neo4j-blue-green-arrow-etl`
2. Install Poetry (if not already installed)
3. Install all Python dependencies

### Manual Setup

If you prefer to set up manually:

```bash
# 1. Create conda environment
conda env create -f environment.yml

# 2. Activate the environment
conda activate neo4j-blue-green-arrow-etl

# 3. Install Poetry (if not already installed)
pip install poetry

# 4. Install dependencies
poetry install
```

### Using the Environment

After setup, you can use the project in two ways:

**Option 1: Activate conda environment and run directly**
```bash
conda activate neo4j-blue-green-arrow-etl
python scripts/setup_demo_data.py
python scripts/load_with_aliases.py --customer customer1 --timestamp 1767741427
```

**Option 2: Use Poetry to run commands (recommended)**
```bash
# Make sure dependencies are installed first
poetry install

# Then run commands
poetry run python scripts/setup_demo_data.py
poetry run python scripts/load_with_aliases.py --customer customer1 --timestamp 1767741427
```

Poetry ensures you're always using the correct dependencies and Python version.

> **Important**: Always run `poetry install` first after cloning or creating the environment. This installs all dependencies into Poetry's virtual environment.

> **Note**: For maximum reproducibility, the `poetry.lock` file (generated after `poetry install`) should be committed to version control. This ensures all users get the exact same dependency versions.

## Testing

This project uses **pytest** for testing and **pytest-cov** for coverage tracking.

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage report
poetry run pytest --cov=. --cov-report=html

# Run specific test file
poetry run pytest tests/test_neo4j_arrow_error.py

# Run with verbose output
poetry run pytest -v
```

### Coverage Reports

Coverage reports are generated in multiple formats:
- **Terminal**: Shows missing lines inline
- **HTML**: `htmlcov/index.html` - Interactive HTML report
- **XML**: `coverage.xml` - For CI/CD integration

View the HTML report:
```bash
poetry run pytest --cov=. --cov-report=html
open htmlcov/index.html  # macOS
# or
xdg-open htmlcov/index.html  # Linux
```

### Test Structure

Tests are located in the `tests/` directory:
- `test_neo4j_arrow_error.py` - Error interpretation and exception handling
- `test_neo4j_arrow_client.py` - Neo4j Arrow client error handling
- `conftest.py` - Shared fixtures and configuration

See [tests/README.md](tests/README.md) for more details on writing and running tests.

## Logging

All scripts use consistent logging with timestamps:
- **Console output**: Timestamped log messages
- **File output**: Logs saved to `logs/blue_green_etl_YYYYMMDD_HHMMSS.log` (includes date and time)
- **Format**: `YYYY-MM-DD HH:MM:SS - logger_name - LEVEL - message`

Log files are automatically created in the `logs/` directory.

## Structure

### Source Data (Tracked in Git)

The original Parquet files are stored in `source_data/` and are tracked in git:
```
source_data/
  nodes/
    Entity/entities.parquet
    Address/addresses.parquet
  relationships/
    HAS_PRINCIPAL_ADDRESS/principal_address_relationship.parquet
    HAS_MAILING_ADDRESS/mailing_address_relationship.parquet
    HAS_AGENT_ADDRESS/agent_address_relationship.parquet
```

### Generated Data (Not Tracked)

The `setup_demo_data.py` script copies source data to multiple customer/timestamp locations for simulation:
```
data/  (ignored by git)
  customer1/
    1767741427/
      nodes/
        Entity/entities.parquet
        Address/addresses.parquet
      relationships/
        HAS_PRINCIPAL_ADDRESS/...
        HAS_MAILING_ADDRESS/...
        HAS_AGENT_ADDRESS/...
    1767741527/
      nodes/...
      relationships/...
  customer2/
    1767741427/...
    1767741527/...
  customer3/
    1767741427/...
    1767741527/...
```

**Note**: The `data/` directory is generated and ignored by git. After cloning, run `python scripts/setup_demo_data.py` to create the demo data structure.

## Database Naming

- **Database names**: `{customer_id}-{timestamp}` (e.g., `customer1-1767741427`)
- **Aliases**: `{customer_id}` (e.g., `customer1`)

The alias always points to the "active" database for that customer.

## Setup

1. **Create demo data** (copies source_data/ to multiple customer/timestamp locations):
   ```bash
   python scripts/setup_demo_data.py
   ```
   
   This copies the Parquet files from `source_data/` to `data/{customer}/{timestamp}/` 
   for each customer and timestamp combination (6 total datasets).

2. **Load a database and switch alias**:
   ```bash
   python scripts/load_with_aliases.py --customer customer1 --timestamp 1767741427
   ```

3. **Load without switching alias** (for blue deployment):
   ```bash
   python scripts/load_with_aliases.py --customer customer1 --timestamp 1767741527 --no-switch
   ```

4. **Switch alias manually** (for green cutover):
   ```bash
   python scripts/manage_aliases.py create customer1 customer1-1767741527
   ```

5. **List aliases and databases**:
   ```bash
   python scripts/manage_aliases.py list-aliases
   python scripts/manage_aliases.py list-databases
   ```

6. **Cleanup demo data** (drops aliases and databases):
   ```bash
   # Clean up everything
   python scripts/cleanup_demo.py
   
   # Clean up specific customer
   python scripts/cleanup_demo.py --customer customer1
   
   # List what would be cleaned up
   python scripts/cleanup_demo.py --list
   
   # Clean up databases only (keep aliases)
   python scripts/cleanup_demo.py --no-aliases
   ```

## Blue/Green Deployment Pattern

1. **Blue (current)**: Load new data to `customer1-1767741527` with `--no-switch`
2. **Verify**: Test queries against `customer1-1767741527` directly
3. **Green (cutover)**: Switch alias `customer1` to point to `customer1-1767741527`
4. **Cleanup**: Drop old database `customer1-1767741427` when ready

## Example Workflow

```bash
# Setup demo data
python scripts/setup_demo_data.py

# Load initial deployment (blue)
python scripts/load_with_aliases.py --customer customer1 --timestamp 1767741427

# Load new deployment (green) without switching
python scripts/load_with_aliases.py --customer customer1 --timestamp 1767741527 --no-switch

# After verification, switch alias (cutover)
python scripts/manage_aliases.py create customer1 customer1-1767741527

# Query using alias (points to active database)
# In Cypher: USE customer1
# Or in GDS: database='customer1'
```

## Additional Demo Options

### Manual Demo (Sequential)

For controlled, step-by-step demonstrations:

```bash
# Generate demo data
python scripts/setup_demo_data.py

# Run complete demo workflow (sequential)
python scripts/demo_workflow.py
```

### Original Orchestrator (Without Prefect)

The original orchestrator (without Prefect UI) is still available. See [docs/ORCHESTRATOR.md](docs/ORCHESTRATOR.md) for details.

```bash
# Start the orchestrator (sequential - 1 worker)
python scripts/orchestrator.py

# In another terminal, simulate dropping a new snapshot
python scripts/simulate_snapshot.py --customer customer1
```

## Production Operations

### Backup and Restore

For production deployments, see [docs/BACKUP_RESTORE.md](docs/BACKUP_RESTORE.md) for:
- Neo4j Enterprise backup procedures using `neo4j-admin database backup`
- Backup scheduling and retention strategies
- Restore procedures and point-in-time recovery
- Integration with blue/green deployment pattern

### Cluster Deployment

This solution is fully cluster-compatible. See [docs/CLUSTER_DEPLOYMENT.md](docs/CLUSTER_DEPLOYMENT.md) for:
- Cluster configuration and connection setup
- Backup server configuration in clusters
- High availability considerations
- Performance and monitoring in cluster environments

### Enterprise Edition Features

This solution leverages Neo4j Enterprise Edition features:
- ✅ **Multi-database support** - Isolated databases per customer deployment
- ✅ **Database aliases** - Zero-downtime cutover between deployments
- ✅ **Arrow protocol** - High-performance bulk data loading
- ✅ **Online backups** - Backup databases while running
- ✅ **Cluster support** - Fully compatible with Neo4j clusters
- ✅ **ACID compliance** - Transactional consistency guaranteed
- ✅ **Concurrency control** - Automatic retry and deadlock handling

See [docs/ENTERPRISE_REVIEW.md](docs/ENTERPRISE_REVIEW.md) for a comprehensive review of Enterprise Edition alignment.

