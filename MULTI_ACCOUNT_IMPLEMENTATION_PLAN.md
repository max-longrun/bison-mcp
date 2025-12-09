# Multi-Account API Key Implementation Plan for EmailBison MCP

## Overview

This document outlines the implementation plan to add multi-account API key functionality to the EmailBison MCP server, following the pattern described in `MULTI_ACCOUNT_API_KEY_LOGIC.md`.

## Current Architecture

### Current State
- **Single API Key**: Server uses one API key from `EMAILBISON_API_KEY` environment variable
- **Single Client**: One `EmailBisonClient` instance created during server lifespan
- **Client Access**: All tools use `_client()` function to retrieve the singleton client
- **Initialization**: Client is created in `lifespan()` context manager with API key from environment

### Key Files
- `emailbison_mcp/server.py` (4498 lines) - MCP server with tool handlers
- `emailbison_mcp/client.py` (1095 lines) - EmailBison API client
- Current configuration: Environment variables (`.env` file)

## Target Architecture

### Target State
- **Multiple API Keys**: Support multiple accounts via `config.json` file
- **Client Manager**: New `ClientManager` class to handle multi-account logic
- **Per-Request Client Selection**: Tools receive `client_name` parameter to select account
- **Backward Compatibility**: Support fallback to environment variable for single-account setups
- **Config Structure**: JSON file with `clients` object and `default_client` field

### Configuration File Structure
```json
{
  "clients": {
    "Account1": {
      "mcp_key": "api-key-for-account-1",
      "mcp_url": "https://send.longrun.agency/api"
    },
    "Account2": {
      "mcp_key": "api-key-for-account-2",
      "mcp_url": ""
    }
  },
  "default_client": "Account1"
}
```

## Implementation Steps

### Phase 1: Create ClientManager Class

**File**: `emailbison_mcp/client_manager.py` (new file)

**Responsibilities**:
1. Load and parse `config.json` from server directory
2. Validate configuration structure
3. Provide methods to retrieve client configurations
4. Manage default client selection
5. Handle error cases (missing config, invalid JSON, missing clients)

**Key Methods**:
- `__init__(config_path: str)` - Load configuration from file
- `get_client_config(client_name: str | None) -> dict[str, str]` - Get full config for a client
- `get_mcp_key(client_name: str | None) -> str` - Extract API key for a client
- `get_mcp_url(client_name: str | None) -> str` - Get base URL (with fallback to default)
- `list_clients() -> list[str]` - Return all configured client names
- `get_default_client() -> str | None` - Get default client name
- `validate_config() -> None` - Validate config structure on load

**Error Handling**:
- Missing `config.json` file
- Invalid JSON syntax
- Missing required fields (`mcp_key`)
- Client not found
- No default client when client_name not provided

### Phase 2: Modify Server Lifespan

**File**: `emailbison_mcp/server.py`

**Changes to `lifespan()` function**:
1. Check for `config.json` first (multi-account mode)
2. Fallback to `EMAILBISON_API_KEY` env var if config.json doesn't exist (backward compatibility)
3. Initialize `ClientManager` instead of single client
4. Store `ClientManager` on server instance: `app.client_manager`
5. Keep timeout from environment variable or config

**Logic Flow**:
```
1. Check if config.json exists in server directory
2. If exists:
   - Load ClientManager with config.json
   - Store on app.client_manager
3. Else:
   - Check EMAILBISON_API_KEY env var
   - If present, create "default" client config dynamically
   - Wrap in ClientManager for consistent interface
4. Store ClientManager on server
```

### Phase 3: Create Client Factory/Cache

**File**: `emailbison_mcp/server.py` or `emailbison_mcp/client_manager.py`

**Purpose**: 
- Cache `EmailBisonClient` instances per account
- Avoid recreating clients on every request
- Handle client lifecycle (close on server shutdown)

**Implementation Options**:
- **Option A**: Client cache in `ClientManager` - Store clients as instance variables
- **Option B**: Client cache in server - Store dict of clients on server instance
- **Option C**: Lazy creation - Create clients on-demand in `_client()` function

**Recommended**: Option A with caching in ClientManager

**Methods**:
- `get_or_create_client(client_name: str | None) -> EmailBisonClient` - Get cached client or create new
- `close_all_clients() -> None` - Close all cached clients (called in lifespan cleanup)

### Phase 4: Update Tool Definitions

**File**: `emailbison_mcp/server.py`

**Changes to TOOL_DEFINITIONS**:
- Add optional `client_name` parameter to ALL tool input schemas
- Make it optional with no default (user must specify or rely on default_client)
- Add description: "Name of the client/account to use. If not provided, uses the default client from config."

**Example**:
```python
"client_name": {
    "type": "string",
    "description": "Name of the client/account to use. If not provided, uses the default client from config.",
}
```

**Note**: This needs to be added to ~70+ tool definitions. Consider helper function to avoid repetition.

### Phase 5: Update Tool Handlers

**File**: `emailbison_mcp/server.py`

**Changes to `call_tool()` function**:
1. Extract `client_name` from arguments (if present)
2. Remove `client_name` from arguments before passing to client methods
3. Replace `client = _client()` with `client = _get_client_for_account(client_name)`
4. Create new helper: `_get_client_for_account(client_name: str | None) -> EmailBisonClient`

**Helper Function**:
```python
def _get_client_for_account(client_name: str | None) -> EmailBisonClient:
    client_manager = getattr(server, "client_manager", None)
    if client_manager is None:
        raise RuntimeError("ClientManager not initialized.")
    return client_manager.get_or_create_client(client_name)
```

**Important**: 
- Extract `client_name` early in `call_tool()` 
- Remove it from arguments dict before passing to client methods
- Handle in all ~70+ tool handler branches

### Phase 6: Update Resource Documentation

**File**: `emailbison_mcp/server.py`

**Changes to RESOURCE_DEFINITIONS**:
1. Update `emailbison-mcp-variables` resource to document multi-account support
2. Add new resource: `emailbison-multi-account-config` explaining config.json structure
3. Update instructions in server initialization to mention multi-account capability

### Phase 7: Create Configuration Template

**File**: `config.json.example` (new file)

**Purpose**: 
- Provide template for users
- Include example structure
- Document fields

**Content**:
```json
{
  "clients": {
    "Production": {
      "mcp_key": "your-api-key-here",
      "mcp_url": "https://send.longrun.agency/api"
    },
    "Staging": {
      "mcp_key": "your-staging-api-key-here",
      "mcp_url": ""
    }
  },
  "default_client": "Production"
}
```

### Phase 8: Update Documentation

**Files**: `README.md`, potentially create `MULTI_ACCOUNT_SETUP.md`

**Changes**:
1. Document multi-account setup in README
2. Explain config.json structure
3. Show backward compatibility with environment variables
4. Provide migration guide for existing users

### Phase 9: Error Handling & Validation

**Files**: `emailbison_mcp/client_manager.py`, `emailbison_mcp/server.py`

**Validation Points**:
1. Config file validation on load
2. Client name validation when requested
3. Clear error messages for common issues:
   - "Config file not found"
   - "Client 'X' not found in config"
   - "No default client specified and no client_name provided"
   - "Missing mcp_key for client 'X'"

**Error Messages**:
- Use descriptive, actionable error messages
- Include suggestions (e.g., "Available clients: Account1, Account2")
- Reference documentation when appropriate

### Phase 10: Testing Considerations

**Test Scenarios**:
1. Multi-account mode with config.json
2. Single-account fallback with environment variable
3. Missing config.json (should fallback gracefully)
4. Invalid config.json (should raise clear error)
5. Client not found (should list available clients)
6. Default client behavior
7. Per-tool client selection
8. Client caching and reuse
9. Server shutdown cleanup (all clients closed)

## Implementation Details

### ClientManager Implementation

```python
class ClientManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config()
        self._client_cache: dict[str, EmailBisonClient] = {}
        self.validate_config()
    
    def _load_config(self) -> dict[str, Any]:
        # Load and parse JSON
    
    def validate_config(self) -> None:
        # Validate structure, required fields
    
    def get_client_config(self, client_name: str | None) -> dict[str, str]:
        # Resolve client name (use default if None)
        # Return config dict
    
    def get_mcp_key(self, client_name: str | None) -> str:
        # Extract mcp_key from config
    
    def get_mcp_url(self, client_name: str | None) -> str:
        # Extract mcp_url with fallback to default
    
    def get_or_create_client(self, client_name: str | None) -> EmailBisonClient:
        # Get from cache or create new
        # Cache by resolved client name
    
    async def close_all_clients(self) -> None:
        # Close all cached clients
```

### Backward Compatibility Strategy

**Priority**: Maintain backward compatibility with existing single-account setups

**Approach**:
1. Check for `config.json` first
2. If not found, check `EMAILBISON_API_KEY` environment variable
3. If env var found, create virtual "default" client config
4. Wrap in ClientManager for consistent interface
5. All code paths use ClientManager, so no conditional logic in tools

### Configuration File Location

**Options**:
1. Same directory as `server.py` (recommended)
2. User's home directory
3. Configurable via environment variable

**Recommended**: Same directory as server.py
- Easy to locate
- Standard practice for MCP servers
- Can be overridden with env var: `EMAILBISON_CONFIG_PATH`

### Timeout Configuration

**Current**: From `EMAILBISON_TIMEOUT_SECONDS` env var (default 30)

**Options**:
1. Global timeout (current approach)
2. Per-client timeout in config.json

**Recommended**: Keep global timeout for simplicity, allow override in config.json if needed

## Migration Path for Existing Users

1. **No Action Required**: Existing users with `EMAILBISON_API_KEY` env var continue working
2. **Optional Migration**: Users can create `config.json` to enable multi-account
3. **Gradual Adoption**: Can start with single account in config.json, add more later

## Security Considerations

1. **Config File Security**: 
   - Document that config.json should not be committed to version control
   - Add to `.gitignore` if not already present
   - Recommend file permissions (600 on Unix)

2. **API Key Storage**:
   - Keys stored in plain text in config.json (same as .env currently)
   - Consider future enhancement: support environment variable references in config.json

3. **Validation**:
   - Validate API keys format if possible
   - Don't log or expose keys in error messages

## Files to Create/Modify

### New Files
1. `emailbison_mcp/client_manager.py` - ClientManager class
2. `config.json.example` - Configuration template

### Modified Files
1. `emailbison_mcp/server.py` - Update lifespan, tool definitions, tool handlers
2. `README.md` - Documentation updates
3. `.gitignore` - Ensure config.json is ignored

### Optional Files
1. `MULTI_ACCOUNT_SETUP.md` - Detailed setup guide
2. Migration script to convert .env to config.json

## Implementation Order

1. **Phase 1**: Create ClientManager class (can be tested independently)
2. **Phase 2**: Modify lifespan to use ClientManager
3. **Phase 3**: Implement client caching
4. **Phase 4**: Update tool definitions (add client_name parameter)
5. **Phase 5**: Update tool handlers (extract and use client_name)
6. **Phase 6**: Update documentation resources
7. **Phase 7**: Create config.json.example
8. **Phase 8**: Update README and other docs
9. **Phase 9**: Add comprehensive error handling
10. **Phase 10**: Testing (throughout implementation)

## Key Design Decisions

1. **Client Caching**: Cache clients per account to avoid recreation overhead
2. **Backward Compatibility**: Support env var fallback for existing users
3. **Default Client**: Require default_client in config or explicit client_name in tools
4. **Tool Parameter**: Optional client_name in all tools (not just some)
5. **Config Location**: Same directory as server.py (standard practice)
6. **Error Messages**: Clear, actionable error messages with suggestions

## Potential Challenges

1. **Tool Definition Updates**: ~70+ tools need client_name parameter added
   - **Solution**: Create helper function to inject parameter consistently

2. **Tool Handler Updates**: All tool handlers need client_name extraction
   - **Solution**: Extract early in call_tool(), pass to helper function

3. **Testing Complexity**: Need to test both config.json and env var paths
   - **Solution**: Comprehensive test coverage for both modes

4. **Client Lifecycle**: Ensuring all clients are properly closed
   - **Solution**: Track clients in cache, close all in lifespan cleanup

5. **Configuration Validation**: Complex validation logic
   - **Solution**: Comprehensive validation with clear error messages

## Success Criteria

- ✅ Multiple accounts can be configured via config.json
- ✅ Tools can specify which account to use via client_name parameter
- ✅ Default client works when client_name not specified
- ✅ Backward compatibility maintained (env var still works)
- ✅ All clients properly cleaned up on server shutdown
- ✅ Clear error messages for common configuration issues
- ✅ Documentation updated with multi-account setup instructions
- ✅ All existing functionality continues to work

## Next Steps

1. **Wait for credentials information** from user
2. **Review and refine plan** based on user feedback
3. **Begin implementation** starting with Phase 1
4. **Iterative development** with testing at each phase


