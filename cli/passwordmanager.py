#!/usr/bin/env python3
"""Password Manager CLI - command-line interface for the Password Manager API.

Usage:
    passwordmanager [list|create|retrieve|delete] [secret|group] [name|id]

Configuration:
    The CLI reads the API key from (in priority order):
      1. --api-key <key> flag
      2. $SECRETSMANAGER_API_KEY environment variable
      3. ~/.secretsmanager/apikey file

    The base URL is read from (in priority order):
      1. --base-url <url> flag
      2. $SECRETSMANAGER_BASE_URL environment variable
      3. http://localhost:8000 (default)

Commands:
    list secret [--group <group_id>]          List all secrets
    list group                                List all secret groups
    create secret                             Create a new secret interactively
    create secret-ssh                         Generate and create a new SSH key
    retrieve secret <id|name>                 Retrieve and display a secret
    retrieve secret-ssh <id>                  Retrieve an SSH key private key
    delete secret <id|name>                   Delete a secret
    delete group <id|name>                    Delete a secret group
    token create <name>                       Create a new API token
    token list                                List all API tokens
    setup                                     Save API key to config file

Options:
    --api-key <key>      API key for authentication
    --base-url <url>     Base URL of the Password Manager service
    --json               Output in JSON format
    -h, --help           Show this help message
"""

import argparse
import json
import sys
from pathlib import Path

from . import config
from .api import PMClient
from .utils import (
    bold,
    blue,
    dim,
    green,
    mask_data,
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
    red,
    yellow,
    format_json,
)

SECRET_TYPES = ["password", "api_key", "credential", "custom"]


def cmd_list_secrets(client, args):
    """List all secrets."""
    secrets = client.list_secrets(group_id=args.group)
    if not secrets:
        print(dim("  No secrets found"))
        return
    headers = ["ID", "Title", "Type", "Group", "Owner"]
    rows = []
    for s in secrets:
        rows.append([
            str(s["id"]),
            s["title"],
            s["secret_type"],
            s.get("group_name", "?"),
            s.get("owner_username", "?"),
        ])
    print_table(headers, rows)
    print(f"  {blue('Total:')}\n  {len(secrets)} secret(s)")


def cmd_list_groups(client, args):
    """List all secret groups."""
    groups = client.list_secret_groups()
    if not groups:
        print(dim("  No secret groups found"))
        return
    headers = ["ID", "Name", "Target Group", "Owner", "Shared"]
    rows = []
    for g in groups:
        shared = "Yes" if g.get("group_ids") else "No"
        rows.append([
            str(g["id"]),
            g["name"],
            g.get("group_name", "?"),
            g.get("owner_username", "?"),
            shared,
        ])
    print_table(headers, rows)
    print(f"  {blue('Total:')}\n  {len(groups)} group(s)")


def cmd_create_secret(client, args):
    """Create a new secret interactively."""
    user_groups = client.list_user_groups()
    if not user_groups:
        print_error("No user groups available. Create a user group first.")
        sys.exit(1)
    print_info("Creating a new secret...")
    title = args.title if args.title else input("  Title: ").strip()
    if not title:
        print_error("Title is required")
        sys.exit(1)
    print(f"  Types: {', '.join(SECRET_TYPES)}")
    secret_type = args.type if args.type else input("  Type [password]: ").strip() or "password"
    if secret_type not in SECRET_TYPES:
        print_error(f"Invalid type. Choose from: {', '.join(SECRET_TYPES)}")
        sys.exit(1)
    print("  Target Groups:")
    for i, g in enumerate(user_groups):
        print(f"    [{i}] {g['name']}")
    group_idx = 0
    if not args.group_id:
        try:
            group_idx = int(input("  Select group [0]: ") or "0")
        except ValueError:
            group_idx = 0
    group_id = user_groups[group_idx]["id"]
    description = args.description if args.description else input("  Description [none]: ").strip() or None
    username = args.username if args.username else input("  Username [none]: ").strip() or None
    url = args.url if args.url else input("  URL [none]: ").strip() or None
    encrypted_data = args.data if args.data else input("  Secret data: ").strip()
    if not encrypted_data:
        print_error("Secret data is required")
        sys.exit(1)
    key_length = None
    if secret_type == "password" and args.key_length:
        key_length = args.key_length
    try:
        result = client.create_secret(
            title=title, secret_type=secret_type, encrypted_data=encrypted_data,
            group_id=group_id, description=description, username=username,
            url=url, key_length=key_length,
        )
        print_success(f"Secret '{title}' created (ID: {result['id']})")
    except SystemExit:
        print_error("Failed to create secret")
        sys.exit(1)


def cmd_create_secret_ssh(client, args):
    """Generate and create a new SSH key."""
    user_groups = client.list_user_groups()
    if not user_groups:
        print_error("No user groups available.")
        sys.exit(1)
    key_length = args.key_length or 4096
    comment = args.comment or ""
    print_info(f"Generating SSH key (RSA, {key_length} bits)...")
    try:
        response = client.generate_ssh_key(key_length=key_length, comment=comment)
    except SystemExit:
        print_error("Failed to generate SSH key")
        sys.exit(1)
    print(f"\n  {green('Private Key:')}")
    print(f"  {dim(response['private_key'])}\n")
    print(f"  {green('Fingerprint:')} {response['fingerprint']}")
    print(f"  {green('Public Key:')} {response['public_key']}")
    save = input("\n  Save this key to the password manager? [y/N]: ").strip().lower()
    if save != "y":
        print_info("Key not saved. Copy it manually.")
        return
    print("  Target Groups:")
    for i, g in enumerate(user_groups):
        print(f"    [{i}] {g['name']}")
    group_idx = int(input("  Select group [0]: ") or "0")
    group_id = user_groups[group_idx]["id"]
    title = f"SSH Key - {response['fingerprint'][-12:]}"
    try:
        result = client.create_secret(
            title=title, secret_type="ssh_key", encrypted_data=response["private_key"],
            group_id=group_id, key_length=key_length,
        )
        print_success(f"SSH key saved (ID: {result['id']})")
    except SystemExit:
        print_error("Failed to save SSH key")
        sys.exit(1)


def cmd_retrieve_secret(client, args):
    """Retrieve and display a secret (masked data)."""
    query = args.query
    secrets = client.list_secrets()
    secret = None
    if query.isdigit():
        try:
            secret = client.get_secret(int(query))
        except SystemExit:
            pass
    else:
        for s in secrets:
            if query.lower() in s["title"].lower():
                secret = s
                break
    if not secret:
        print_error(f"Secret '{query}' not found")
        sys.exit(1)
    try:
        masked = client.get_secret_masked(secret["id"])
    except SystemExit:
        print_error(f"Failed to retrieve secret '{secret['title']}'")
        sys.exit(1)
    print(f"\n  {bold('Title:')}       {masked['title']}")
    print(f"  {bold('Type:')}        {masked['secret_type']}")
    print(f"  {bold('Description:')} {masked.get('description', '-')}")
    print(f"  {bold('Username:')}    {masked.get('username', '-')}")
    print(f"  {bold('URL:')}         {masked.get('url', '-')}")
    print(f"  {bold('Data:')}        {masked['decrypted_data']}")
    print(f"\n  {dim('Audit:')} {masked.get('audit_event', '-')} at {masked.get('audit_timestamp', '-')}")


def cmd_reveal_secret(client, args):
    """Reveal and display a secret with decrypted data."""
    query = args.query
    secrets = client.list_secrets()
    secret = None
    if query.isdigit():
        try:
            secret = client.get_secret(int(query))
        except SystemExit:
            pass
    else:
        for s in secrets:
            if query.lower() in s["title"].lower():
                secret = s
                break
    if not secret:
        print_error(f"Secret '{query}' not found")
        sys.exit(1)
    try:
        revealed = client.reveal_secret(secret["id"])
    except SystemExit:
        print_error(f"Failed to reveal secret '{secret['title']}'")
        sys.exit(1)
    print(f"\n  {bold('Title:')}       {revealed['title']}")
    print(f"  {bold('Type:')}        {revealed['secret_type']}")
    print(f"  {bold('Description:')} {revealed.get('description', '-')}")
    print(f"  {bold('Username:')}    {revealed.get('username', '-')}")
    print(f"  {bold('URL:')}         {revealed.get('url', '-')}")
    print(f"  {bold('Data:')}        {revealed['decrypted_data']}")
    print(f"\n  {dim('Audit:')} {revealed.get('audit_event', '-')} at {revealed.get('audit_timestamp', '-')}")


def cmd_retrieve_secret_ssh(client, args):
    """Retrieve an SSH key private key."""
    secret_id = args.query
    try:
        secret_id = int(secret_id)
    except ValueError:
        print_error(f"'{secret_id}' is not a valid ID")
        sys.exit(1)
    try:
        masked = client.get_secret_masked(secret_id)
    except SystemExit:
        print_error("Secret not found or access denied")
        sys.exit(1)
    if masked["secret_type"] != "ssh_key":
        print_error("This secret is not an SSH key")
        sys.exit(1)
    print(f"\n  {bold('Private Key:')}")
    print(f"  {dim(masked['decrypted_data'])}\n")


def cmd_delete_secret(client, args):
    """Delete a secret."""
    query = args.query
    secrets = client.list_secrets()
    secret = None
    if query.isdigit():
        try:
            secret = client.get_secret(int(query))
        except SystemExit:
            pass
    else:
        for s in secrets:
            if query.lower() in s["title"].lower():
                secret = s
                break
    if not secret:
        print_error(f"Secret '{query}' not found")
        sys.exit(1)
    confirm = input(f"  Delete secret '{secret['title']}' (ID: {secret['id']})? [y/N]: ").strip().lower()
    if confirm != "y":
        print_info("Cancelled")
        return
    try:
        client.delete_secret(secret["id"])
        print_success(f"Secret '{secret['title']}' deleted")
    except SystemExit:
        print_error("Failed to delete secret")
        sys.exit(1)


def cmd_delete_group(client, args):
    """Delete a secret group."""
    query = args.query
    groups = client.list_secret_groups()
    group = None
    if query.isdigit():
        try:
            group = client.get_secret_group(int(query))
        except SystemExit:
            pass
    else:
        for g in groups:
            if query.lower() in g["name"].lower():
                group = g
                break
    if not group:
        print_error(f"Group '{query}' not found")
        sys.exit(1)
    confirm = input(f"  Delete group '{group['name']}' (ID: {group['id']})? [y/N]: ").strip().lower()
    if confirm != "y":
        print_info("Cancelled")
        return
    try:
        client.delete_secret_group(group["id"])
        print_success(f"Group '{group['name']}' deleted")
    except SystemExit:
        print_error("Failed to delete group")
        sys.exit(1)


def cmd_create_group(client, args):
    """Create a new secret group interactively."""
    user_groups = client.list_user_groups()
    if not user_groups:
        print_error("No user groups available.")
        sys.exit(1)
    print_info("Creating a new secret group...")
    name = args.name if args.name else input("  Name: ").strip()
    if not name:
        print_error("Name is required")
        sys.exit(1)
    description = args.description if args.description else input("  Description [none]: ").strip() or None
    print("  Target Groups:")
    for i, g in enumerate(user_groups):
        print(f"    [{i}] {g['name']}")
    group_idx = int(input("  Select group [0]: ") or "0")
    group_id = user_groups[group_idx]["id"]
    member_ids_str = input("  Share with user group IDs (comma-separated, or empty for private): ").strip()
    member_ids = []
    if member_ids_str:
        try:
            member_ids = [int(x.strip()) for x in member_ids_str.split(",")]
        except ValueError:
            print_error("Invalid group IDs")
            sys.exit(1)
    try:
        result = client.create_secret_group(
            name=name, group_id=group_id, description=description,
            member_group_ids=member_ids if member_ids else [],
        )
        print_success(f"Group '{name}' created (ID: {result['id']})")
    except SystemExit:
        print_error("Failed to create group")
        sys.exit(1)


def cmd_list_tokens(client, args):
    """List all API tokens."""
    tokens = client.list_api_tokens()
    if not tokens:
        print(dim("  No API tokens found"))
        return
    headers = ["ID", "Name", "Active", "Created", "Last Used"]
    rows = []
    for t in tokens:
        rows.append([
            str(t["id"]), t["name"],
            "Yes" if t["is_active"] else "No",
            t["created_at"][:10] if t["created_at"] else "-",
            t["last_used_at"][:10] if t["last_used_at"] else "Never",
        ])
    print_table(headers, rows)


def cmd_create_token(client, args):
    """Create a new API token."""
    name = args.name
    if not name:
        name = input("  Token name: ").strip()
        if not name:
            print_error("Name is required")
            sys.exit(1)
    description = input("  Description [none]: ").strip() or None
    try:
        result = client.create_api_token(name=name, description=description)
        print(f"\n  {green('Token:')} {result['token']}")
        print(f"  {dim('Copy this token now - it will not be shown again!')}\n")
        print_success(f"Token '{name}' created (ID: {result['token_id']})")
    except SystemExit:
        print_error("Failed to create token")
        sys.exit(1)


def cmd_revoke_token(client, args):
    """Revoke an API token."""
    token_id = args.token_id
    try:
        token_id = int(token_id)
    except ValueError:
        print_error(f"'{token_id}' is not a valid ID")
        sys.exit(1)
    confirm = input(f"  Revoke token ID {token_id}? [y/N]: ").strip().lower()
    if confirm != "y":
        print_info("Cancelled")
        return
    try:
        client.revoke_api_token(token_id)
        print_success(f"Token {token_id} revoked")
    except SystemExit:
        print_error("Failed to revoke token")
        sys.exit(1)


def cmd_setup(client, args):
    """Save API key to config file."""
    key = args.api_key or input("  API Key: ").strip()
    if not key:
        print_error("API key is required")
        sys.exit(1)
    try:
        path = config.save_api_key(key)
        print_success(f"API key saved to {path}")
    except OSError as e:
        print_error(f"Failed to save API key: {e}")
        sys.exit(1)


def build_parser():
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="passwordmanager",
        description="Password Manager CLI - manage secrets from the command line.",
        epilog="Examples:\n"
               "  passwordmanager list secret\n"
               "  passwordmanager list group\n"
               "  passwordmanager create secret\n"
               "  passwordmanager retrieve secret my-password\n"
               "  passwordmanager delete secret 1\n"
               "  passwordmanager create group\n"
               "  passwordmanager token create my-token\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--api-key", help="API key for authentication")
    parser.add_argument("--base-url", help="Base URL of the Password Manager service")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # list
    list_parser = subparsers.add_parser("list", help="List secrets or groups")
    list_sub = list_parser.add_subparsers(dest="subcommand")
    list_secret = list_sub.add_parser("secret", help="List all secrets")
    list_secret.add_argument("--group", "-g", type=int, help="Filter by group ID")
    list_secret.set_defaults(func=cmd_list_secrets)
    list_group = list_sub.add_parser("group", help="List all secret groups")
    list_group.set_defaults(func=cmd_list_groups)

    # create
    create_parser = subparsers.add_parser("create", help="Create a new resource")
    create_sub = create_parser.add_subparsers(dest="subcommand")
    create_secret = create_sub.add_parser("secret", help="Create a new secret")
    create_secret.add_argument("title", nargs="?", help="Secret title")
    create_secret.add_argument("-t", "--type", choices=SECRET_TYPES, help="Secret type")
    create_secret.add_argument("-g", "--group-id", type=int, help="Target group ID")
    create_secret.add_argument("-d", "--description", help="Description")
    create_secret.add_argument("-u", "--username", help="Username")
    create_secret.add_argument("-U", "--url", help="URL")
    create_secret.add_argument("-D", "--data", help="Secret data (non-interactive)")
    create_secret.set_defaults(func=cmd_create_secret)
    create_ssh = create_sub.add_parser("secret-ssh", help="Generate and create a new SSH key")
    create_ssh.add_argument("-k", "--key-length", type=int, default=4096, help="Key length (default: 4096)")
    create_ssh.add_argument("-c", "--comment", default="", help="SSH key comment")
    create_ssh.set_defaults(func=cmd_create_secret_ssh)
    create_group = create_sub.add_parser("group", help="Create a new secret group")
    create_group.add_argument("name", nargs="?", help="Group name")
    create_group.add_argument("-d", "--description", help="Description")
    create_group.set_defaults(func=cmd_create_group)

    # retrieve
    retrieve_parser = subparsers.add_parser("retrieve", help="Retrieve a secret")
    retrieve_sub = retrieve_parser.add_subparsers(dest="subcommand")
    retrieve_secret = retrieve_sub.add_parser("secret", help="Retrieve a secret by ID or name")
    retrieve_secret.add_argument("query", help="Secret ID or name")
    retrieve_secret.set_defaults(func=cmd_retrieve_secret)
    retrieve_ssh = retrieve_sub.add_parser("secret-ssh", help="Retrieve an SSH key")
    retrieve_ssh.add_argument("query", help="SSH key secret ID")
    retrieve_ssh.set_defaults(func=cmd_retrieve_secret_ssh)

    # reveal
    reveal_parser = subparsers.add_parser("reveal", help="Reveal a secret with decrypted data")
    reveal_sub = reveal_parser.add_subparsers(dest="subcommand")
    reveal_secret = reveal_sub.add_parser("secret", help="Reveal a secret by ID or name")
    reveal_secret.add_argument("query", help="Secret ID or name")
    reveal_secret.set_defaults(func=cmd_reveal_secret)

    # delete
    delete_parser = subparsers.add_parser("delete", help="Delete a resource")
    delete_sub = delete_parser.add_subparsers(dest="subcommand")
    delete_secret = delete_sub.add_parser("secret", help="Delete a secret by ID or name")
    delete_secret.add_argument("query", help="Secret ID or name")
    delete_secret.set_defaults(func=cmd_delete_secret)
    delete_group = delete_sub.add_parser("group", help="Delete a secret group by ID or name")
    delete_group.add_argument("query", help="Group ID or name")
    delete_group.set_defaults(func=cmd_delete_group)

    # token
    token_parser = subparsers.add_parser("token", help="Manage API tokens")
    token_sub = token_parser.add_subparsers(dest="subcommand")
    token_list = token_sub.add_parser("list", help="List all API tokens")
    token_list.set_defaults(func=cmd_list_tokens)
    token_create = token_sub.add_parser("create", help="Create a new API token")
    token_create.add_argument("name", nargs="?", help="Token name")
    token_create.set_defaults(func=cmd_create_token)
    token_revoke = token_sub.add_parser("revoke", help="Revoke an API token")
    token_revoke.add_argument("token_id", help="Token ID to revoke")
    token_revoke.set_defaults(func=cmd_revoke_token)

    # setup
    setup_parser = subparsers.add_parser("setup", help="Save API key to config file")
    setup_parser.add_argument("--api-key", help="API key to save")
    setup_parser.set_defaults(func=cmd_setup)

    return parser


def main():
    """Main entry point for the CLI."""
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)
    base_url = config.load_base_url(getattr(args, "base_url", None))
    api_key = config.load_api_key(getattr(args, "api_key", None))
    client = PMClient(base_url=base_url, api_key=api_key)
    if hasattr(args, "func") and callable(args.func):
        try:
            args.func(client, args)
        except KeyboardInterrupt:
            print("\n  Cancelled")
            sys.exit(130)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
