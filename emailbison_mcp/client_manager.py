"""Client manager for handling multiple EmailBison API accounts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from emailbison_mcp.client import EmailBisonClient


class ClientManagerError(RuntimeError):
    """Raised when there's an error with client management."""


class ClientManager:
    """Manages multiple EmailBison API clients based on configuration."""

    def __init__(
        self,
        config_path: str | None = None,
        *,
        config_dict: dict[str, Any] | None = None,
        default_base_url: str = "https://send.longrun.agency/api",
        default_timeout: float = 30.0,
    ) -> None:
        """
        Initialize the ClientManager.

        Args:
            config_path: Path to config.json file. If None, looks for config.json
                in the same directory as this module. Ignored if config_dict is provided.
            config_dict: Optional in-memory configuration dictionary. If provided,
                config_path is ignored.
            default_base_url: Default base URL for API requests.
            default_timeout: Default timeout for API requests in seconds.
        """
        self.default_base_url = default_base_url
        self.default_timeout = default_timeout
        self._client_cache: dict[str, EmailBisonClient] = {}
        
        if config_dict is not None:
            self.config_path = None
            self.config = config_dict
        else:
            if config_path is None:
                # Look for config.json in the same directory as this module
                module_dir = Path(__file__).parent
                config_path = str(module_dir / "config.json")
            self.config_path = config_path
            self.config = self._load_config()
        
        self.validate_config()

    def _load_config(self) -> dict[str, Any]:
        """Load configuration from JSON file."""
        if self.config_path is None:
            raise ClientManagerError("No config_path provided and no config_dict provided.")
            
        config_file = Path(self.config_path)
        if not config_file.exists():
            raise ClientManagerError(
                f"Configuration file not found: {self.config_path}\n"
                f"Please create a config.json file or set EMAILBISON_API_KEY environment variable."
            )

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            raise ClientManagerError(
                f"Invalid JSON in configuration file {self.config_path}: {e}"
            ) from e
        except Exception as e:
            raise ClientManagerError(
                f"Error reading configuration file {self.config_path}: {e}"
            ) from e

        return config

    def validate_config(self) -> None:
        """Validate the configuration structure."""
        if not isinstance(self.config, dict):
            raise ClientManagerError("Configuration must be a JSON object.")

        if "clients" not in self.config:
            raise ClientManagerError(
                'Configuration must contain a "clients" object.'
            )

        clients = self.config.get("clients", {})
        if not isinstance(clients, dict):
            raise ClientManagerError('"clients" must be a JSON object.')

        if not clients:
            raise ClientManagerError(
                'Configuration must contain at least one client in "clients".'
            )

        # Validate each client configuration
        for client_name, client_config in clients.items():
            if not isinstance(client_config, dict):
                raise ClientManagerError(
                    f'Client "{client_name}" configuration must be an object.'
                )

            if "mcp_key" not in client_config:
                raise ClientManagerError(
                    f'Client "{client_name}" is missing required field "mcp_key".'
                )

            if not isinstance(client_config["mcp_key"], str):
                raise ClientManagerError(
                    f'Client "{client_name}" field "mcp_key" must be a string.'
                )

            if not client_config["mcp_key"].strip():
                raise ClientManagerError(
                    f'Client "{client_name}" field "mcp_key" cannot be empty.'
                )

        # Validate default_client if present
        if "default_client" in self.config:
            default = self.config["default_client"]
            if not isinstance(default, str):
                raise ClientManagerError(
                    '"default_client" must be a string.'
                )
            if default not in clients:
                available = ", ".join(sorted(clients.keys()))
                raise ClientManagerError(
                    f'Default client "{default}" not found in clients. '
                    f"Available clients: {available}"
                )

    def get_default_client_name(self) -> str | None:
        """Get the default client name from configuration."""
        return self.config.get("default_client")

    def list_clients(self) -> list[str]:
        """Return a list of all configured client names."""
        return sorted(self.config.get("clients", {}).keys())

    def get_client_config(self, client_name: str | None = None) -> dict[str, str]:
        """
        Get the full configuration for a client.

        Args:
            client_name: Name of the client. If None, uses the default client.

        Returns:
            Dictionary with client configuration (mcp_key, mcp_url).

        Raises:
            ClientManagerError: If client is not found or no default is set.
        """
        # Resolve client name
        if client_name is None:
            client_name = self.get_default_client_name()
            if client_name is None:
                available = ", ".join(self.list_clients())
                raise ClientManagerError(
                    f"No client_name provided and no default_client specified in config. "
                    f"Please specify a client_name. Available clients: {available}"
                )

        # Get client configuration
        clients = self.config.get("clients", {})
        if client_name not in clients:
            available = ", ".join(self.list_clients())
            raise ClientManagerError(
                f'Client "{client_name}" not found in configuration. '
                f"Available clients: {available}"
            )

        return dict(clients[client_name])

    def get_mcp_key(self, client_name: str | None = None) -> str:
        """
        Get the API key for a client.

        Args:
            client_name: Name of the client. If None, uses the default client.

        Returns:
            API key string.

        Raises:
            ClientManagerError: If client is not found or no default is set.
        """
        config = self.get_client_config(client_name)
        return config["mcp_key"]

    def get_mcp_url(self, client_name: str | None = None) -> str:
        """
        Get the base URL for a client.

        Args:
            client_name: Name of the client. If None, uses the default client.

        Returns:
            Base URL string, or default_base_url if not specified.

        Raises:
            ClientManagerError: If client is not found or no default is set.
        """
        config = self.get_client_config(client_name)
        mcp_url = config.get("mcp_url", "")
        return mcp_url.strip() if mcp_url else self.default_base_url

    def get_or_create_client(
        self, client_name: str | None = None, timeout: float | None = None
    ) -> EmailBisonClient:
        """
        Get or create a cached EmailBisonClient for a client.

        Args:
            client_name: Name of the client. If None, uses the default client.
            timeout: Request timeout in seconds. If None, uses default_timeout.

        Returns:
            EmailBisonClient instance.

        Raises:
            ClientManagerError: If client is not found or no default is set.
        """
        # Resolve client name
        if client_name is None:
            client_name = self.get_default_client_name()
            if client_name is None:
                available = ", ".join(self.list_clients())
                raise ClientManagerError(
                    f"No client_name provided and no default_client specified in config. "
                    f"Please specify a client_name. Available clients: {available}"
                )

        # Check cache
        if client_name in self._client_cache:
            return self._client_cache[client_name]

        # Create new client
        api_key = self.get_mcp_key(client_name)
        base_url = self.get_mcp_url(client_name)
        timeout = timeout if timeout is not None else self.default_timeout

        client = EmailBisonClient(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )

        # Cache it
        self._client_cache[client_name] = client
        return client

    async def close_all_clients(self) -> None:
        """Close all cached clients."""
        for client in self._client_cache.values():
            await client.close()
        self._client_cache.clear()

