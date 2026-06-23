"""Configuration loader for the Password Manager CLI.

Reads API key and base URL from:
1. Command-line arguments (--api-key, --base-url)
2. Environment variables (SECRETSMANAGER_API_KEY, SECRETSMANAGER_BASE_URL)
3. File (~/.secretsmanager/apikey)
"""

import os
import sys
from pathlib import Path


# Default base URL
DEFAULT_BASE_URL = "http://localhost:8000"

# Default config file path
DEFAULT_CONFIG_DIR = Path.home() / ".secretsmanager"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "apikey"


def load_api_key(cli_key: str | None = None) -> str:
    """Load the API key from CLI arg, env var, or config file.

    Priority:
    1. CLI argument (--api-key)
    2. Environment variable (SECRETSMANAGER_API_KEY)
    3. Config file (~/.secretsmanager/apikey)

    Returns:
        str: The API key

    Raises:
        SystemExit: If no API key is found
    """
    # 1. CLI argument
    if cli_key:
        return cli_key

    # 2. Environment variable
    env_key = os.environ.get("SECRETSMANAGER_API_KEY", "").strip()
    if env_key:
        return env_key

    # 3. Config file
    if DEFAULT_CONFIG_FILE.exists():
        key = DEFAULT_CONFIG_FILE.read_text().strip()
        if key:
            return key

    # Nothing found
    print(
        "Error: API key not found.\n\n"
        "Set it via one of:\n"
        "  1. --api-key <key>\n"
        "  2. export SECRETSMANAGER_API_KEY=<key>\n"
        f"  3. echo <key> > {DEFAULT_CONFIG_FILE}\n",
        file=sys.stderr,
    )
    sys.exit(1)


def load_base_url(cli_url: str | None = None) -> str:
    """Load the base URL from CLI arg or env var.

    Priority:
    1. CLI argument (--base-url)
    2. Environment variable (SECRETSMANAGER_BASE_URL)
    3. Default URL

    Returns:
        str: The base URL
    """
    # 1. CLI argument
    if cli_url:
        return cli_url.rstrip("/")

    # 2. Environment variable
    env_url = os.environ.get("SECRETSMANAGER_BASE_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")

    # 3. Default
    return DEFAULT_BASE_URL


def save_api_key(key: str) -> Path:
    """Save the API key to the config file.

    Args:
        key: The API key to save

    Returns:
        Path: The path where the key was saved
    """
    config_dir = DEFAULT_CONFIG_DIR
    config_dir.mkdir(parents=True, exist_ok=True)

    config_file = DEFAULT_CONFIG_FILE
    config_file.write_text(key)
    # Set restrictive permissions (owner read/write only)
    config_file.chmod(0o600)

    return config_file
