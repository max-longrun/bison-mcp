# Multi-Account API Key Management in MCP Servers

This document explains how MCP (Model Context Protocol) servers handle multiple API keys for different accounts, how they interact with API endpoints, and how configuration data is structured and used.

## Overview

MCP servers act as intermediaries between MCP clients (like Claude Desktop) and external API services. When managing multiple accounts for the same service, the server needs to:

1. Store multiple API keys securely
2. Route requests to the correct API key based on account/client selection
3. Maintain configuration data in a structured format
4. Provide a way to specify which account to use for each request

## How MCP Servers Work with API Endpoints

### Request Flow

The typical flow when an MCP server makes an API request is:

```
MCP Client → MCP Server → API Endpoint
              ↓
         (Selects API Key)
              ↓
         (Makes HTTP Request)
```

1. **MCP Client Request**: The MCP client (e.g., Claude Desktop) calls a tool provided by the MCP server
2. **Client Selection**: The tool receives a `client_name` parameter identifying which account to use
3. **Configuration Lookup**: The server looks up the configuration for that client
4. **API Key Retrieval**: The server extracts the API key from the client's configuration
5. **HTTP Request**: The server makes an HTTP request to the API endpoint with the appropriate API key in the headers
6. **Response Handling**: The server processes the API response and returns it to the MCP client

### API Request Implementation

When making API requests, the server:

1. **Identifies the Client**: Receives a `client_name` parameter (or uses a default if not specified)
2. **Retrieves Configuration**: Looks up the client's configuration from the loaded config data
3. **Extracts Credentials**: Gets the API key associated with that client
4. **Constructs Request**: Builds the HTTP request with:
   - The API key in the appropriate header (e.g., `X-API-KEY`, `Authorization`)
   - The correct base URL (which may be client-specific or shared)
   - Any required headers (Content-Type, Accept, etc.)
5. **Executes Request**: Makes the HTTP request to the API endpoint
6. **Returns Response**: Processes and returns the API response to the MCP client

### Example Request Flow

```python
# 1. MCP tool receives request with client_name
client_name = "Account1"

# 2. Server retrieves client configuration
config = client_manager.get_client_config(client_name)
api_key = config.get("mcp_key")

# 3. Server constructs HTTP request
headers = {
    "X-API-KEY": api_key,
    "Content-Type": "application/json"
}
url = f"{base_url}/{endpoint}"

# 4. Server makes request
response = await http_client.get(url, headers=headers)

# 5. Server returns response to MCP client
return response.json()
```

## Configuration File Structure (config.json)

The `config.json` file serves as the central repository for all account configurations. It uses a simple JSON structure that is easy to read, write, and maintain.

### Data Structure

```json
{
  "clients": {
    "ClientName1": {
      "mcp_key": "api-key-for-client-1",
      "mcp_url": "https://api.example.com/client-1"
    },
    "ClientName2": {
      "mcp_key": "api-key-for-client-2",
      "mcp_url": "https://api.example.com/client-2"
    },
    "ClientName3": {
      "mcp_key": "api-key-for-client-3",
      "mcp_url": "https://api.example.com/client-3"
    }
  },
  "default_client": "ClientName1"
}
```

### Structure Breakdown

#### Root Level

- **`clients`** (object, required): A dictionary/object where each key is a unique client/account name, and each value is a configuration object for that client
- **`default_client`** (string, optional): The name of the client to use when no client is explicitly specified in a request

#### Client Configuration Object

Each client entry in the `clients` object contains:

- **`mcp_key`** (string, required): The API key/authentication token for this specific client account
- **`mcp_url`** (string, optional): A client-specific base URL or endpoint identifier. This can be:
  - A full base URL for the API
  - An endpoint path segment
  - A workspace/account identifier
  - Empty string if all clients use the same base URL

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `clients` | object | Yes | Container for all client configurations |
| `clients[ClientName]` | object | Yes | Individual client configuration |
| `clients[ClientName].mcp_key` | string | Yes | API key/authentication token for this client |
| `clients[ClientName].mcp_url` | string | No | Client-specific URL or identifier |
| `default_client` | string | No | Default client name to use when not specified |

### Example Configurations

#### Simple Multi-Account Setup

```json
{
  "clients": {
    "Production": {
      "mcp_key": "prod-api-key-12345",
      "mcp_url": "https://api.service.com/prod"
    },
    "Staging": {
      "mcp_key": "staging-api-key-67890",
      "mcp_url": "https://api.service.com/staging"
    }
  },
  "default_client": "Production"
}
```

#### Shared Base URL with Different Keys

```json
{
  "clients": {
    "AccountA": {
      "mcp_key": "key-account-a",
      "mcp_url": ""
    },
    "AccountB": {
      "mcp_key": "key-account-b",
      "mcp_url": ""
    }
  },
  "default_client": "AccountA"
}
```

## How the Server Uses config.json

### Configuration Loading

When the MCP server starts:

1. **File Location**: The server locates `config.json` (typically in the same directory as the server script)
2. **File Reading**: Reads and parses the JSON file
3. **Validation**: Validates that:
   - The file contains valid JSON
   - At least one client is configured
   - Required fields are present
4. **In-Memory Storage**: Loads the configuration into memory for fast access during runtime

### Client Manager Pattern

The server uses a `ClientManager` class to handle configuration operations:

#### Key Responsibilities

1. **Configuration Loading**: Loads and parses `config.json` on initialization
2. **Client Lookup**: Provides methods to retrieve client configurations by name
3. **Default Handling**: Manages default client selection when no client is specified
4. **Validation**: Ensures requested clients exist and have required configuration

#### Common Operations

- **`get_client_config(client_name)`**: Retrieves the full configuration object for a specific client
- **`get_mcp_key(client_name)`**: Extracts just the API key for a client
- **`get_mcp_url(client_name)`**: Retrieves the URL/endpoint for a client
- **`list_clients()`**: Returns a list of all configured client names

### Runtime Usage

During operation, when a tool is called:

1. **Client Identification**: The tool receives a `client_name` parameter (or uses default)
2. **Config Retrieval**: Calls `client_manager.get_client_config(client_name)`
3. **Key Extraction**: Gets the `mcp_key` from the returned configuration
4. **Request Construction**: Uses the key to authenticate the API request

### Error Handling

The server handles various error scenarios:

- **Missing Config File**: Raises an error if `config.json` doesn't exist
- **Invalid JSON**: Validates JSON syntax and reports parsing errors
- **Missing Client**: Returns an error if a requested client doesn't exist
- **Missing API Key**: Validates that each client has an API key configured
- **No Default Client**: Provides clear error when no client is specified and no default is set

## Multi-Account API Key Routing Logic

### The Problem

When managing multiple accounts, each account has its own API key. The server needs to:

- Store multiple API keys securely
- Know which key to use for each request
- Provide a simple way to switch between accounts
- Handle cases where no account is specified

### The Solution

The routing logic follows these principles:

1. **Client Name as Identifier**: Each account is identified by a unique name (the key in the `clients` object)
2. **Configuration Lookup**: When a request comes in, the server looks up the client by name
3. **Key Selection**: The API key is extracted from that client's configuration
4. **Request Routing**: The request is made with the selected API key

### Routing Flow Diagram

```
┌─────────────────┐
│  MCP Tool Call  │
│  (with client)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Client Manager │
│  Lookup Client  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Get API Key    │
│  from Config    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Make API       │
│  Request with   │
│  Selected Key   │
└─────────────────┘
```

### Default Client Behavior

When no client is specified:

1. **Check for Default**: Server checks if a `default_client` is set in config
2. **Use Default**: If available, uses the default client's API key
3. **Error if None**: If no default is set, returns an error asking for explicit client specification

### Benefits of This Approach

1. **Scalability**: Easy to add new accounts by simply adding entries to `config.json`
2. **Separation**: Each account's credentials are isolated
3. **Flexibility**: Can specify different base URLs per account if needed
4. **Simplicity**: No code changes required to add new accounts
5. **Security**: API keys are stored in a single, manageable file (that should be kept secure)

## Best Practices

### Configuration Management

1. **Secure Storage**: Keep `config.json` secure and never commit it to version control
2. **Backup**: Maintain backups of your configuration
3. **Validation**: Validate configuration structure before deployment
4. **Documentation**: Document what each client/account is used for

### API Key Security

1. **Environment Variables**: Consider using environment variables for sensitive keys (with fallback to config.json)
2. **Access Control**: Restrict file system access to `config.json`
3. **Key Rotation**: Have a process for rotating API keys when needed
4. **Audit**: Log which client is used for each request (without logging the actual keys)

### Server Design

1. **Error Messages**: Provide clear error messages when clients are missing or misconfigured
2. **Validation**: Validate client names and configuration at startup
3. **Default Handling**: Always have a sensible default or require explicit client specification
4. **Tool Design**: Design MCP tools to accept optional `client_name` parameters with sensible defaults

## Summary

MCP servers handle multiple API keys by:

1. **Storing configurations** in a structured `config.json` file with a `clients` object containing account-specific data
2. **Using a ClientManager** to load, validate, and retrieve client configurations
3. **Routing requests** by looking up the client name, extracting its API key, and using it in API requests
4. **Supporting defaults** through a `default_client` field for convenience
5. **Providing flexibility** through a simple JSON structure that's easy to modify without code changes

This approach allows a single MCP server to manage dozens or hundreds of accounts, with each account maintaining its own API key and configuration, while keeping the implementation simple and maintainable.

