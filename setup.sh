#!/bin/bash
# Setup script for neo4j-blue-green-arrow-etl project
# This script creates a conda environment and installs dependencies using Poetry

set -e  # Exit on error

echo "🚀 Setting up neo4j-blue-green-arrow-etl project..."
echo ""

# Check if conda is installed
if ! command -v conda &> /dev/null; then
    echo "❌ Error: conda is not installed or not in PATH"
    echo "Please install Miniconda or Anaconda first:"
    echo "  https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

# Check if poetry is installed (might be in conda env or system)
if ! command -v poetry &> /dev/null; then
    echo "📦 Poetry not found. Installing Poetry..."
    # Install poetry in the conda environment we're about to create
    # We'll do this after creating the environment
    POETRY_NEEDED=true
else
    POETRY_NEEDED=false
    echo "✅ Poetry found: $(poetry --version)"
fi

# Create conda environment
ENV_NAME="neo4j-blue-green-arrow-etl"
echo "📦 Creating conda environment: $ENV_NAME"

if conda env list | grep -q "^${ENV_NAME} "; then
    echo "⚠️  Environment '$ENV_NAME' already exists."
    read -p "Do you want to remove and recreate it? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️  Removing existing environment..."
        conda env remove -n "$ENV_NAME" -y
    else
        echo "📝 Using existing environment. Activating..."
        eval "$(conda shell.bash hook)"
        conda activate "$ENV_NAME"
        
        # Install poetry if needed
        if [ "$POETRY_NEEDED" = true ]; then
            echo "📦 Installing Poetry in conda environment..."
            pip install poetry
        fi
        
        echo "📦 Installing dependencies with Poetry..."
        poetry install
        
        # Install pre-commit hooks
        if [ -d ".git" ] && command -v pre-commit &> /dev/null; then
            echo ""
            echo "🛡️  Installing pre-commit hooks..."
            pre-commit install
            echo "✅ Pre-commit hooks installed"
        fi
        
        echo ""
        echo "✅ Setup complete!"
        echo ""
        echo "To activate the environment, run:"
        echo "  conda activate $ENV_NAME"
        echo ""
        echo "🔐 Don't forget to set your Neo4j password:"
        echo "  export NEO4J_PASSWORD=your_password"
        exit 0
    fi
fi

# Create the environment
conda env create -f environment.yml

# Activate the environment
echo "🔌 Activating conda environment..."
eval "$(conda shell.bash hook)"
conda activate "$ENV_NAME"

# Install poetry if needed
if [ "$POETRY_NEEDED" = true ]; then
    echo "📦 Installing Poetry..."
    pip install poetry
fi

# Configure poetry to create virtualenv in project (optional, but cleaner)
poetry config virtualenvs.in-project true --local

# Install dependencies
echo "📦 Installing Python dependencies with Poetry..."
poetry install

# Install pre-commit hooks for security (using detect-secrets)
if [ -d ".git" ]; then
    echo ""
    echo "🛡️  Installing pre-commit hooks for secret detection..."
    if command -v pre-commit &> /dev/null; then
        pre-commit install
        echo "✅ Pre-commit hooks installed"
        echo "   Using detect-secrets (Yelp) for secret scanning"
    else
        echo "⚠️  Warning: pre-commit not found"
        echo "   Install with: pip install pre-commit detect-secrets"
        echo "   Then run: pre-commit install"
    fi
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "To activate the environment, run:"
echo "  conda activate $ENV_NAME"
echo ""
echo "Or use Poetry to run commands:"
echo "  poetry run python scripts/setup_demo_data.py"
echo "  poetry run python scripts/load_with_aliases.py --customer customer1 --timestamp 1767741427"
echo ""
echo "🔐 Don't forget to set your Neo4j password:"
echo "  export NEO4J_PASSWORD=your_password"
