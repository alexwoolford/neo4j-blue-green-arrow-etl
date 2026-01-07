"""
Configuration loader with environment variable support.

This module provides a function to load YAML configuration files with support
for environment variable substitution. Secrets can be injected at runtime
via environment variables.
"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any


def load_config(config_path: Path) -> Dict[str, Any]:
    """
    Load configuration from YAML file with environment variable substitution.
    
    Environment variables can be used in the config file using the syntax:
    - ${VAR_NAME} - Required variable (raises error if not set)
    - ${VAR_NAME:default_value} - Optional variable with default
    
    For Neo4j password, use: NEO4J_PASSWORD environment variable.
    
    Args:
        config_path: Path to YAML configuration file
        
    Returns:
        Configuration dictionary with environment variables substituted
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If required environment variable is missing
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path) as f:
        content = f.read()
    
    # Substitute environment variables
    content = _substitute_env_vars(content)
    
    # Parse YAML
    config = yaml.safe_load(content)
    
    # Special handling: If password is still a placeholder or empty, try NEO4J_PASSWORD
    if 'neo4j' in config and 'password' in config['neo4j']:
        password = config['neo4j']['password']
        if not password or password == '${NEO4J_PASSWORD}':
            env_password = os.getenv('NEO4J_PASSWORD')
            if env_password:
                config['neo4j']['password'] = env_password
            elif not password or password == '${NEO4J_PASSWORD}':
                raise ValueError(
                    "Neo4j password not found. Set NEO4J_PASSWORD environment variable "
                    "or provide password in config file."
                )
    
    return config


def _substitute_env_vars(content: str) -> str:
    """
    Substitute environment variables in string content.
    
    Supports:
    - ${VAR_NAME} - Required (raises error if not set)
    - ${VAR_NAME:default} - Optional with default value
    
    Args:
        content: String content with environment variable placeholders
        
    Returns:
        String with environment variables substituted
    """
    import re
    
    def replace_var(match):
        var_expr = match.group(1)
        
        # Check for default value
        if ':' in var_expr:
            var_name, default_value = var_expr.split(':', 1)
            return os.getenv(var_name, default_value)
        else:
            var_name = var_expr
            value = os.getenv(var_name)
            if value is None:
                raise ValueError(
                    f"Required environment variable '{var_name}' is not set. "
                    f"Please set it before running the application."
                )
            return value
    
    # Pattern: ${VAR_NAME} or ${VAR_NAME:default}
    pattern = r'\$\{([^}]+)\}'
    return re.sub(pattern, replace_var, content)

