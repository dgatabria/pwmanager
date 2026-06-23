"""Utility functions for the Password Manager CLI."""

import sys
from typing import Any

# Terminal colors (ANSI escape codes)
class Colors:
    """ANSI color codes for terminal output."""
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"


def color(text: str, color_code: str) -> str:
    """Wrap text in ANSI color codes."""
    return f"{color_code}{text}{Colors.RESET}"


def green(text: str) -> str:
    """Return green text."""
    return color(text, Colors.GREEN)


def red(text: str) -> str:
    """Return red text."""
    return color(text, Colors.RED)


def yellow(text: str) -> str:
    """Return yellow text."""
    return color(text, Colors.YELLOW)


def blue(text: str) -> str:
    """Return blue text."""
    return color(text, Colors.BLUE)


def bold(text: str) -> str:
    """Return bold text."""
    return color(text, Colors.BOLD)


def dim(text: str) -> str:
    """Return dim text."""
    return color(text, Colors.DIM)


def print_success(message: str) -> None:
    """Print a success message."""
    print(f"  {green('\u2713')} {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    print(f"  {red('\u2717')} {message}", file=sys.stderr)


def print_warning(message: str) -> None:
    """Print a warning message."""
    print(f"  {yellow('\u26a0')} {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    print(f"  {blue('\u25b6')} {message}")


def format_json(data: Any, indent: int = 2) -> str:
    """Format data as pretty JSON."""
    import json
    return json.dumps(data, indent=indent, default=str, ensure_ascii=False)


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    """Print data as a formatted table."""
    if not rows:
        print(dim("  No results"))
        return

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    # Print header
    header_line = "  " + " | ".join(
        h.ljust(col_widths[i]) for i, h in enumerate(headers)
    )
    print(bold(header_line))
    print(dim("  " + "-+-".join("-" * w for w in col_widths)))

    # Print rows
    for row in rows:
        line = "  " + " | ".join(
            str(row[i]).ljust(col_widths[i]) if i < len(row) else ""
            for i in range(len(headers))
        )
        print(line)


def mask_data(data: str, visible_chars: int = 4) -> str:
    """Mask sensitive data, showing only the first few characters."""
    if len(data) <= visible_chars:
        return "*" * len(data)
    return data[:visible_chars] + "*" * (len(data) - visible_chars)


def prompt_input(prompt: str, default: str = "") -> str:
    """Prompt the user for input with an optional default value."""
    if default:
        display_prompt = f"{prompt} [{default}]: "
    else:
        display_prompt = f"{prompt}: "

    result = input(display_prompt).strip()
    if result == "" and default:
        return default
    return result


def prompt_choice(prompt: str, choices: list[str], default: int = 0) -> str:
    """Prompt the user to choose from a list of options."""
    print(f"\n{bold(prompt)}")
    for i, choice in enumerate(choices):
        marker = f"[{i}]" if i == default else f" {i} "
        print(f"    {marker} {choice}")

    while True:
        try:
            idx = int(input(f"  Select [0-{len(choices)-1}] [{default}]: "))
            if 0 <= idx < len(choices):
                return choices[idx]
        except (ValueError, IndexError):
            pass
        print(f"  Invalid selection. Enter a number between 0 and {len(choices)-1}.")


def find_by_name(items: list[dict], name_field: str, query: str) -> dict | None:
    """Find an item in a list by name (case-insensitive partial match)."""
    query_lower = query.lower()
    for item in items:
        name = item.get(name_field, "").lower()
        if query_lower in name:
            return item
    return None


def find_by_id(items: list[dict], id_field: str, query: str) -> dict | None:
    """Find an item in a list by ID (partial match)."""
    query_lower = query.lower()
    for item in items:
        item_id = str(item.get(id_field, "")).lower()
        if query_lower in item_id:
            return item
    return None
