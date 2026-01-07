# Managing Secrets in Configuration

This project uses environment variables to inject secrets at runtime, keeping sensitive information out of version control.

## Quick Start

1. **Copy the example config:**
   ```bash
   cp config.yaml.example config.yaml
   ```

2. **Set the Neo4j password:**
   ```bash
   export NEO4J_PASSWORD=your_password_here
   ```

3. **Run the application:**
   ```bash
   python scripts/orchestrator.py
   ```

## Environment Variables

### Required

- **`NEO4J_PASSWORD`** - Neo4j database password

### Optional

You can use environment variables for any config value using the syntax:
- `${VAR_NAME}` - Required variable (raises error if not set)
- `${VAR_NAME:default_value}` - Optional variable with default

## Configuration File

The `config.yaml` file uses environment variable placeholders:

```yaml
neo4j:
  password: ${NEO4J_PASSWORD}  # Injected from environment
```

## Setting Environment Variables

### Linux/macOS

**Temporary (current session):**
```bash
export NEO4J_PASSWORD=your_password
```

**Permanent (add to `~/.bashrc` or `~/.zshrc`):**
```bash
echo 'export NEO4J_PASSWORD=your_password' >> ~/.bashrc
source ~/.bashrc
```

**Using `.env` file (recommended for development):**
```bash
# Create .env file
echo "NEO4J_PASSWORD=your_password" > .env

# Load it (add to your shell startup)
export $(cat .env | xargs)
```

### Windows

**Command Prompt:**
```cmd
set NEO4J_PASSWORD=your_password
```

**PowerShell:**
```powershell
$env:NEO4J_PASSWORD="your_password"
```

**Permanent (System Properties):**
1. Right-click "This PC" → Properties
2. Advanced system settings → Environment Variables
3. Add new variable

## Security Best Practices

1. **`config.yaml` is safe to commit** - It uses environment variable placeholders, no secrets
2. **Never commit actual secrets** - Always use environment variables
3. **Pre-commit hooks with detect-secrets** - Battle-tested secret scanning (see [GIT_HOOKS.md](GIT_HOOKS.md))
4. **Use `.env` files for development** - Add `.env` to `.gitignore` if storing secrets there
5. **Use secret management in production** - AWS Secrets Manager, HashiCorp Vault, etc.

## Example: Using .env File

Create a `.env` file in the project root:

```bash
NEO4J_PASSWORD=your_actual_password
```

Then load it before running:

```bash
# Linux/macOS
export $(cat .env | xargs)
python scripts/orchestrator.py

# Or use a tool like python-dotenv
pip install python-dotenv
# Then add to your script:
# from dotenv import load_dotenv
# load_dotenv()
```

## Troubleshooting

### Error: "Required environment variable 'NEO4J_PASSWORD' is not set"

**Solution:** Set the environment variable:
```bash
export NEO4J_PASSWORD=your_password
```

### Error: "Neo4j password not found"

**Solution:** Make sure `NEO4J_PASSWORD` is set and exported:
```bash
export NEO4J_PASSWORD=your_password
echo $NEO4J_PASSWORD  # Should print your password
```

### Config file not found

**Solution:** Copy the example config:
```bash
cp config.yaml.example config.yaml
```

## Advanced: Multiple Environment Variables

You can use environment variables for any config value:

```yaml
neo4j:
  host: ${NEO4J_HOST:localhost}  # Uses NEO4J_HOST or defaults to localhost
  port: ${NEO4J_PORT:7687}       # Uses NEO4J_PORT or defaults to 7687
  user: ${NEO4J_USER:neo4j}      # Uses NEO4J_USER or defaults to neo4j
  password: ${NEO4J_PASSWORD}    # Required - no default
```

## CI/CD Integration

For CI/CD pipelines, set environment variables in your pipeline configuration:

**GitHub Actions:**
```yaml
env:
  NEO4J_PASSWORD: ${{ secrets.NEO4J_PASSWORD }}
```

**GitLab CI:**
```yaml
variables:
  NEO4J_PASSWORD: $NEO4J_PASSWORD
```

**Jenkins:**
```groovy
environment {
    NEO4J_PASSWORD = credentials('neo4j-password')
}
```

