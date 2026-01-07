# Setup Guide

This guide provides detailed instructions for setting up the neo4j-blue-green-arrow-etl project.

## System Requirements

- **Operating System**: macOS, Linux, or Windows (with WSL recommended for Windows)
- **Conda**: Miniconda or Anaconda (Python 3.11+)
- **Git LFS**: Required for cloning Parquet files (~726MB). [Install here](https://git-lfs.github.com/)
- **Neo4j**: Instance running with:
  - Arrow protocol enabled on port 8491
  - Bolt protocol on port 7687
  - Database aliases feature enabled (Neo4j 5.x+)

## Quick Start

The easiest way to get started is using the automated setup script:

```bash
./setup.sh
```

This script will:
1. Check for conda installation
2. Create a conda environment with Python 3.11
3. Install Poetry (if needed)
4. Install all project dependencies

## Manual Setup

### Step 1: Install Git LFS

This repository uses Git LFS to store Parquet files. After cloning, ensure LFS files are downloaded:

```bash
# Install Git LFS (if not already installed)
# macOS (Homebrew):
brew install git-lfs

# Linux:
# See https://git-lfs.github.com/

# Initialize Git LFS (if not already done globally)
git lfs install

# After cloning, pull LFS files
git lfs pull
```

### Step 2: Install Conda

If you don't have conda installed:

**macOS/Linux:**
```bash
# Download and install Miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
```

**macOS (Homebrew):**
```bash
brew install miniconda
```

### Step 3: Create Conda Environment

```bash
conda env create -f environment.yml
```

This creates an environment named `neo4j-blue-green-arrow-etl` with Python 3.11.

### Step 4: Activate Environment

```bash
conda activate neo4j-blue-green-arrow-etl
```

### Step 5: Install Poetry

Poetry is included in the conda environment, but if you need to install it separately:

```bash
pip install poetry
```

Or using the official installer:
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### Step 6: Install Dependencies

```bash
poetry install
```

This will:
- Create a virtual environment (if using Poetry's venv management)
- Install all dependencies from `pyproject.toml`
- Generate `poetry.lock` for reproducible builds

## Verifying Setup

After setup, verify everything works:

```bash
# Check Python version
python --version  # Should show Python 3.11.x

# Check Poetry
poetry --version

# Check installed packages
poetry show

# Test imports
poetry run python -c "import pyarrow; import neo4j; import graphdatascience; print('✅ All imports successful')"
```

## Project Structure

```
neo4j-blue-green-arrow-etl/
├── environment.yml          # Conda environment definition
├── pyproject.toml           # Poetry dependency management
├── poetry.lock              # Locked dependency versions (generated)
├── setup.sh                 # Automated setup script
├── config.yaml              # Configuration (uses environment variables, safe to commit)
├── src/blue_green_etl/      # Core package (reusable modules)
├── scripts/                 # Executable scripts/CLI tools
├── tests/                   # Test suite
├── docs/                    # Documentation
├── .gitattributes           # Git LFS configuration for Parquet files
├── source_data/             # Source Parquet files (tracked via Git LFS)
└── data/                    # Generated data directory (gitignored)
```

## Dependency Management

### Adding New Dependencies

To add a new dependency:

```bash
poetry add package-name
```

For development dependencies:

```bash
poetry add --group dev package-name
```

### Updating Dependencies

```bash
# Update all dependencies to latest compatible versions
poetry update

# Update a specific package
poetry update package-name
```

### Viewing Dependencies

```bash
# List all dependencies
poetry show

# Show dependency tree
poetry show --tree
```

## Troubleshooting

### Conda Environment Issues

If you encounter issues with the conda environment:

```bash
# Remove and recreate
conda env remove -n neo4j-blue-green-arrow-etl
conda env create -f environment.yml
```

### Poetry Issues

If Poetry commands fail:

```bash
# Clear Poetry cache
poetry cache clear pypi --all

# Reinstall dependencies
poetry install --no-cache
```

### Import Errors

If you get import errors after setup:

1. Verify you're in the correct environment:
   ```bash
   conda activate neo4j-blue-green-arrow-etl
   ```

2. Verify dependencies are installed:
   ```bash
   poetry show
   ```

3. Try reinstalling:
   ```bash
   poetry install
   ```

### Python Version Mismatch

If you see Python version errors:

1. Check the environment:
   ```bash
   conda activate neo4j-blue-green-arrow-etl
   python --version
   ```

2. Recreate with correct Python version:
   ```bash
   conda env remove -n neo4j-blue-green-arrow-etl
   conda env create -f environment.yml
   ```

## Next Steps

After setup, see the main [README.md](../README.md) for:
- Configuration instructions
- Running the demo
- Blue/green deployment workflow
- Orchestration service usage
