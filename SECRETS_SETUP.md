# Quick Setup: Secrets Configuration

After cloning this repository, set up your configuration:

## 1. Set your Neo4j password

The `config.yaml` file is already included and uses environment variables for secrets.

```bash
export NEO4J_PASSWORD=your_password_here
```

## 3. Verify it works

```bash
export NEO4J_PASSWORD=your_password_here
python scripts/orchestrator.py --help
```

If you see the help message, you're all set!

## Permanent Setup

To make the password persistent, add to your shell startup file:

**Linux/macOS (bash):**
```bash
echo 'export NEO4J_PASSWORD=your_password_here' >> ~/.bashrc
source ~/.bashrc
```

**macOS (zsh):**
```bash
echo 'export NEO4J_PASSWORD=your_password_here' >> ~/.zshrc
source ~/.zshrc
```

**Windows (PowerShell):**
```powershell
[System.Environment]::SetEnvironmentVariable('NEO4J_PASSWORD', 'your_password_here', 'User')
```

## More Information

See [docs/SECRETS.md](docs/SECRETS.md) for detailed documentation on:
- Using `.env` files
- CI/CD integration
- Advanced configuration options

