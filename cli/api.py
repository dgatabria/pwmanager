"""API client for the Password Manager CLI.

Provides functions to interact with the Password Manager API endpoints.
"""

import json
import sys
from typing import Any

import requests


class PMClient:
    """HTTP client for the Password Manager API."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "X-Api-Key": api_key,
        })

    def _request(
        self,
        method: str,
        endpoint: str,
        json_data: dict | None = None,
        params: dict | None = None,
    ) -> Any:
        """Make an HTTP request and return the parsed JSON response.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            json_data: JSON body for POST/PUT requests
            params: Query parameters

        Returns:
            Parsed JSON response, or None for 204 responses

        Raises:
            requests.exceptions.RequestException: On network errors
            SystemExit: On API errors (4xx/5xx)
        """
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(
                method, url, json=json_data, params=params
            )
        except requests.exceptions.ConnectionError:
            print(
                f"Error: Could not connect to {self.base_url}\n"
                "Is the Password Manager service running?",
                file=sys.stderr,
            )
            sys.exit(1)
        except requests.exceptions.Timeout:
            print("Error: Request timed out", file=sys.stderr)
            sys.exit(1)

        if response.status_code == 204:
            return None

        if response.status_code >= 400:
            try:
                error = response.json()
                detail = error.get("detail", "Unknown error")
            except (json.JSONDecodeError, KeyError):
                detail = response.text[:200] or f"HTTP {response.status_code}"
            print(f"Error: {detail}", file=sys.stderr)
            sys.exit(1)

        return response.json()

    def get(self, endpoint: str, params: dict | None = None) -> Any:
        """GET request."""
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, json_data: dict | None = None) -> Any:
        """POST request."""
        return self._request("POST", endpoint, json_data=json_data)

    def put(self, endpoint: str, json_data: dict | None = None) -> Any:
        """PUT request."""
        return self._request("PUT", endpoint, json_data=json_data)

    def delete(self, endpoint: str) -> None:
        """DELETE request."""
        self._request("DELETE", endpoint)

    # ─── Secrets ─────────────────────────────────────────────────────

    def list_secrets(self, group_id: int | None = None) -> list[dict]:
        """List all secrets, optionally filtered by group_id."""
        params = {}
        if group_id is not None:
            params["group_id"] = group_id
        return self.get("/api/secrets", params=params or None) or []

    def get_secret(self, secret_id: int) -> dict:
        """Get a single secret by ID."""
        return self.get(f"/api/secrets/{secret_id}")

    def get_secret_masked(self, secret_id: int) -> dict:
        """Get a secret with masked data (audit-logged)."""
        return self.get(f"/api/secrets/{secret_id}/masked")

    def reveal_secret(self, secret_id: int) -> dict:
        """Get a secret with decrypted data (audit-logged)."""
        return self.get(f"/api/secrets/{secret_id}/reveal")

    def create_secret(
        self,
        title: str,
        secret_type: str,
        plaintext_data: str,
        group_id: int,
        description: str | None = None,
        username: str | None = None,
        url: str | None = None,
        key_length: int | None = None,
    ) -> dict:
        """Create a new secret."""
        data = {
            "title": title,
            "secret_type": secret_type,
            "plaintext_data": plaintext_data,
            "group_id": group_id,
        }
        if description:
            data["description"] = description
        if username:
            data["username"] = username
        if url:
            data["url"] = url
        if key_length:
            data["key_length"] = key_length
        return self.post("/api/secrets", json_data=data)

    def delete_secret(self, secret_id: int) -> None:
        """Delete a secret."""
        self.delete(f"/api/secrets/{secret_id}")

    def generate_ssh_key(
        self, key_length: int = 4096, comment: str = ""
    ) -> dict:
        """Generate a new SSH key pair."""
        data: dict[str, Any] = {"key_length": key_length}
        if comment:
            data["comment"] = comment
        return self.post("/api/secrets/ssh-key/generate", json_data=data)

    # ─── Secret Groups ───────────────────────────────────────────────

    def list_secret_groups(self, group_id: int | None = None) -> list[dict]:
        """List all secret groups, optionally filtered by group_id."""
        params = {}
        if group_id is not None:
            params["group_id"] = group_id
        return self.get("/api/secret-groups", params=params or None) or []

    def get_secret_group(self, group_id: int) -> dict:
        """Get a single secret group by ID."""
        return self.get(f"/api/secret-groups/{group_id}")

    def create_secret_group(
        self,
        name: str,
        group_id: int,
        description: str | None = None,
        member_group_ids: list[int] | None = None,
    ) -> dict:
        """Create a new secret group."""
        data = {
            "name": name,
            "group_id": group_id,
            "member_group_ids": member_group_ids or [],
        }
        if description:
            data["description"] = description
        return self.post("/api/secret-groups", json_data=data)

    def delete_secret_group(self, group_id: int) -> None:
        """Delete a secret group."""
        self.delete(f"/api/secret-groups/{group_id}")

    def update_secret_group_access(
        self, group_id: int, member_group_ids: list[int]
    ) -> None:
        """Update which user groups can access a secret group."""
        self.post(
            f"/api/secret-groups/{group_id}/access",
            json_data={"member_group_ids": member_group_ids},
        )

    # ─── User Groups ─────────────────────────────────────────────────

    def list_user_groups(self) -> list[dict]:
        """List all user groups."""
        return self.get("/api/groups") or []

    # ─── API Tokens ──────────────────────────────────────────────────

    def list_api_tokens(self) -> list[dict]:
        """List all API tokens for the current user."""
        return self.get("/api/api-tokens") or []

    def create_api_token(
        self, name: str, description: str | None = None
    ) -> dict:
        """Create a new API token."""
        data = {"name": name}
        if description:
            data["description"] = description
        return self.post("/api/api-tokens", json_data=data)

    def revoke_api_token(self, token_id: int) -> None:
        """Revoke an API token."""
        self.delete(f"/api/api-tokens/{token_id}")
