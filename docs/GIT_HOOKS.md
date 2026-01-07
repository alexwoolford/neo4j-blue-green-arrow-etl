# Git Hooks for Security

This project uses the **pre-commit framework** with **detect-secrets** (Yelp) to prevent accidentally committing secrets.

## Why detect-secrets?

- ✅ **Battle-tested** - Used by Yelp and thousands of companies
- ✅ **Comprehensive** - Detects 20+ types of secrets (AWS keys, API tokens, passwords, etc.)
- ✅ **Maintained** - Actively developed and updated
- ✅ **Python-native** - Integrates seamlessly with this Python project
- ✅ **Industry standard** - Part of the pre-commit framework ecosystem

## Installation

### Automatic Installation

The setup script installs pre-commit hooks automatically:

```bash
./setup.sh
```

### Manual Installation

```bash
# Install pre-commit and detect-secrets
pip install pre-commit detect-secrets

# Or with Poetry
poetry add --group dev pre-commit detect-secrets

# Install the hooks
pre-commit install
```

### For New Clones

After cloning the repository:

```bash
# Install dependencies
poetry install

# Install hooks
pre-commit install
```

## How It Works

The pre-commit hook runs automatically before each commit and:

1. **Scans staged files** - Uses detect-secrets to find potential secrets
2. **Checks against baseline** - Compares with `.secrets.baseline` (known false positives)
3. **Blocks commit** - If new secrets are found, the commit is rejected

## Example Output

### ✅ Safe Commit (No Secrets)

```bash
$ git commit -m "Update config"
detect-secrets........................................................Passed
[main abc1234] Update config
```

### ❌ Blocked Commit (Secret Detected)

```bash
$ git commit -m "Update config"
detect-secrets........................................................Failed
- hook id: detect-secrets
- exit code: 1

Potential secrets about to be committed to git repo!

config.yaml:6:password: V1ctoria

ERROR: Potential secrets detected. If this is a false positive, update .secrets.baseline
```

## Managing False Positives

If detect-secrets flags something that's not actually a secret (e.g., example values, test data):

1. **Update the baseline:**
   ```bash
   detect-secrets scan --update .secrets.baseline
   ```

2. **Review the baseline file** - It will contain the flagged items marked as verified false positives

3. **Commit the updated baseline:**
   ```bash
   git add .secrets.baseline
   git commit -m "Update secrets baseline"
   ```

## Configuration

The hook configuration is in `.pre-commit-config.yaml`. It:

- Uses detect-secrets v1.4.0
- Excludes binary files (`.parquet`, `.lock`, etc.)
- Uses a baseline file (`.secrets.baseline`) for known false positives

## What Gets Detected

detect-secrets detects 20+ types of secrets including:

- **AWS Keys** - Access keys, secret keys
- **API Tokens** - GitHub, Slack, Stripe, Twilio, etc.
- **Passwords** - High-entropy strings that look like passwords
- **Private Keys** - SSH keys, RSA keys, etc.
- **Database Credentials** - Connection strings with passwords
- **OAuth Tokens** - Various OAuth implementations
- **And more** - See [detect-secrets documentation](https://github.com/Yelp/detect-secrets)

## Bypassing the Hook (Not Recommended)

If you absolutely need to bypass the hook (e.g., for testing), use:

```bash
git commit --no-verify -m "message"
```

**⚠️ Warning**: Only use this if you're certain there are no secrets. Never bypass for production commits.

## Running Manually

You can run the secret scanner manually:

```bash
# Scan all files
detect-secrets scan .

# Scan specific files
detect-secrets scan config.yaml

# Update baseline
detect-secrets scan --update .secrets.baseline
```

## CI/CD Integration

For additional protection, add secret scanning to your CI/CD pipeline:

**GitHub Actions:**
```yaml
- name: Check for secrets
  run: |
    pip install detect-secrets
    detect-secrets scan --baseline .secrets.baseline
```

**GitLab CI:**
```yaml
secret_detection:
  stage: test
  script:
    - pip install detect-secrets
    - detect-secrets scan --baseline .secrets.baseline
```

## Best Practices

1. **Always use environment variables** for secrets
2. **Never bypass the hook** for production code
3. **Review hook output** - it helps catch mistakes
4. **Update baseline carefully** - only for verified false positives
5. **Use CI/CD scanning** - additional layer of protection
6. **Keep dependencies updated** - `poetry update detect-secrets`

## Troubleshooting

### Hook Not Running

**Check if hook is installed:**
```bash
pre-commit run --all-files
```

**Reinstall hooks:**
```bash
pre-commit uninstall
pre-commit install
```

### Too Many False Positives

1. Update the baseline with known false positives:
   ```bash
   detect-secrets scan --update .secrets.baseline
   ```

2. Review and commit the updated baseline

### Hook Too Slow

The hook only scans staged files, so it should be fast. If it's slow:

- Check if you're staging large files
- The hook automatically excludes binary files
- Consider adding more exclusions in `.pre-commit-config.yaml`

## Related Documentation

- [SECRETS.md](SECRETS.md) - Managing secrets with environment variables
- [SETUP.md](SETUP.md) - Project setup instructions
- [detect-secrets documentation](https://github.com/Yelp/detect-secrets)
- [pre-commit documentation](https://pre-commit.com)
