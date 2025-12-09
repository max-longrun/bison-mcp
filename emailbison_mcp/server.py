"""Model Context Protocol server exposing EmailBison tools."""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from typing import Any, Iterable, Mapping

import anyio
from dotenv import load_dotenv
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from emailbison_mcp.client import EmailBisonClient, EmailBisonError
from emailbison_mcp.client_manager import ClientManager, ClientManagerError


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True)


@asynccontextmanager
async def lifespan(app: Server):
    """Configure the EmailBison client for the server lifecycle."""
    load_dotenv(override=True)  # Override any existing environment variables
    
    base_url = os.getenv("EMAILBISON_BASE_URL", "https://send.longrun.agency/api")
    timeout = float(os.getenv("EMAILBISON_TIMEOUT_SECONDS", "30"))
    
    # Try to load config.json first (multi-account mode)
    from pathlib import Path
    module_dir = Path(__file__).parent
    config_path = str(module_dir / "config.json")
    
    client_manager: ClientManager | None = None
    
    if Path(config_path).exists():
        # Multi-account mode: use config.json
        try:
            client_manager = ClientManager(
                config_path=config_path,
                default_base_url=base_url,
                default_timeout=timeout,
            )
        except ClientManagerError as e:
            raise RuntimeError(f"Failed to load configuration: {e}") from e
    else:
        # Backward compatibility: use environment variable
        api_key = os.getenv("EMAILBISON_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Neither config.json nor EMAILBISON_API_KEY environment variable found. "
                "Please create a config.json file or set EMAILBISON_API_KEY."
            )
        
        # Create in-memory config for backward compatibility
        temp_config = {
            "clients": {
                "default": {
                    "mcp_key": api_key,
                    "mcp_url": base_url,
                }
            },
            "default_client": "default",
        }
        
        try:
            client_manager = ClientManager(
                config_dict=temp_config,
                default_base_url=base_url,
                default_timeout=timeout,
            )
        except ClientManagerError as e:
            raise RuntimeError(f"Failed to initialize client manager: {e}") from e
    
    app.client_manager = client_manager  # type: ignore[attr-defined]
    
    try:
        yield
    finally:
        await client_manager.close_all_clients()


server = Server(
    name="emailbison-mcp",
    version="0.1.0",
    instructions=(
        "🚨 CRITICAL: Before using ANY tools, you MUST first read the following resources by calling read_resource():\n"
        "1. document:emailbison/api-reference - API endpoint details and filter parameter formats\n"
        "2. document:emailbison/pagination - CRITICAL pagination requirements (MUST read before fetching data)\n"
        "3. document:emailbison/entity-ids - CRITICAL entity ID requirements (MUST read before filtering/searching)\n"
        "4. document:emailbison/filters - CRITICAL filtering guide (MUST read before using filters)\n"
        "5. document:emailbison/tags - How to use tags for filtering\n"
        "6. document:emailbison/mcp-variables - Configuration details\n"
        "7. document:emailbison/account-details - Account information endpoint\n"
        "\n"
        "These resources contain essential information about API behavior, pagination requirements, and parameter formats. "
        "DO NOT use any tools until you have read at minimum the api-reference, pagination, and entity-ids resources.\n"
        "\n"
        "🚨 MULTI-ACCOUNT MODE - CRITICAL: This server supports multiple workspaces via the `client_name` parameter. "
        "Each API key is automatically associated with its workspace. "
        "To access different workspaces, simply use the `client_name` parameter in tool calls (e.g., `client_name=\"ATI\"` or `client_name=\"LongRun\"`). "
        "DO NOT use W_List_Workspaces or W_Switch_Workspace when accessing different workspaces - just specify the correct `client_name`. "
        "Workspace switching tools are only needed for advanced workspace management within a single account, not for accessing different accounts/workspaces.\n"
        "\n"
        "🚨 ENTITY ID REQUIREMENT: Before filtering, searching, or referencing ANY entity (tags, timezones, campaigns, leads, sender emails, workspaces), "
        "you MUST first call the appropriate list tool to get all available entities and their IDs. "
        "The API requires IDs (not names) for all entity references. See document:emailbison/entity-ids for details.\n"
        "\n"
        "After reading resources, use these tools to query and manage leads, campaigns, and outbound email via the EmailBison API. "
        "Always confirm required identifiers (lead IDs, campaign IDs, email account IDs) before executing "
        "actions that mutate state. When filtering by tags, call `list_tags` to retrieve IDs before supplying them "
        "to other tools.\n"
        "\n"
        "🚨 SEQUENCE STEPS UPDATE WORKFLOW: When a user asks to update campaign sequence steps, you MUST follow this workflow:\n"
        "1. FIRST call C_Get_Campaign_Sequence_Steps with the campaign_id to view all existing sequence steps\n"
        "2. Review the existing steps to identify which steps need to be updated (note their IDs)\n"
        "3. THEN call C_Update_Campaign_Sequence_Steps with the sequence_id and include the 'id' field for each step being updated\n"
        "4. IMPORTANT: Do NOT create new steps when updating existing ones - always include the step 'id' field from the existing steps\n"
        "5. The sequence_id can be found in the Campaign object (not the campaign_id)\n"
        "\n"
        "🚨 VARIABLE FORMAT: When using variables in sequence steps (email_subject, email_body, email_subject_variables), "
        "ALWAYS use uppercase format with single curly braces: {FIRST_NAME}, {LAST_NAME}, {COMPANY}, etc. "
        "NEVER use double curly braces or lowercase: NOT {{first_name}} or {{FIRST_NAME}} or {first_name}. "
        "The correct format is: {FIRST_NAME}, {LAST_NAME}, {COMPANY}, {TITLE}, etc.\n"
        "\n"
        "🚨 THREAD REPLY: When creating or updating sequence steps with thread_reply=true, do NOT include 'Re:' prefix in the email_subject. "
        "The system automatically adds 'Re:' when thread_reply is enabled. If you include 'Re:' manually, it will result in 'Re: Re:' in the final email.\n"
        "\n"
        "🚨 VARIANT STEPS AND ORDER FIELD: When creating sequence steps with variants (A/B testing):\n"
        "- ALL steps (both main and variant): MUST include 'order' field (1, 2, 3, etc.) - order values must be unique and sequential\n"
        "- Main steps (variant=false or null): require 'order' field\n"
        "- Variant steps (variant=true): ALSO require 'order' field - variants need order just like main steps\n"
        "- Variants need: variant=true + variant_from_step (or variant_from_step_id) + order field\n"
        "\n"
        "🚨 CRITICAL: Before making ANY create or update request for sequence steps, you MUST:\n"
        "1. RECHECK the order of ALL steps in your request (both main and variant steps)\n"
        "2. Ensure ALL steps have correct sequential order values (1, 2, 3, etc.) with no gaps or duplicates\n"
        "3. Verify that order values are correct for ALL steps before sending the request\n"
        "DO NOT send the request until you have verified and corrected the order for all steps!"
    ),
    website_url="https://docs.emailbison.com/get-started",
    lifespan=lifespan,
)


RESOURCE_DEFINITIONS: dict[str, dict[str, str]] = {
    "emailbison-api-reference": {
        "name": "emailbison-api-reference",
        "title": "EmailBison API Reference",
        "uri": "document:emailbison/api-reference",
        "description": (
            "🚨 REQUIRED READING: Official REST endpoints for managing leads, campaigns, senders, and more. "
            "MUST be read before using any tools. Contains essential information about filter parameters, "
            "query formats, and endpoint behavior. Useful for inspecting supported query parameters (e.g., pagination, interested flag)."
        ),
        "mime_type": "text/markdown",
        "content": (
            "# EmailBison API Reference\n"
            "\n"
            "- Base URL: `https://send.longrun.agency/api`\n"
            "\n"
            "**Filter Parameters:**\n"
            "- ALL endpoints (GET and POST) use request body for filters\n"
            "\n"
            "- Leads endpoint: `GET /leads` - Filter parameters (`status`, `interested`, `tag_ids`, "
            "`page`, `per_page`, `filters`) are sent in the request body.\n"
            "- Campaigns endpoint: `GET /campaigns` - Filter parameters (`search`, `status`, `tag_ids`, `page`, "
            "`per_page`, `filters`) are sent in the request body. Always retrieve tag IDs via `list_tags` before filtering campaigns.\n"
            "- Create Campaign endpoint: `POST /campaigns` - Requires 'name' field in request body (this is for creating, not listing).\n"
            "- Campaign replies: `POST /campaigns/{id}/replies` - Filter parameters are sent in the request body.\n"
            "- Campaign leads: `GET /campaigns/{id}/leads` - Filter parameters are sent in the request body.\n"
            "\n"
            "Refer to the hosted documentation for complete schemas: https://send.longrun.agency/api/reference\n"
        ),
    },
    "emailbison-mcp-variables": {
        "name": "emailbison-mcp-variables",
        "title": "EmailBison MCP Configuration",
        "uri": "document:emailbison/mcp-variables",
        "description": (
            "🚨 REQUIRED READING: Configuration options for the EmailBison MCP server. "
            "Supports both multi-account mode (config.json) and single-account mode (environment variables)."
        ),
        "mime_type": "text/markdown",
        "content": (
            "# EmailBison MCP Configuration\n"
            "\n"
            "## Multi-Account Mode (Recommended)\n"
            "\n"
            "The server supports multiple accounts via `config.json` file located in the server directory.\n"
            "\n"
            "See `document:emailbison/multi-account-config` for details on setting up `config.json`.\n"
            "\n"
            "## Single-Account Mode (Backward Compatible)\n"
            "\n"
            "If `config.json` is not found, the server falls back to environment variables:\n"
            "\n"
            "- `EMAILBISON_API_KEY`: Workspace API key with access to leads, campaigns, and sending.\n"
            "- `EMAILBISON_BASE_URL`: Overrides the REST base URL (defaults to `https://send.longrun.agency/api`).\n"
            "- `EMAILBISON_TIMEOUT_SECONDS`: Optional request timeout override (defaults to `30`).\n"
            "\n"
            "Set these variables before launching the MCP server so Claude can authenticate with EmailBison.\n"
            "\n"
            "## Using Multiple Accounts\n"
            "\n"
            "When using multi-account mode, you can specify which account/workspace to use for each tool call by including "
            "the `client_name` parameter in tool arguments. Each API key is automatically associated with its workspace, "
            "so no workspace switching is needed - just use the correct `client_name` and the right API key will be used. "
            "If not specified, the default client from config.json is used.\n"
        ),
    },
    "emailbison-multi-account-config": {
        "name": "emailbison-multi-account-config",
        "title": "Multi-Account Configuration",
        "uri": "document:emailbison/multi-account-config",
        "description": (
            "🚨 REQUIRED READING: Guide for setting up multiple EmailBison accounts in config.json. "
            "MUST be read before using multi-account functionality."
        ),
        "mime_type": "text/markdown",
        "content": (
            "# Multi-Account Configuration Guide\n"
            "\n"
            "The EmailBison MCP server supports managing multiple accounts through a `config.json` file.\n"
            "\n"
            "## Configuration File Location\n"
            "\n"
            "Create a `config.json` file in the same directory as the server (`emailbison_mcp/`).\n"
            "\n"
            "## Configuration Structure\n"
            "\n"
            "```json\n"
            "{\n"
            "  \"clients\": {\n"
            "    \"ClientName1\": {\n"
            "      \"mcp_key\": \"api-key-for-client-1\",\n"
            "      \"mcp_url\": \"https://send.longrun.agency/api\"\n"
            "    },\n"
            "    \"ClientName2\": {\n"
            "      \"mcp_key\": \"api-key-for-client-2\",\n"
            "      \"mcp_url\": \"\"\n"
            "    }\n"
            "  },\n"
            "  \"default_client\": \"ClientName1\"\n"
            "}\n"
            "```\n"
            "\n"
            "### Fields\n"
            "\n"
            "- **`clients`** (required): Object containing account configurations\n"
            "  - Each key is a unique client/account name\n"
            "  - Each value is a configuration object with:\n"
            "    - **`mcp_key`** (required): API key for this account\n"
            "    - **`mcp_url`** (optional): Base URL override (empty string uses default)\n"
            "- **`default_client`** (optional): Name of the default client to use when `client_name` is not specified\n"
            "\n"
            "## Using Accounts in Tools\n"
            "\n"
            "All tools accept an optional `client_name` parameter. Each API key is automatically associated with its workspace, "
            "so specifying `client_name` uses that workspace's API key - no workspace switching needed.\n"
            "\n"
            "**CRITICAL: DO NOT use W_List_Workspaces or W_Switch_Workspace to access different workspaces.** "
            "Just use the `client_name` parameter:\n"
            "\n"
            "```\n"
            "# Access ATI workspace\n"
            "C_List_Campaigns(client_name=\"ATI\", page=1, per_page=50)\n"
            "\n"
            "# Access LongRun workspace\n"
            "C_List_Campaigns(client_name=\"LongRun\", page=1, per_page=50)\n"
            "```\n"
            "\n"
            "If `client_name` is not provided, the `default_client` from config.json is used. "
            "Each client's API key automatically accesses its associated workspace. "
            "Workspace switching tools (W_List_Workspaces, W_Switch_Workspace) are only for managing workspaces within a single account, not for accessing different accounts.\n"
            "\n"
            "## Security\n"
            "\n"
            "- **Never commit `config.json` to version control**\n"
            "- Keep API keys secure\n"
            "- Restrict file system access to config.json\n"
        ),
    },
    "emailbison-account-details": {
        "name": "emailbison-account-details",
        "title": "Account Details Endpoint",
        "uri": "document:emailbison/account-details",
        "description": (
            "🚨 REQUIRED READING: Reference for retrieving the authenticated user's account and team information. "
            "MUST be read before using account-related tools."
        ),
        "mime_type": "text/markdown",
        "content": (
            "# Account Details Endpoint\n"
            "\n"
            "- Endpoint: `GET /users`\n"
            "- Requires: Bearer token in `Authorization` header\n"
            "- Returns: User id, name, email, profile photo, and nested team limits (sender email limit, warmup limit, etc.)\n"
            "\n"
            "Example usage:\n"
            "```\n"
            "curl https://send.longrun.agency/api/users \\\n"
            "  --header 'Authorization: Bearer <TOKEN>'\n"
            "```\n"
        ),
    },
    "emailbison-tags": {
        "name": "emailbison-tags",
        "title": "Workspace Tags Endpoint",
        "uri": "document:emailbison/tags",
        "description": (
            "🚨 REQUIRED READING: Reference for listing workspace tags and using their IDs for filtering leads. "
            "MUST be read before filtering leads or campaigns by tags."
        ),
        "mime_type": "text/markdown",
        "content": (
            "# Tags Endpoint\n"
            "\n"
            "- Endpoint: `GET /tags`\n"
            "- Returns: `id`, `name`, `default`, and timestamps for every tag in the workspace.\n"
            "- Usage: When filtering leads, always supply the tag **ID** in `tag_ids` rather than the name.\n"
            "\n"
            "Example usage:\n"
            "```\n"
            "curl https://send.longrun.agency/api/tags \\\n"
            "  --header 'Authorization: Bearer <TOKEN>'\n"
            "```\n"
        ),
    },
    "emailbison-filters": {
        "name": "emailbison-filters",
        "title": "EmailBison Filtering Guide",
        "uri": "document:emailbison/filters",
        "description": (
            "🚨 CRITICAL REQUIRED READING: Complete guide to filtering leads, campaigns, and other entities. "
            "MUST be read before using any filtering operations. All filtering (including tags) is done by putting filters into the request body."
        ),
        "mime_type": "text/markdown",
        "content": (
            "# EmailBison Filtering Guide\n"
            "\n"
            "**CRITICAL: All filtering and tag usage is done by putting filters into the BODY of the request.**\n"
            "\n"
            "## Important Notes\n"
            "\n"
            "- **ALL endpoints (GET and POST) use request body for filters**\n"
            "- Filters are sent as a nested object in the request body under the `filters` key\n"
            "- Tags are filtered using `filters.tag_ids` (array of tag IDs, not names)\n"
            "- Always retrieve tag IDs via `list_tags` before filtering by tags\n"
            "\n"
            "## Filter Structure\n"
            "\n"
            "Filters are provided as a nested object in the request body:\n"
            "\n"
            "```json\n"
            "{\n"
            "  \"page\": 1,\n"
            "  \"per_page\": 15,\n"
            "  \"filters\": {\n"
            "    \"lead_campaign_status\": \"in_sequence\",\n"
            "    \"tag_ids\": [1, 2, 3],\n"
            "    \"emails_sent\": {\n"
            "      \"criteria\": \">=\",\n"
            "      \"value\": 5\n"
            "    }\n"
            "  }\n"
            "}\n"
            "```\n"
            "\n"
            "## Available Filter Options\n"
            "\n"
            "### 1. Lead Campaign Status\n"
            "\n"
            "- **Key**: `filters.lead_campaign_status`\n"
            "- **Type**: `string`\n"
            "- **Values**: One of:\n"
            "  - `in_sequence` - Lead is currently in an email sequence\n"
            "  - `sequence_finished` - Lead has completed the sequence\n"
            "  - `sequence_stopped` - Sequence was stopped for this lead\n"
            "  - `never_contacted` - Lead has never been contacted\n"
            "  - `replied` - Lead has replied to emails\n"
            "\n"
            "**Example:**\n"
            "```json\n"
            "{\n"
            "  \"filters\": {\n"
            "    \"lead_campaign_status\": \"replied\"\n"
            "  }\n"
            "}\n"
            "```\n"
            "\n"
            "### 2. Emails Sent\n"
            "\n"
            "- **Key**: `filters.emails_sent`\n"
            "- **Type**: `object` with `criteria` and `value`\n"
            "- **criteria**: Comparison operator - One of: `=`, `>=`, `>`, `<=`, `<`\n"
            "- **value**: `integer | null` - Number of emails sent\n"
            "\n"
            "**Example:** Filter leads with 5 or more emails sent\n"
            "```json\n"
            "{\n"
            "  \"filters\": {\n"
            "    \"emails_sent\": {\n"
            "      \"criteria\": \">=\",\n"
            "      \"value\": 5\n"
            "    }\n"
            "  }\n"
            "}\n"
            "```\n"
            "\n"
            "### 3. Email Opens\n"
            "\n"
            "- **Key**: `filters.opens`\n"
            "- **Type**: `object` with `criteria` and `value`\n"
            "- **criteria**: Comparison operator - One of: `=`, `>=`, `>`, `<=`, `<`\n"
            "- **value**: `integer | null` - Number of email opens\n"
            "\n"
            "**Example:** Filter leads with more than 10 opens\n"
            "```json\n"
            "{\n"
            "  \"filters\": {\n"
            "    \"opens\": {\n"
            "      \"criteria\": \">\",\n"
            "      \"value\": 10\n"
            "    }\n"
            "  }\n"
            "}\n"
            "```\n"
            "\n"
            "### 4. Replies\n"
            "\n"
            "- **Key**: `filters.replies`\n"
            "- **Type**: `object` with `criteria` and `value`\n"
            "- **criteria**: Comparison operator - One of: `=`, `>=`, `>`, `<=`, `<`\n"
            "- **value**: `integer | null` - Number of replies\n"
            "\n"
            "**Example:** Filter leads with at least 1 reply\n"
            "```json\n"
            "{\n"
            "  \"filters\": {\n"
            "    \"replies\": {\n"
            "      \"criteria\": \">=\",\n"
            "      \"value\": 1\n"
            "    }\n"
            "  }\n"
            "}\n"
            "```\n"
            "\n"
            "### 5. Verification Statuses\n"
            "\n"
            "- **Key**: `filters.verification_statuses`\n"
            "- **Type**: `array` of `string`\n"
            "- **Values**: One or more of:\n"
            "  - `verifying` - Email is being verified\n"
            "  - `verified` - Email is verified\n"
            "  - `risky` - Email is marked as risky\n"
            "  - `unknown` - Verification status is unknown\n"
            "  - `unverified` - Email is not verified\n"
            "  - `inactive` - Email is inactive\n"
            "  - `bounced` - Email has bounced\n"
            "  - `unsubscribed` - Lead has unsubscribed\n"
            "\n"
            "**Example:** Filter verified and risky leads\n"
            "```json\n"
            "{\n"
            "  \"filters\": {\n"
            "    \"verification_statuses\": [\"verified\", \"risky\"]\n"
            "  }\n"
            "}\n"
            "```\n"
            "\n"
            "### 6. Tag IDs (Inclusion)\n"
            "\n"
            "- **Key**: `filters.tag_ids`\n"
            "- **Type**: `array` of `integer`\n"
            "- **Description**: Filter by tag IDs. Only leads/campaigns with these tags will be returned.\n"
            "- **Important**: You MUST call `list_tags` first to get tag IDs (not names)\n"
            "\n"
            "**Example:** Filter leads with tag IDs 1, 5, and 10\n"
            "```json\n"
            "{\n"
            "  \"filters\": {\n"
            "    \"tag_ids\": [1, 5, 10]\n"
            "  }\n"
            "}\n"
            "```\n"
            "\n"
            "### 7. Excluded Tag IDs\n"
            "\n"
            "- **Key**: `filters.excluded_tag_ids`\n"
            "- **Type**: `array` of `integer`\n"
            "- **Description**: Exclude leads/campaigns by tag IDs. Leads/campaigns with these tags will be excluded from results.\n"
            "\n"
            "**Example:** Exclude leads with tag IDs 2 and 3\n"
            "```json\n"
            "{\n"
            "  \"filters\": {\n"
            "    \"excluded_tag_ids\": [2, 3]\n"
            "  }\n"
            "}\n"
            "```\n"
            "\n"
            "### 8. Without Tags\n"
            "\n"
            "- **Key**: `filters.without_tags`\n"
            "- **Type**: `boolean`\n"
            "- **Description**: Only show leads/campaigns that have no tags attached.\n"
            "\n"
            "**Example:** Show only leads without any tags\n"
            "```json\n"
            "{\n"
            "  \"filters\": {\n"
            "    \"without_tags\": true\n"
            "  }\n"
            "}\n"
            "```\n"
            "\n"
            "### 9. Created At Date\n"
            "\n"
            "- **Key**: `filters.created_at`\n"
            "- **Type**: `object` with `criteria` and `value`\n"
            "- **criteria**: Comparison operator - One of: `=`, `>=`, `>`, `<=`, `<`\n"
            "- **value**: `string | null` - Date in `YYYY-MM-DD` format\n"
            "\n"
            "**Example:** Filter leads created on or after 2024-01-01\n"
            "```json\n"
            "{\n"
            "  \"filters\": {\n"
            "    \"created_at\": {\n"
            "      \"criteria\": \">=\",\n"
            "      \"value\": \"2024-01-01\"\n"
            "    }\n"
            "  }\n"
            "}\n"
            "```\n"
            "\n"
            "### 10. Updated At Date\n"
            "\n"
            "- **Key**: `filters.updated_at`\n"
            "- **Type**: `object` with `criteria` and `value`\n"
            "- **criteria**: Comparison operator - One of: `=`, `>=`, `>`, `<=`, `<`\n"
            "- **value**: `string | null` - Date in `YYYY-MM-DD` format\n"
            "\n"
            "**Example:** Filter leads updated before 2024-12-31\n"
            "```json\n"
            "{\n"
            "  \"filters\": {\n"
            "    \"updated_at\": {\n"
            "      \"criteria\": \"<\",\n"
            "      \"value\": \"2024-12-31\"\n"
            "    }\n"
            "  }\n"
            "}\n"
            "```\n"
            "\n"
            "## Combining Multiple Filters\n"
            "\n"
            "You can combine multiple filters in a single request. All filters are applied together (AND logic):\n"
            "\n"
            "**Example:** Find leads that:\n"
            "- Are in sequence\n"
            "- Have tag ID 5\n"
            "- Have sent 3 or more emails\n"
            "- Were created after 2024-01-01\n"
            "\n"
            "```json\n"
            "{\n"
            "  \"page\": 1,\n"
            "  \"per_page\": 15,\n"
            "  \"filters\": {\n"
            "    \"lead_campaign_status\": \"in_sequence\",\n"
            "    \"tag_ids\": [5],\n"
            "    \"emails_sent\": {\n"
            "      \"criteria\": \">=\",\n"
            "      \"value\": 3\n"
            "    },\n"
            "    \"created_at\": {\n"
            "      \"criteria\": \">\",\n"
            "      \"value\": \"2024-01-01\"\n"
            "    }\n"
            "  }\n"
            "}\n"
            "```\n"
            "\n"
            "## Tag Filtering Workflow\n"
            "\n"
            "**CRITICAL: Always get tag IDs before filtering by tags.**\n"
            "\n"
            "1. Call `T_List_Tags` to get all available tags\n"
            "2. Find the tag(s) you need and extract their `id` values\n"
            "3. Use those IDs in `filters.tag_ids` array\n"
            "\n"
            "**Example Workflow:**\n"
            "\n"
            "```\n"
            "Step 1: Call T_List_Tags\n"
            "Response: [\n"
            "  {\"id\": 1, \"name\": \"Google\"},\n"
            "  {\"id\": 2, \"name\": \"Facebook\"},\n"
            "  {\"id\": 3, \"name\": \"LinkedIn\"}\n"
            "]\n"
            "\n"
            "Step 2: Filter leads with tag 'Google' (ID: 1)\n"
            "Request body: {\n"
            "  \"filters\": {\n"
            "    \"tag_ids\": [1]\n"
            "  }\n"
            "}\n"
            "```\n"
            "\n"
            "## Comparison Operators\n"
            "\n"
            "For numeric and date filters, use these comparison operators:\n"
            "\n"
            "- `=` - Equal to\n"
            "- `>=` - Greater than or equal to\n"
            "- `>` - Greater than\n"
            "- `<=` - Less than or equal to\n"
            "- `<` - Less than\n"
            "\n"
            "## Date Format\n"
            "\n"
            "All date values must be in `YYYY-MM-DD` format:\n"
            "\n"
            "- ✅ Correct: `\"2024-01-15\"`\n"
            "- ❌ Wrong: `\"01/15/2024\"`\n"
            "- ❌ Wrong: `\"2024-1-15\"` (missing zero padding)\n"
            "\n"
            "## Summary\n"
            "\n"
            "- **All filters go in the request body** under the `filters` key\n"
            "- **Tags are filtered using `filters.tag_ids`** (array of integers)\n"
            "- **Always get tag IDs first** using `list_tags`\n"
            "- **Combine multiple filters** by including them all in the `filters` object\n"
            "- **Use comparison operators** (`=`, `>=`, `>`, `<=`, `<`) for numeric and date filters\n"
            "- **Date format must be YYYY-MM-DD**\n"
        ),
    },
    "emailbison-pagination": {
        "name": "emailbison-pagination",
        "title": "EmailBison Pagination Guide",
        "uri": "document:emailbison/pagination",
        "description": (
            "🚨 CRITICAL REQUIRED READING: Guide for handling paginated API responses. "
            "MUST be read before using any data-fetching tools. Contains essential pagination requirements "
            "and workflows. Always use pagination when fetching data."
        ),
        "mime_type": "text/markdown",
        "content": (
            "# Pagination Guide\n"
            "\n"
            "**IMPORTANT: Always use pagination when fetching data from EmailBison API.**\n"
            "\n"
            "## Overview\n"
            "\n"
            "Many API endpoints return paginated responses to handle large datasets efficiently. "
            "Responses are broken into pages of 15 entries per page by default.\n"
            "\n"
            "## Response Structure\n"
            "\n"
            "Paginated responses include:\n"
            "\n"
            "- `data`: Array of entries for the current page\n"
            "- `links`: Navigation links for pagination\n"
            "  - `first`: URL to the first page\n"
            "  - `last`: URL to the last page\n"
            "  - `prev`: URL to the previous page (null if on first page)\n"
            "  - `next`: URL to the next page (null if on last page)\n"
            "- `meta`: Pagination metadata\n"
            "  - `current_page`: Current page number\n"
            "  - `from`: Starting entry number\n"
            "  - `last_page`: Total number of pages\n"
            "\n"
            "## How to Use Pagination\n"
            "\n"
            "### Method 1: Using `links.next`\n"
            "\n"
            "1. Send a request to the paginated endpoint\n"
            "2. Process the data in the `data` field\n"
            "3. If `links.next` is not null, send a request to that URL to get the next page\n"
            "4. Repeat until `links.next` is null\n"
            "\n"
            "### Method 2: Using `page` Parameter\n"
            "\n"
            "1. Start with `page=1`\n"
            "2. Process the data in the `data` field\n"
            "3. Increment the page number: `page=2`, `page=3`, etc.\n"
            "4. Continue until you reach `meta.last_page`\n"
            "\n"
            "## Example Request\n"
            "\n"
            "```\n"
            "GET /api/leads?page=1&per_page=15\n"
            "```\n"
            "\n"
            "## Example Response\n"
            "\n"
            "```json\n"
            "{\n"
            "  \"data\": [...],\n"
            "  \"links\": {\n"
            "    \"first\": \"https://send.longrun.agency/api/leads?page=1\",\n"
            "    \"last\": \"https://send.longrun.agency/api/leads?page=4\",\n"
            "    \"prev\": null,\n"
            "    \"next\": \"https://send.longrun.agency/api/leads?page=2\"\n"
            "  },\n"
            "  \"meta\": {\n"
            "    \"current_page\": 1,\n"
            "    \"from\": 1,\n"
            "    \"last_page\": 4\n"
            "  }\n"
            "}\n"
            "```\n"
            "\n"
            "## Endpoints with Pagination\n"
            "\n"
            "The following endpoints support pagination:\n"
            "\n"
            "- `list_leads` - Always paginated (GET with query parameters)\n"
            "- `list_campaigns` - Always paginated (GET with query parameters)\n"
            "- `get_campaign_replies` - Always paginated (POST with body parameters)\n"
            "- `get_campaign_leads` - Always paginated (GET with query parameters)\n"
            "\n"
            "## Critical Pagination Workflow\n"
            "\n"
            "**When a user asks for 'first 15', 'all leads', or any quantity of results:**\n"
            "\n"
            "1. **ALWAYS start with page=1** - Fetch the first page\n"
            "2. **ALWAYS check pagination metadata** - Look for `meta.last_page` or `links.next`\n"
            "3. **ALWAYS fetch additional pages if needed** - If `meta.last_page > 1`, you MUST fetch pages 2, 3, etc.\n"
            "4. **ALWAYS combine results** - Merge results from all pages before responding\n"
            "5. **NEVER assume page 1 has all results** - Even if page 1 has results, check if more pages exist\n"
            "\n"
            "## Example Workflow: Getting 'First 15 Leads with Tag X'\n"
            "\n"
            "```\n"
            "Step 1: Call list_tags to find tag ID for 'Google'\n"
            "Step 2: Call list_leads with tag_ids=[google_tag_id], page=1\n"
            "Step 3: Check response:\n"
            "  - If meta.last_page = 1: You have all results, return first 15\n"
            "  - If meta.last_page > 1: You MUST fetch additional pages\n"
            "Step 4: If more pages exist, call list_leads with page=2, page=3, etc.\n"
            "Step 5: Combine all results from all pages\n"
            "Step 6: Return the first 15 names from the combined results\n"
            "```\n"
            "\n"
            "## Best Practices\n"
            "\n"
            "1. **Always check pagination metadata first** - Don't assume you have all results\n"
            "2. **Handle edge cases** - Empty results, single-page results, API errors\n"
            "3. **Use appropriate page sizes** - Default is 15 per page, can be adjusted with `per_page` parameter\n"
            "4. **Combine results systematically** - Fetch all pages before filtering or limiting results\n"
            "5. **Log pagination progress** - Track which pages have been fetched\n"
            "\n"
            "**Remember: The API ALWAYS returns paginated results. You MUST check for and fetch additional pages!**\n"
        ),
    },
    "emailbison-entity-ids": {
        "name": "emailbison-entity-ids",
        "title": "Entity ID Requirements Guide",
        "uri": "document:emailbison/entity-ids",
        "description": (
            "🚨 CRITICAL REQUIRED READING: Guide for working with entity IDs. "
            "MUST be read before filtering or searching by any entities. "
            "The API requires IDs (not names) for tags, timezones, schedules, campaigns, leads, sender emails, and workspaces."
        ),
        "mime_type": "text/markdown",
        "content": (
            "# Entity ID Requirements Guide\n"
            "\n"
            "**CRITICAL: The EmailBison API requires IDs (not names) for most entity references.**\n"
            "\n"
            "## Required Workflow\n"
            "\n"
            "**BEFORE filtering, searching, or referencing any entity, you MUST first list all available entities to get their IDs.**\n"
            "\n"
            "### Step-by-Step Process:\n"
            "\n"
            "1. **List the entity type** - Call the appropriate list tool to get all available entities\n"
            "2. **Extract the ID** - Find the entity you need and get its `id` field\n"
            "3. **Use the ID** - Use the ID (not the name) in your filter or operation\n"
            "\n"
            "## Entities That Require IDs\n"
            "\n"
            "### Tags (tag_ids)\n"
            "- **List tool**: `T_List_Tags`\n"
            "- **Used in**: Filtering leads, campaigns, sender emails\n"
            "- **Example**: To filter leads by tag 'Google':\n"
            "  1. Call `T_List_Tags` to get all tags\n"
            "  2. Find the tag with name 'Google' and get its `id`\n"
            "  3. Use that `id` in `tag_ids` parameter when filtering\n"
            "\n"
            "### Timezones (timezone id)\n"
            "- **List tool**: `C_List_Schedule_Timezones`\n"
            "- **Used in**: Creating or updating campaign schedules\n"
            "- **Example**: To create a schedule with timezone 'America/New_York':\n"
            "  1. Call `C_List_Schedule_Timezones` to get all timezones\n"
            "  2. Find the timezone with name containing 'New York' and get its `id` field\n"
            "  3. Use that `id` (e.g., 'America/New_York') in the schedule\n"
            "\n"
            "### Schedule Templates (schedule_id)\n"
            "- **List tool**: `C_List_Schedule_Templates`\n"
            "- **Used in**: Creating campaign schedules from templates\n"
            "- **Example**: To create a schedule from a template:\n"
            "  1. Call `C_List_Schedule_Templates` to get all templates\n"
            "  2. Find the template you need and get its `id`\n"
            "  3. Use that `id` in `schedule_id` parameter\n"
            "\n"
            "### Campaigns (campaign_id)\n"
            "- **List tool**: `C_List_Campaigns`\n"
            "- **Used in**: Most campaign-related operations\n"
            "- **Example**: To get leads for a campaign named 'Sales Campaign':\n"
            "  1. Call `C_List_Campaigns` to get all campaigns\n"
            "  2. Find the campaign with name 'Sales Campaign' and get its `id`\n"
            "  3. Use that `id` in `campaign_id` parameter\n"
            "\n"
            "### Leads (lead_id)\n"
            "- **List tool**: `L_List_Leads`\n"
            "- **Used in**: Lead operations, filtering replies\n"
            "- **Example**: To get a specific lead's details:\n"
            "  1. Call `L_List_Leads` to find the lead\n"
            "  2. Get the lead's `id` from the response\n"
            "  3. Use that `id` in `lead_id` parameter\n"
            "\n"
            "### Sender Emails (sender_email_id)\n"
            "- **List tool**: `M_List_Sender_Emails`\n"
            "- **Used in**: Email operations, filtering replies\n"
            "- **Example**: To send an email from a specific sender:\n"
            "  1. Call `M_List_Sender_Emails` to get all sender emails\n"
            "  2. Find the sender email you need and get its `id`\n"
            "  3. Use that `id` in `sender_email_id` parameter\n"
            "\n"
            "### Workspaces (team_id)\n"
            "- **List tool**: `W_List_Workspaces`\n"
            "- **Used in**: Workspace operations\n"
            "- **Example**: To access a different workspace, use `client_name` parameter in tools (e.g., `client_name=\"ATI\"`). "
            "Workspace switching tools are only for managing workspaces within a single account, not for accessing different accounts.\n"
            "\n"
            "### Custom Variables\n"
            "- **List tool**: `W_List_Custom_Variables`\n"
            "- **Used in**: Lead creation/updates\n"
            "- **Example**: To use a custom variable in a lead:\n"
            "  1. Call `W_List_Custom_Variables` to see available variables\n"
            "  2. Use the variable `name` (not ID) in `custom_variables` array\n"
            "\n"
            "## Common Mistakes to Avoid\n"
            "\n"
            "❌ **DON'T**: Use entity names directly in filters\n"
            "✅ **DO**: Always list entities first, then use their IDs\n"
            "\n"
            "❌ **DON'T**: Assume you know the ID\n"
            "✅ **DO**: Always fetch the current list of entities\n"
            "\n"
            "❌ **DON'T**: Use names like 'Google' in tag_ids\n"
            "✅ **DO**: List tags, find 'Google', use its ID\n"
            "\n"
            "## Workflow Example: Filter Leads by Tag\n"
            "\n"
            "```\n"
            "Step 1: Call T_List_Tags to get all tags\n"
            "Step 2: Find tag with name 'Important' → ID is 5\n"
            "Step 3: Call L_List_Leads with tag_ids=[5] (NOT tag_ids=['Important'])\n"
            "```\n"
            "\n"
            "## Workflow Example: Create Schedule with Timezone\n"
            "\n"
            "```\n"
            "Step 1: Call C_List_Schedule_Timezones to get all timezones\n"
            "Step 2: Find timezone 'America/New_York' → ID is 'America/New_York'\n"
            "Step 3: Use timezone: 'America/New_York' in schedule creation\n"
            "```\n"
            "\n"
            "**Remember: ALWAYS list entities before using them. The API requires IDs, not names!**\n"
        ),
    },
}

RESOURCE_DEFINITIONS_BY_URI = {info["uri"]: info for info in RESOURCE_DEFINITIONS.values()}

PROMPT_DEFINITIONS: dict[str, types.Prompt] = {
    "list-interested-leads": types.Prompt(
        name="list-interested-leads",
        description="Retrieve leads that have been flagged as interested.",
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(
                    type="text",
                    text=(
                        "Find any leads that have responded positively in the last two weeks and are marked as "
                        "interested. Return their names, email, last activity, and any associated tags."
                    ),
                ),
            )
        ],
    ),
    "review-active-campaigns": types.Prompt(
        name="review-active-campaigns",
        description="Audit the current campaigns and summarise status, engagement, and next steps.",
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(
                    type="text",
                    text=(
                        "List all non-completed campaigns with send volumes, reply counts, and any that may need "
                        "attention. Highlight paused campaigns separately."
                    ),
                ),
            )
        ],
    ),
    "summarise-account-limits": types.Prompt(
        name="summarise-account-limits",
        description="Review account metadata and highlight current workspace limits.",
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(
                    type="text",
                    text=(
                        "Retrieve my EmailBison account details and summarise the sender email limit, warmup status, "
                        "and any quota metrics I should watch."
                    ),
                ),
            )
        ],
    ),
    "filter-leads-by-tag": types.Prompt(
        name="filter-leads-by-tag",
        description="Demonstrates fetching tag IDs before filtering leads.",
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(
                    type="text",
                    text=(
                        "Find all leads tagged 'Important'. Start by listing tags to obtain the tag ID, then filter "
                        "leads using that id in the tag_ids parameter."
                    ),
                ),
            )
        ],
    ),
    "pagination-example": types.Prompt(
        name="pagination-example",
        description="Example demonstrating proper pagination usage when fetching multiple results.",
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(
                    type="text",
                    text=(
                        "Get me the first 15 names of leads that have the tag 'Google'. "
                        "IMPORTANT: The list_leads endpoint returns paginated results (15 per page by default). "
                        "You MUST:\n"
                        "1. First, call list_tags to find the 'Google' tag ID\n"
                        "2. Call list_leads with tag_ids=[google_tag_id] and page=1\n"
                        "3. Check the response for 'meta.last_page' or 'links.next' to see if there are more pages\n"
                        "4. If there are more pages (meta.last_page > 1), you MUST fetch additional pages (page=2, page=3, etc.) until you have at least 15 results or reach the last page\n"
                        "5. Combine results from all pages and return the first 15 names\n"
                        "\n"
                        "Remember: Never assume page 1 contains all results. Always check pagination metadata and fetch all necessary pages."
                    ),
                ),
            )
        ],
    ),
}

TOOL_DEFINITIONS: list[types.Tool] = [
    types.Tool(
        name="C_Archive_Campaign",
        title="C. Archive Campaign",
        description="Archive a campaign by ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to archive.",
                }
            },
            "required": ["campaign_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Attach_Sender_Emails_To_Campaign",
        title="C. Attach Sender Emails To Campaign",
        description="Attach sender emails to a campaign by providing their sender email IDs. This allows you to configure which email accounts will be used to send emails for the campaign.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to attach sender emails to.",
                },
                "sender_email_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of sender email IDs to attach to the campaign.",
                },
            },
            "required": ["campaign_id", "sender_email_ids"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Create_Campaign",
        title="C. Create Campaign",
        description="Create a new campaign. Provide a name and optionally specify the campaign type or extra settings.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Internal name for the campaign."},
                "type": {
                    "type": "string",
                    "enum": ["outbound", "reply_followup"],
                    "description": "Optional campaign type. Defaults to outbound if omitted.",
                },
                "additional_fields": {
                    "type": "object",
                    "description": (
                        "Advanced JSON payload to merge into the request body (e.g., schedules, limits). "
                        "Fields provided here override defaults."
                    ),
                    "additionalProperties": True,
                }
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Create_Campaign_Schedule",
        title="C. Create Campaign Schedule",
        description=(
            "Define allowable send days and times for a campaign. "
            "🚨 REQUIRED FIRST STEP: If using a timezone, you MUST first call C_List_Schedule_Timezones to get all available timezones. "
            "Use the timezone ID (from the 'id' field, e.g., 'America/New_York') in the schedule, NOT the 'name' field."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to schedule.",
                },
                "schedule": {
                    "type": "object",
                    "description": (
                        "Schedule configuration requiring booleans for weekdays (`monday`-`sunday`), "
                        "`start_time`, `end_time`, `timezone`, and optional `save_as_template`."
                    ),
                    "required": [
                        "monday",
                        "tuesday",
                        "wednesday",
                        "thursday",
                        "friday",
                        "saturday",
                        "sunday",
                        "start_time",
                        "end_time",
                        "timezone",
                    ],
                    "additionalProperties": True,
                },
            },
            "required": ["campaign_id", "schedule"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Create_Campaign_Schedule_From_Template",
        title="C. Create Campaign Schedule From Template",
        description=(
            "Create a campaign schedule using a saved schedule template. "
            "🚨 REQUIRED FIRST STEP: You MUST first call C_List_Schedule_Templates to get all available templates and their IDs. "
            "Use the template ID (not name) in the schedule_id parameter."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to create the schedule for.",
                },
                "schedule_id": {
                    "type": "integer",
                    "description": "ID of the schedule template to use. Retrieve template IDs via list_schedule_templates.",
                },
            },
            "required": ["campaign_id", "schedule_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Create_Campaign_Sequence_Steps",
        title="C. Create Campaign Sequence Steps",
        description=(
            "Create campaign sequence steps from scratch. Each step defines an email with subject, body, wait time, and optional variant settings. "
            "🚨 CRITICAL: Before making the request, RECHECK the order of ALL steps: ALL steps (both main and variant) need sequential order (1, 2, 3...). "
            "🚨 VARIABLE FORMAT: Use variables as {FIRST_NAME}, {LAST_NAME}, {COMPANY}, etc. (uppercase, single curly braces). "
            "NEVER use {{first_name}} or {{FIRST_NAME}} or {first_name} (no double braces, no lowercase). "
            "🚨 THREAD REPLY: When thread_reply=true, do NOT include 'Re:' prefix in email_subject. The system adds it automatically. "
            "🚨 VARIANT STEPS: ALL steps (main and variant) require 'order' field. Variant steps need: variant=true + variant_from_step (or variant_from_step_id) + order field."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "The ID of the campaign.",
                },
                "title": {
                    "type": "string",
                    "description": "The title for the sequence.",
                },
                "sequence_steps": {
                    "type": "array",
                    "description": "The array containing the sequence steps.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "email_body": {
                                "type": "string",
                                "description": "The body of the email. Use variables as {FIRST_NAME}, {LAST_NAME}, {COMPANY}, etc. (uppercase, single curly braces). NOT {{first_name}} or {first_name}.",
                            },
                            "email_subject": {
                                "type": "string",
                                "description": "The subject for the email. Use variables as {FIRST_NAME}, {LAST_NAME}, {COMPANY}, etc. (uppercase, single curly braces). NOT {{first_name}} or {first_name}.",
                            },
                            "wait_in_days": {
                                "type": "integer",
                                "description": "The days to wait.",
                            },
                            "attachments": {
                                "type": ["string", "null"],
                                "description": "The email attachments.",
                            },
                            "email_subject_variables": {
                                "type": "array",
                                "items": {"type": ["string", "null"]},
                                "description": "The subject variables. Use format {FIRST_NAME}, {LAST_NAME}, etc. (uppercase, single curly braces). NOT {{first_name}} or {first_name}.",
                            },
                            "order": {
                                "type": ["integer", "null"],
                                "description": "The order of the step. REQUIRED for ALL steps (both main and variant). Order values must be unique and sequential.",
                            },
                            "thread_reply": {
                                "type": ["boolean", "null"],
                                "description": "Whether the step should be a reply from the previous step. When true, do NOT include 'Re:' prefix in email_subject - the system adds it automatically.",
                            },
                            "variant": {
                                "type": ["boolean", "null"],
                                "description": "Whether the step is variant of another step.",
                            },
                            "variant_from_step": {
                                "type": ["integer", "null"],
                                "description": "The order number of a step in the current request to be a variant of. Cannot be used with variant_from_step_id.",
                            },
                            "variant_from_step_id": {
                                "type": ["integer", "null"],
                                "description": "The ID of an already saved step to be a variant of. Cannot be used with variant_from_step.",
                            },
                        },
                        "required": ["email_body", "email_subject", "wait_in_days"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["campaign_id", "title", "sequence_steps"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Delete_Sequence_Step",
        title="C. Delete Sequence Step",
        description="Delete a specific sequence step from a sequence. Get sequence step IDs by calling get_campaign_sequence_steps.",
        inputSchema={
            "type": "object",
            "properties": {
                "sequence_step_id": {
                    "type": "integer",
                    "description": "ID of the sequence step to delete. You can get a list of all campaign sequence steps by calling get_campaign_sequence_steps.",
                },
            },
            "required": ["sequence_step_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Duplicate_Campaign",
        title="C. Duplicate Campaign",
        description="Create a copy of an existing campaign by ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to duplicate.",
                }
            },
            "required": ["campaign_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Get_Campaign_Details",
        title="C. Get Campaign Details",
        description=(
            "Retrieve the details of a specific campaign. "
            "🚨 REQUIRED FIRST STEP: You MUST first call C_List_Campaigns to find the campaign and get its ID. "
            "Returns comprehensive information including campaign ID, UUID, name, type, status, completion percentage, email statistics (sent, opened, replied, bounced, unsubscribed, interested), lead counts, settings (max emails per day, plain text, open tracking, unsubscribe settings), timestamps, and associated tags."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to retrieve details for.",
                },
            },
            "required": ["campaign_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Get_Campaign_Leads",
        title="C. Get Campaign Leads",
        description=(
            "Retrieve all leads associated with a campaign. "
            "🚨 REQUIRED FIRST STEP: You MUST first call C_List_Campaigns to find the campaign and get its ID. "
            "If filtering by tags, you MUST first call T_List_Tags to get tag IDs (not names). "
            "Returns paginated results (15 per page by default). Uses GET request with body for filters. "
            "Supports filtering by search term and complex filters for status, emails sent, opens, replies, verification statuses, tags, and dates. "
            "CRITICAL: This endpoint ALWAYS returns paginated results. You MUST check the response for 'links.next' or 'meta.last_page' to determine if there are more pages. "
            "If the user asks for 'all leads' or 'first 15' or multiple results, you MUST fetch all pages. Always use pagination - never assume the first page contains all results."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to retrieve leads for.",
                },
                "page": {
                    "type": "integer",
                    "description": "Page number to retrieve (default: 1). Use pagination to fetch all data.",
                    "default": 1,
                },
                "per_page": {
                    "type": "integer",
                    "description": "Number of results per page (default: 15).",
                    "default": 15,
                },
                "search": {
                    "type": "string",
                    "description": "Search term for filtering leads.",
                },
                "filters": {
                    "type": "object",
                    "description": "Filter parameters sent in the request body. All filters are nested in this object. See document:emailbison/filters for complete filter options and examples.",
                    "properties": {
                        "lead_campaign_status": {
                            "type": "string",
                            "enum": ["in_sequence", "sequence_finished", "sequence_stopped", "never_contacted", "replied"],
                            "description": "Filter by lead campaign status.",
                        },
                        "emails_sent": {
                            "type": "object",
                            "description": "Filter by number of emails sent.",
                            "properties": {
                                "criteria": {
                                    "type": "string",
                                    "enum": ["=", ">=", ">", "<=", "<"],
                                    "description": "Comparison operator.",
                                },
                                "value": {
                                    "type": "integer",
                                    "description": "Value for the number of emails sent.",
                                },
                            },
                        },
                        "opens": {
                            "type": "object",
                            "description": "Filter by number of email opens.",
                            "properties": {
                                "criteria": {
                                    "type": "string",
                                    "enum": ["=", ">=", ">", "<=", "<"],
                                    "description": "Comparison operator.",
                                },
                                "value": {
                                    "type": "integer",
                                    "description": "Value for the number of opens.",
                                },
                            },
                        },
                        "replies": {
                            "type": "object",
                            "description": "Filter by number of replies.",
                            "properties": {
                                "criteria": {
                                    "type": "string",
                                    "enum": ["=", ">=", ">", "<=", "<"],
                                    "description": "Comparison operator.",
                                },
                                "value": {
                                    "type": "integer",
                                    "description": "Value for the number of replies.",
                                },
                            },
                        },
                        "verification_statuses": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["verifying", "verified", "risky", "unknown", "unverified", "inactive", "bounced", "unsubscribed"],
                            },
                            "description": "Filter by verification statuses.",
                        },
                        "tag_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Array of tag IDs to filter by. Use list_tags to get tag IDs.",
                        },
                        "excluded_tag_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Array of tag IDs to exclude. Use list_tags to get tag IDs.",
                        },
                        "without_tags": {
                            "type": "boolean",
                            "description": "Only show leads that have no tags attached.",
                        },
                        "created_at": {
                            "type": "object",
                            "description": "Filter by created_at date.",
                            "properties": {
                                "criteria": {
                                    "type": "string",
                                    "enum": ["=", ">=", ">", "<=", "<"],
                                    "description": "Comparison operator.",
                                },
                                "value": {
                                    "type": "string",
                                    "format": "date",
                                    "description": "Date value in YYYY-MM-DD format.",
                                },
                            },
                        },
                        "updated_at": {
                            "type": "object",
                            "description": "Filter by updated_at date.",
                            "properties": {
                                "criteria": {
                                    "type": "string",
                                    "enum": ["=", ">=", ">", "<=", "<"],
                                    "description": "Comparison operator.",
                                },
                                "value": {
                                    "type": "string",
                                    "format": "date",
                                    "description": "Date value in YYYY-MM-DD format.",
                                },
                            },
                        },
                    },
                },
            },
            "required": ["campaign_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Get_Campaign_Line_Area_Chart_Stats",
        title="C. Get Campaign Line Area Chart Stats",
        description="Retrieve full normalized stats by date for a given period. Returns time-series data for various events including Replied, Total Opens, Unique Opens, Sent, Bounced, Unsubscribed, and Interested. Each event includes a label, color, and an array of date-value pairs showing the metric value for each date in the period.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to retrieve stats for.",
                },
                "start_date": {
                    "type": "string",
                    "format": "date",
                    "description": "Start date for the statistics period. Must be a valid date in YYYY-MM-DD format (e.g., '2024-07-01').",
                },
                "end_date": {
                    "type": "string",
                    "format": "date",
                    "description": "End date for the statistics period. Must be a valid date in YYYY-MM-DD format (e.g., '2024-07-19').",
                },
            },
            "required": ["campaign_id", "start_date", "end_date"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Get_Campaign_Replies",
        title="C. Get Campaign Replies",
        description=(
            "Retrieve all replies associated with a campaign. "
            "🚨 REQUIRED FIRST STEP: You MUST first call C_List_Campaigns to find the campaign and get its ID. "
            "If filtering by sender_email_id, you MUST first call M_List_Sender_Emails to get sender email IDs. "
            "If filtering by lead_id, you MUST first call L_List_Leads to get lead IDs. "
            "If filtering by tag_ids, you MUST first call T_List_Tags to get tag IDs (not names). "
            "Returns paginated results (15 per page by default). IMPORTANT: All filter parameters (search, status, folder, read, sender_email_id, lead_id, tag_ids, filters) are sent in the request body, not as query parameters. "
            "CRITICAL: This endpoint ALWAYS returns paginated results. You MUST check the response for 'links.next' or 'meta.last_page' to determine if there are more pages. "
            "If the user asks for 'all replies' or multiple results, you MUST fetch all pages. Always use pagination - never assume the first page contains all results."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to retrieve replies for.",
                },
                "page": {
                    "type": "integer",
                    "description": "Page number to retrieve (default: 1). Use pagination to fetch all data.",
                    "default": 1,
                },
                "per_page": {
                    "type": "integer",
                    "description": "Number of results per page (default: 15).",
                    "default": 15,
                },
                "search": {
                    "type": "string",
                    "description": "Search term for filtering replies.",
                },
                "status": {
                    "type": "string",
                    "enum": ["interested", "automated_reply", "not_automated_reply"],
                    "description": "Filter by status.",
                },
                "folder": {
                    "type": "string",
                    "enum": ["inbox", "sent", "spam", "bounced", "all"],
                    "description": "Filter by folder.",
                },
                "read": {
                    "type": "boolean",
                    "description": "Filter by read status.",
                },
                "sender_email_id": {
                    "type": "integer",
                    "description": "ID of the sender email address to filter by.",
                },
                "lead_id": {
                    "type": "integer",
                    "description": "ID of a lead to filter by.",
                },
                "tag_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of tag IDs to filter by. Use list_tags to get tag IDs.",
                },
                "query_campaign_id": {
                    "type": "integer",
                    "description": "Additional campaign ID filter sent in the request body.",
                },
                "filters": {
                    "type": "object",
                    "description": "Additional filter parameters sent in the request body. All filters are nested in this object. See document:emailbison/filters for complete filter options and examples.",
                },
            },
            "required": ["campaign_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Get_Campaign_Schedule",
        title="C. Get Campaign Schedule",
        description="Read the configured schedule for a campaign.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign whose schedule should be retrieved.",
                }
            },
            "required": ["campaign_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Get_Campaign_Scheduled_Emails",
        title="C. Get Campaign Scheduled Emails",
        description="Retrieve all scheduled emails associated with a campaign. Returns detailed information about each scheduled email including subject, body, status, scheduled dates, lead information, and sender email details. Supports filtering by scheduled date, local scheduled date, and status.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to retrieve scheduled emails for.",
                },
                "scheduled_date": {
                    "type": "string",
                    "description": "Filter by scheduled date. Must be a valid date string.",
                },
                "scheduled_date_local": {
                    "type": "string",
                    "description": "Filter by local scheduled date. Must be a valid date string.",
                },
                "status": {
                    "type": "string",
                    "enum": ["scheduled", "sent", "failed", "paused"],
                    "description": "Filter by email status.",
                },
            },
            "required": ["campaign_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Get_Campaign_Sender_Emails",
        title="C. Get Campaign Sender Emails",
        description="Retrieve all email accounts (sender emails) associated with a campaign. Returns detailed information about each sender email including name, email address, IMAP/SMTP settings, daily limits, status, statistics (emails sent, replies, opens, etc.), and tags.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to retrieve sender emails for.",
                },
            },
            "required": ["campaign_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Get_Campaign_Sending_Schedule",
        title="C. Get Campaign Sending Schedule",
        description="View the sending schedule for a specific campaign on a given day.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to view the sending schedule for.",
                },
                "day": {
                    "type": "string",
                    "enum": ["today", "tomorrow", "day_after_tomorrow"],
                    "description": "The day to view the sending schedule for.",
                },
            },
            "required": ["campaign_id", "day"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Get_Campaign_Sequence_Steps",
        title="C. Get Campaign Sequence Steps",
        description=(
            "View the sequence steps of a campaign, including email subjects, bodies, wait times, and other step details. "
            "🚨 REQUIRED FIRST STEP: You MUST call this tool FIRST before updating sequence steps to see existing steps and their IDs. "
            "When updating sequence steps, use the step IDs from this response in the C_Update_Campaign_Sequence_Steps tool."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to view sequence steps for.",
                },
            },
            "required": ["campaign_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Get_Campaign_Stats",
        title="C. Get Campaign Stats",
        description="Retrieve campaign statistics (summary) for a specified date range. Returns overall campaign metrics including emails sent, leads contacted, opens, replies, bounces, unsubscribes, interested leads, and percentages. Also includes per-sequence-step statistics showing performance for each email in the sequence.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to retrieve statistics for.",
                },
                "start_date": {
                    "type": "string",
                    "format": "date",
                    "description": "Start date for the statistics period. Must be a valid date in YYYY-MM-DD format (e.g., '2024-07-01').",
                },
                "end_date": {
                    "type": "string",
                    "format": "date",
                    "description": "End date for the statistics period. Must be a valid date in YYYY-MM-DD format (e.g., '2024-07-19').",
                },
            },
            "required": ["campaign_id", "start_date", "end_date"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Get_Sending_Schedules",
        title="C. Get Sending Schedules",
        description="View sending schedules for campaigns on a specific day.",
        inputSchema={
            "type": "object",
            "properties": {
                "day": {
                    "type": "string",
                    "enum": ["today", "tomorrow", "day_after_tomorrow"],
                    "description": "The day to view sending schedules for.",
                },
            },
            "required": ["day"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Import_Leads_By_IDs",
        title="C. Import Leads By IDs",
        description="Import leads by their IDs into a campaign. For active campaigns, leads are cached locally and synced every 5 minutes to ensure no interruption to sending. IMPORTANT: For reply followup campaigns, this will start the conversation from the last sent reply. For more control over which conversation to follow up on, consider using a more explicit endpoint.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to import leads into.",
                },
                "lead_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of lead IDs to import into the campaign.",
                },
                "allow_parallel_sending": {
                    "type": "boolean",
                    "description": "Force add leads that are 'In Sequence' in other campaigns. If true, allows leads to be in multiple campaigns simultaneously.",
                },
            },
            "required": ["campaign_id", "lead_ids"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Import_Leads_From_List",
        title="C. Import Leads From List",
        description="Import leads from an existing lead list into a campaign. This allows you to add multiple leads at once by referencing a lead list ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to import leads into.",
                },
                "lead_list_id": {
                    "type": "integer",
                    "description": "ID of the lead list to import from.",
                },
                "allow_parallel_sending": {
                    "type": "boolean",
                    "description": "Force add leads that are 'In Sequence' in other campaigns. If true, allows leads to be in multiple campaigns simultaneously.",
                },
            },
            "required": ["campaign_id", "lead_list_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_List_Campaigns",
        title="C. List Campaigns",
        description=(
            "🚨 REQUIRED FIRST STEP: Retrieve campaigns with pagination, optional search, status, and tag filters (use tag IDs). "
            "MUST be called before using any campaign_id in other operations. "
            "If filtering by tags, you MUST first call T_List_Tags to get tag IDs (not names). "
            "Uses GET request with body for filters. "
            "CRITICAL: This endpoint ALWAYS returns paginated results (15 per page by default). "
            "You MUST check the response for 'links.next' or 'meta.last_page' to determine if there are more pages. "
            "If the user asks for 'all campaigns' or multiple results, you MUST fetch all pages. "
            "Always use pagination - never assume the first page contains all results."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "search": {
                    "type": ["string", "null"],
                    "description": "Optional search term to match campaign names or metadata.",
                },
                "status": {
                    "type": "string",
                    "description": (
                        "Optional filter for campaign status. Supported values include "
                        "`draft`, `launching`, `active`, `stopped`, `completed`, `paused`, `failed`, `queued`, `archived`."
                    ),
                },
                "tag_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Optional list of tag IDs to filter campaigns. Retrieve IDs via the list_tags tool.",
                },
                "page": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 1,
                    "description": "Page number to load.",
                },
                "per_page": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 50,
                    "description": "Number of campaigns per page.",
                },
                "filters": {
                    "type": "object",
                    "description": "Additional filter parameters sent in the request body. All filters are nested in this object. See document:emailbison/filters for complete filter options and examples.",
                    "additionalProperties": True,
                },
            },
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_List_Schedule_Templates",
        title="C. List Schedule Templates",
        description=(
            "🚨 REQUIRED FIRST STEP: Retrieve all saved schedule templates for the workspace. "
            "MUST be called before using schedule_id in C_Create_Campaign_Schedule_From_Template. "
            "Returns template IDs that are required for creating schedules from templates."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_List_Schedule_Timezones",
        title="C. List Schedule Timezones",
        description=(
            "🚨 REQUIRED FIRST STEP: Retrieve all available timezones for campaign schedules. "
            "MUST be called before creating or updating campaign schedules. "
            "Use the timezone ID (from the 'id' field, e.g., 'America/New_York') when creating or updating schedules. "
            "Do NOT use the 'name' field - only use the 'id' field."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Pause_Campaign",
        title="C. Pause Campaign",
        description="Pause an active campaign by ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to pause.",
                }
            },
            "required": ["campaign_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Remove_Campaign_Leads",
        title="C. Remove Campaign Leads",
        description="Remove one or more leads from a campaign by providing their lead IDs.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to remove leads from.",
                },
                "lead_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of lead IDs to remove from the campaign.",
                },
            },
            "required": ["campaign_id", "lead_ids"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Remove_Sender_Emails_From_Campaign",
        title="C. Remove Sender Emails From Campaign",
        description="Remove sender emails from a draft or paused campaign by providing their sender email IDs. Note: This operation can only be performed on campaigns that are in draft or paused status.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to remove sender emails from.",
                },
                "sender_email_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of sender email IDs to remove from the campaign.",
                },
            },
            "required": ["campaign_id", "sender_email_ids"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Resume_Campaign",
        title="C. Resume Campaign",
        description="Resume a paused campaign by ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to resume.",
                }
            },
            "required": ["campaign_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Send_Sequence_Step_Test_Email",
        title="C. Send Sequence Step Test Email",
        description="Send a test email from a sequence step. Requires at least one lead in the campaign. Get sequence step IDs by calling get_campaign_sequence_steps.",
        inputSchema={
            "type": "object",
            "properties": {
                "sequence_step_id": {
                    "type": "integer",
                    "description": "ID of the sequence step to send a test email from. You can get a list of all campaign sequence steps by calling get_campaign_sequence_steps.",
                },
                "sender_email_id": {
                    "type": "integer",
                    "description": "ID of the sender email to send from.",
                },
                "to_email": {
                    "type": "string",
                    "format": "email",
                    "description": "The email address to send the sequence step test email to.",
                },
                "use_dedicated_ips": {
                    "type": "boolean",
                    "description": "Send using the dedicated campaign IPs instead of the instance IP.",
                },
            },
            "required": ["sequence_step_id", "sender_email_id", "to_email"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Stop_Future_Emails_For_Leads",
        title="C. Stop Future Emails For Leads",
        description="Stop future emails for selected leads in a campaign. This prevents the campaign from sending additional emails to the specified leads.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to stop future emails for leads.",
                },
                "lead_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of lead IDs to stop future emails for.",
                },
            },
            "required": ["campaign_id", "lead_ids"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Update_Campaign_Schedule",
        title="C. Update Campaign Schedule",
        description=(
            "Replace the schedule for a campaign. "
            "🚨 REQUIRED FIRST STEP: If using a timezone, you MUST first call C_List_Schedule_Timezones to get all available timezones. "
            "Use the timezone ID (from the 'id' field, e.g., 'America/New_York') in the schedule, NOT the 'name' field."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to update.",
                },
                "schedule": {
                    "type": "object",
                    "description": (
                        "Schedule payload mirroring the create endpoint. All required fields must be provided."
                    ),
                    "required": [
                        "monday",
                        "tuesday",
                        "wednesday",
                        "thursday",
                        "friday",
                        "saturday",
                        "sunday",
                        "start_time",
                        "end_time",
                        "timezone",
                        "save_as_template",
                    ],
                    "additionalProperties": True,
                },
            },
            "required": ["campaign_id", "schedule"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Update_Campaign_Sequence_Steps",
        title="C. Update Campaign Sequence Steps",
        description=(
            "Update existing campaign sequence steps. This endpoint allows the authenticated user to update the campaign sequence steps. "
            "The ID of the sequence. You can get this on the Campaign object. "
            "🚨 CRITICAL WORKFLOW: Before calling this tool, you MUST FIRST call C_Get_Campaign_Sequence_Steps to view existing steps. "
            "When updating, you MUST include the 'id' field for each step being updated (from the get response). "
            "Do NOT create new steps when the user asks to update existing ones - always include step IDs. "
            "Only steps with an 'id' field will be updated; steps without 'id' will be treated as new steps. "
            "🚨 CRITICAL: Before making the request, RECHECK the order of ALL steps: ALL steps (both main and variant) need correct sequential order (1, 2, 3...). "
            "Verify order is correct for ALL steps before sending. "
            "🚨 VARIABLE FORMAT: Use variables as {FIRST_NAME}, {LAST_NAME}, {COMPANY}, etc. (uppercase, single curly braces). "
            "NEVER use {{first_name}} or {{FIRST_NAME}} or {first_name} (no double braces, no lowercase). "
            "🚨 THREAD REPLY: When thread_reply=true, do NOT include 'Re:' prefix in email_subject. The system adds it automatically. "
            "🚨 VARIANT STEPS: ALL steps (main and variant) require 'order' field. Variant steps need: variant=true + variant_from_step_id + order field."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "sequence_id": {
                    "type": "integer",
                    "description": "The ID of the sequence. You can get this on the Campaign object.",
                },
                "title": {
                    "type": "string",
                    "description": "The title for the sequence.",
                },
                "sequence_steps": {
                    "type": "array",
                    "description": "The array containing the sequence steps.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "integer",
                                "description": "The ID of the sequence step.",
                            },
                            "email_body": {
                                "type": "string",
                                "description": "The body of the email. Use variables as {FIRST_NAME}, {LAST_NAME}, {COMPANY}, etc. (uppercase, single curly braces). NOT {{first_name}} or {first_name}.",
                            },
                            "email_subject": {
                                "type": "string",
                                "description": "The subject for the email. Use variables as {FIRST_NAME}, {LAST_NAME}, {COMPANY}, etc. (uppercase, single curly braces). NOT {{first_name}} or {first_name}.",
                            },
                            "order": {
                                "type": "integer",
                                "description": "The order of the step. REQUIRED for ALL steps (both main and variant). Order values must be unique and sequential.",
                            },
                            "wait_in_days": {
                                "type": "integer",
                                "description": "The days to wait.",
                            },
                            "attachments": {
                                "type": ["string", "null"],
                                "description": "The email attachments.",
                            },
                            "email_subject_variables": {
                                "type": "array",
                                "items": {"type": ["string", "null"]},
                                "description": "The subject variables. Use format {FIRST_NAME}, {LAST_NAME}, etc. (uppercase, single curly braces). NOT {{first_name}} or {first_name}.",
                            },
                            "thread_reply": {
                                "type": ["boolean", "null"],
                                "description": "Whether the step should be a reply from the previous step. When true, do NOT include 'Re:' prefix in email_subject - the system adds it automatically.",
                            },
                            "variant": {
                                "type": ["boolean", "null"],
                                "description": "Whether the step is variant of another step.",
                            },
                            "variant_from_step_id": {
                                "type": "integer",
                                "description": "The step ID this step will be a variant of (required if variant is true).",
                            },
                        },
                        "required": ["id", "email_body", "email_subject", "order", "wait_in_days"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["sequence_id", "title", "sequence_steps"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="C_Update_Campaign_Settings",
        title="C. Update Campaign Settings",
        description="Patch campaign options such as send limits, unsubscribe text, and tracking flags.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to update.",
                },
                "updates": {
                    "type": "object",
                    "description": (
                        "Fields to patch on the campaign. Supported keys include `name`, `max_emails_per_day`, "
                        "`max_new_leads_per_day`, `plain_text`, `open_tracking`, `reputation_building`, "
                        "`can_unsubscribe`, and `unsubscribe_text`."
                    ),
                    "additionalProperties": True,
                },
            },
            "required": ["campaign_id", "updates"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="L_Bulk_Create_Leads_CSV",
        title="L. Bulk Create Leads CSV",
        description="Create multiple leads in a single request using a CSV file. Uploads the CSV content along with column mapping configuration. Returns a list of processing results with status, leads processed, succeeded, and failed counts. The CSV content should be provided as a string containing the CSV data.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the contact list to create.",
                },
                "csv_content": {
                    "type": "string",
                    "description": "The CSV file content as a string. Should contain headers in the first row and data rows following.",
                },
                "columns_to_map": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "email": {
                                "type": "string",
                                "description": "The email address header field from the CSV (required).",
                            },
                            "first_name": {
                                "type": "string",
                                "description": "The first name header field from the CSV (required).",
                            },
                            "last_name": {
                                "type": "string",
                                "description": "The last name header field from the CSV (required).",
                            },
                            "company": {
                                "type": "string",
                                "description": "The company name header field from the CSV (optional).",
                            },
                            "title": {
                                "type": "string",
                                "description": "The title header field from the CSV (optional).",
                            },
                            "custom_variable": {
                                "type": "string",
                                "description": "The header field from your CSV to match a custom variable (optional).",
                            },
                        },
                        "required": ["email", "first_name", "last_name"],
                        "additionalProperties": False,
                    },
                    "description": "Array of column mapping objects. Each object maps CSV header fields to lead fields. Must include email, first_name, and last_name mappings. Optional: company, title, custom_variable.",
                },
                "existing_lead_behavior": {
                    "type": "string",
                    "enum": ["put", "patch", "skip"],
                    "description": "Behavior when a lead already exists. 'put' (default): replace all fields including custom variables (fields not passed are cleared). 'patch': only update fields that are passed (fields not passed are kept). 'skip': do not process the lead.",
                },
            },
            "required": ["name", "csv_content", "columns_to_map"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="L_Create_Lead",
        title="L. Create Lead",
        description="Create a single lead (contact) record. Returns the created lead with ID, contact information, status, custom variables, and statistics.",
        inputSchema={
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "format": "email",
                    "description": "The email address of the contact. Must be unique and in a valid email format.",
                },
                "first_name": {
                    "type": "string",
                    "description": "The first name of the contact.",
                },
                "last_name": {
                    "type": "string",
                    "description": "The last name of the contact.",
                },
                "company": {
                    "type": "string",
                    "description": "The company name of the contact.",
                },
                "title": {
                    "type": "string",
                    "description": "The title of the contact.",
                },
                "notes": {
                    "type": "string",
                    "description": "Additional notes about the contact.",
                },
                "custom_variables": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the custom variable. Use list_custom_variables to see available custom variables.",
                            },
                            "value": {
                                "type": "string",
                                "description": "Value for the custom variable.",
                            },
                        },
                        "required": ["name", "value"],
                        "additionalProperties": False,
                    },
                    "description": "Array of custom variable objects. Each object should have 'name' and 'value' properties.",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of tag IDs to attach to the lead. Use list_tags to get tag IDs.",
                },
            },
            "required": ["email", "first_name", "last_name"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="L_Get_Lead",
        title="L. Get Lead",
        description="Retrieve the details of a specific lead by its ID or email address. Returns comprehensive information including contact details (first name, last name, email, title, company, notes), status, custom variables, lead campaign data, overall statistics (emails sent, opens, replies), and timestamps.",
        inputSchema={
            "type": "object",
            "properties": {
                "lead_id": {
                    "type": "string",
                    "description": "The ID (integer) or email address (string) of the lead to retrieve.",
                },
            },
            "required": ["lead_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="L_Get_Lead_Scheduled_Emails",
        title="L. Get Lead Scheduled Emails",
        description="Retrieve all scheduled emails for a specific lead. Returns an array of scheduled email objects with comprehensive information including email ID, campaign ID, lead ID, sender email ID, sequence step ID, thread reply flag, email subject and body, status (scheduled, sending, paused, stopped, bounced, unsubscribed, replied), scheduled dates, sent date, engagement metrics (opens, clicks, replies, interested), and full lead and sender email details.",
        inputSchema={
            "type": "object",
            "properties": {
                "lead_id": {
                    "type": "string",
                    "description": "The ID (integer) or email address (string) of the lead to retrieve scheduled emails for.",
                },
            },
            "required": ["lead_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="L_Get_Lead_Sent_Emails",
        title="L. Get Lead Sent Emails",
        description="Retrieve all sent campaign emails for a specific lead. Returns an array of sent email objects with comprehensive information including email ID, campaign ID, lead ID, sender email ID, sequence step ID, thread reply flag, email subject and body, status (sent), scheduled dates, sent date, and engagement metrics (opens, clicks, replies, interested, unique replies, unique opens).",
        inputSchema={
            "type": "object",
            "properties": {
                "lead_id": {
                    "type": "string",
                    "description": "The ID (integer) or email address (string) of the lead to retrieve sent emails for.",
                },
            },
            "required": ["lead_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="L_List_Leads",
        title="L. List Leads",
        description=(
            "🚨 REQUIRED FIRST STEP: Retrieve a paginated list of all leads for the authenticated user. "
            "MUST be called before using any lead_id in other operations. "
            "Supports extensive filtering options including search, status, campaign status, email metrics (sent, opens, replies), verification statuses, tags, and date ranges. "
            "If filtering by tags, you MUST first call T_List_Tags to get tag IDs (not names). "
            "Uses GET request with body for filters. "
            "🚨 CRITICAL PAGINATION REQUIREMENT: This endpoint ALWAYS returns paginated results (15 per page by default). "
            "You MUST: (1) Fetch page=1 first, (2) Check 'meta.last_page' or 'links.next' in the response, "
            "(3) If meta.last_page > 1, you MUST fetch ALL pages (page=2, page=3, etc. up to meta.last_page), "
            "(4) Combine results from ALL pages before responding. "
            "If user asks for 'first 15 leads' or 'all leads with tag X', you MUST fetch ALL pages first, then return the requested quantity. "
            "NEVER assume page 1 contains all results - always check and fetch additional pages!"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "Search term for filtering leads.",
                },
                "status": {
                    "type": "string",
                    "description": "Optional lead status filter (e.g., active, paused, unsubscribed).",
                },
                "page": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 1,
                    "description": "Page number to retrieve. CRITICAL: Always start with page=1, then check 'meta.last_page' in the response. If last_page > 1, you MUST fetch additional pages (page=2, page=3, etc.) to get all results.",
                },
                "per_page": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 50,
                    "description": "Number of leads per page.",
                },
                "tag_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional collection of tag IDs to filter by.",
                },
                "interested": {
                    "type": "boolean",
                    "description": "When true, only return leads flagged as interested.",
                },
                "filters": {
                    "type": "object",
                    "description": "Advanced filter parameters sent in the request body. All filters are nested in this object. Supports: lead_campaign_status (in_sequence, sequence_finished, sequence_stopped, never_contacted, replied), emails_sent (object with criteria: =, >=, >, <=, < and value), opens (object with criteria and value), replies (object with criteria and value), verification_statuses (array: verifying, verified, risky, unknown, unverified, inactive, bounced, unsubscribed), tag_ids (array of integers), excluded_tag_ids (array of integers), without_tags (boolean), created_at (object with criteria and value in YYYY-MM-DD format), updated_at (object with criteria and value in YYYY-MM-DD format). See document:emailbison/filters for complete details and examples.",
                    "additionalProperties": True,
                },
            },
            "additionalProperties": False,
        },
        outputSchema={
            "type": "object",
            "properties": {
                "data": {"type": "array"},
                "page": {"type": "integer"},
                "perPage": {"type": "integer"},
                "total": {"type": "integer"},
            },
            "required": ["data", "page", "perPage", "total"],
        },
    ),
    types.Tool(
        name="L_Unsubscribe_Lead",
        title="L. Unsubscribe Lead",
        description="Unsubscribe a lead from scheduled emails. This will stop all future scheduled emails from being sent to this lead. Returns the updated lead object with status set to 'unsubscribed' and all lead details including contact information, custom variables, campaign data, and statistics.",
        inputSchema={
            "type": "object",
            "properties": {
                "lead_id": {
                    "type": "integer",
                    "description": "The ID of the lead to unsubscribe.",
                },
            },
            "required": ["lead_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="L_Update_Lead",
        title="L. Update Lead",
        description="Update the details of a specific lead by its ID or email address. Fields and custom variables not passed in the request will remain unchanged. Returns the updated lead with all details including contact information, status, custom variables, campaign data, and statistics.",
        inputSchema={
            "type": "object",
            "properties": {
                "lead_id": {
                    "type": "string",
                    "description": "The ID (integer) or email address (string) of the lead to update.",
                },
                "email": {
                    "type": "string",
                    "format": "email",
                    "description": "The email address of the contact. Must be in a valid email format.",
                },
                "first_name": {
                    "type": "string",
                    "description": "The first name of the contact.",
                },
                "last_name": {
                    "type": "string",
                    "description": "The last name of the contact.",
                },
                "company": {
                    "type": "string",
                    "description": "The company name of the contact.",
                },
                "title": {
                    "type": "string",
                    "description": "The title of the contact.",
                },
                "notes": {
                    "type": "string",
                    "description": "Additional notes about the contact.",
                },
                "custom_variables": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the custom variable. Use list_custom_variables to see available custom variables.",
                            },
                            "value": {
                                "type": "string",
                                "description": "Value for the custom variable.",
                            },
                        },
                        "required": ["name", "value"],
                        "additionalProperties": False,
                    },
                    "description": "Array of custom variable objects. Each object should have 'name' and 'value' properties. Fields and custom variables not passed will remain unchanged.",
                },
            },
            "required": ["lead_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="R_Compose_New_Email",
        title="R. Compose New Email",
        description=(
            "Send a one-off email in a new email thread. This creates a new email conversation (not a reply to an existing thread). "
            "🚨 REQUIRED FIRST STEP: You MUST first call M_List_Sender_Emails to get the sender_email_id. "
            "Returns the sent reply object with full details including ID, subject, message content, recipients, and attachments."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "sender_email_id": {
                    "type": "integer",
                    "description": "ID of the sender email account to send from. Use get_campaign_sender_emails or list_sender_emails to get available sender email IDs.",
                },
                "to_emails": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Recipient's name."},
                            "email_address": {
                                "type": "string",
                                "format": "email",
                                "description": "Recipient's email address.",
                            },
                        },
                        "required": ["email_address"],
                        "additionalProperties": False,
                    },
                    "description": "Array of recipients to send the email to. Each recipient should have 'name' (optional) and 'email_address' (required).",
                },
                "subject": {
                    "type": "string",
                    "description": "Subject line of the email.",
                },
                "message": {
                    "type": "string",
                    "description": "The body/content of the email message.",
                },
                "content_type": {
                    "type": "string",
                    "enum": ["html", "text"],
                    "description": "Type of the email content. Use 'html' for HTML emails or 'text' for plain text emails.",
                },
                "cc_emails": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "CC recipient's name."},
                            "email_address": {
                                "type": "string",
                                "format": "email",
                                "description": "CC recipient's email address.",
                            },
                        },
                        "required": ["email_address"],
                        "additionalProperties": False,
                    },
                    "description": "Array of CC recipients. Each recipient should have 'name' (optional) and 'email_address' (required).",
                },
                "bcc_emails": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "BCC recipient's name."},
                            "email_address": {
                                "type": "string",
                                "format": "email",
                                "description": "BCC recipient's email address.",
                            },
                        },
                        "required": ["email_address"],
                        "additionalProperties": False,
                    },
                    "description": "Array of BCC recipients. Each recipient should have 'name' (optional) and 'email_address' (required).",
                },
                "attachments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Array of file attachments. Combined max size: 25MB, individual max size: 10MB. Note: If sending attachments, the request must use multipart/form-data (this is handled automatically by the API).",
                },
                "use_dedicated_ips": {
                    "type": "boolean",
                    "description": "Send using dedicated campaign IPs instead of the instance IP.",
                },
            },
            "required": ["sender_email_id", "to_emails"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="R_Create_Reply",
        title="R. Create Reply",
        description=(
            "Reply to an existing email thread. This creates a reply to a specific email conversation. "
            "🚨 REQUIRED FIRST STEP: You MUST first call M_List_Sender_Emails to get the sender_email_id. "
            "Returns the sent reply object with full details including ID, subject, message content, recipients, and attachments."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "reply_id": {
                    "type": "integer",
                    "description": "ID of the parent reply to reply to. Use get_reply or list_replies to find the reply ID.",
                },
                "sender_email_id": {
                    "type": "integer",
                    "description": "ID of the sender email account to send from. Use get_campaign_sender_emails or list_sender_emails to get available sender email IDs.",
                },
                "to_emails": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Recipient's name."},
                            "email_address": {
                                "type": "string",
                                "format": "email",
                                "description": "Recipient's email address.",
                            },
                        },
                        "required": ["email_address"],
                        "additionalProperties": False,
                    },
                    "description": "Array of recipients to send the reply to. Each recipient should have 'name' (optional) and 'email_address' (required).",
                },
                "message": {
                    "type": "string",
                    "description": "The body/content of the reply message.",
                },
                "content_type": {
                    "type": "string",
                    "enum": ["html", "text"],
                    "description": "Type of the email content. Use 'html' for HTML emails or 'text' for plain text emails.",
                },
                "cc_emails": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "CC recipient's name."},
                            "email_address": {
                                "type": "string",
                                "format": "email",
                                "description": "CC recipient's email address.",
                            },
                        },
                        "required": ["email_address"],
                        "additionalProperties": False,
                    },
                    "description": "Array of CC recipients. Each recipient should have 'name' (optional) and 'email_address' (required).",
                },
                "bcc_emails": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "BCC recipient's name."},
                            "email_address": {
                                "type": "string",
                                "format": "email",
                                "description": "BCC recipient's email address.",
                            },
                        },
                        "required": ["email_address"],
                        "additionalProperties": False,
                    },
                    "description": "Array of BCC recipients. Each recipient should have 'name' (optional) and 'email_address' (required).",
                },
                "attachments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Array of file attachments. Combined max size: 25MB, individual max size: 10MB. Note: If sending attachments, the request must use multipart/form-data (this is handled automatically by the API).",
                },
                "inject_previous_email_body": {
                    "type": "boolean",
                    "description": "Whether to inject the body of the previous email into this reply. If not specified, defaults to false.",
                },
                "use_dedicated_ips": {
                    "type": "boolean",
                    "description": "Send using dedicated campaign IPs instead of the instance IP.",
                },
            },
            "required": ["reply_id", "sender_email_id", "to_emails"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="R_Get_Lead_Replies",
        title="R. Get Lead Replies",
        description="Retrieve all replies for a specific lead. Returns an array of reply objects with comprehensive information including reply ID, UUID, folder, subject, read status, interested flag, automated reply flag, HTML and text body, date received, type, tracked status, associated campaign and lead IDs, sender email ID, message details, and attachments. Supports filtering by search, status, folder, read status, campaign, sender email, and tags.",
        inputSchema={
            "type": "object",
            "properties": {
                "lead_id": {
                    "type": "string",
                    "description": "The ID (integer) or email address (string) of the lead to retrieve replies for.",
                },
                "search": {
                    "type": "string",
                    "description": "Search term for filtering replies.",
                },
                "status": {
                    "type": "string",
                    "enum": ["interested", "automated_reply", "not_automated_reply"],
                    "description": "Filter by status.",
                },
                "folder": {
                    "type": "string",
                    "enum": ["inbox", "sent", "spam", "bounced", "all"],
                    "description": "Filter by folder.",
                },
                "read": {
                    "type": "boolean",
                    "description": "Filter by read status.",
                },
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to filter by.",
                },
                "sender_email_id": {
                    "type": "integer",
                    "description": "ID of the sender email address to filter by.",
                },
                "tag_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of tag IDs to filter by. Use list_tags to get tag IDs.",
                },
            },
            "required": ["lead_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="R_Get_Reply",
        title="R. Get Reply",
        description="Retrieve a specific reply by its ID. Returns comprehensive information including reply ID, UUID, folder, subject, read status, interested flag, automated reply flag, HTML and text body, raw body, headers, date received, type, tracked status, associated campaign and lead IDs, sender email ID, message details (from name, email address, to addresses, CC, BCC), parent ID, and attachments with download URLs.",
        inputSchema={
            "type": "object",
            "properties": {
                "reply_id": {
                    "type": "integer",
                    "description": "ID of the reply to retrieve.",
                },
            },
            "required": ["reply_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="R_List_Replies",
        title="R. List Replies",
        description="Retrieve all replies for the authenticated user across all campaigns. Returns paginated results (15 per page by default). IMPORTANT: All filter parameters (search, status, folder, read, campaign_id, sender_email_id, lead_id, tag_ids) are sent in the request body. CRITICAL: This endpoint ALWAYS returns paginated results. You MUST check the response for 'links.next' or 'meta.last_page' to determine if there are more pages. If the user asks for 'all replies' or multiple results, you MUST fetch all pages. Always use pagination - never assume the first page contains all results.",
        inputSchema={
            "type": "object",
            "properties": {
                "page": {
                    "type": "integer",
                    "description": "Page number to retrieve (default: 1). Use pagination to fetch all data.",
                    "default": 1,
                },
                "per_page": {
                    "type": "integer",
                    "description": "Number of results per page (default: 15).",
                    "default": 15,
                },
                "search": {
                    "type": "string",
                    "description": "Search term for filtering replies.",
                },
                "status": {
                    "type": "string",
                    "enum": ["interested", "automated_reply", "not_automated_reply"],
                    "description": "Filter by status.",
                },
                "folder": {
                    "type": "string",
                    "enum": ["inbox", "sent", "spam", "bounced", "all"],
                    "description": "Filter by folder.",
                },
                "read": {
                    "type": "boolean",
                    "description": "Filter by read status.",
                },
                "campaign_id": {
                    "type": "integer",
                    "description": "ID of the campaign to filter by (optional).",
                },
                "sender_email_id": {
                    "type": "integer",
                    "description": "ID of the sender email address to filter by.",
                },
                "lead_id": {
                    "type": "integer",
                    "description": "ID of a lead to filter by.",
                },
                "tag_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of tag IDs to filter by. Use list_tags to get tag IDs.",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="M_Disable_Warmup_For_Sender_Emails",
        title="M. Disable Warmup For Sender Emails",
        description="Disable warmup for selected email accounts. This operation disables the warmup process for all specified sender email IDs. Warmup emails will slowly ramp down over a period of 24 hours. Returns a success message indicating that warmup is being disabled. Note: This operation can take a few minutes if the list of email accounts is long.",
        inputSchema={
            "type": "object",
            "properties": {
                "sender_email_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of sender email IDs to disable warmup for. Use list_sender_emails to get sender email IDs.",
                },
            },
            "required": ["sender_email_ids"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="M_Enable_Warmup_For_Sender_Emails",
        title="M. Enable Warmup For Sender Emails",
        description="Enable warmup for selected email accounts. This operation enables the warmup process for all specified sender email IDs. The warmup process helps improve email deliverability by gradually increasing sending volume. Returns a success message indicating that warmup is being enabled. Note: This operation can take a few minutes if the list of email accounts is long.",
        inputSchema={
            "type": "object",
            "properties": {
                "sender_email_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of sender email IDs to enable warmup for. Use list_sender_emails to get sender email IDs.",
                },
            },
            "required": ["sender_email_ids"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="M_Get_Sender_Email_With_Warmup_Details",
        title="M. Get Sender Email With Warmup Details",
        description="Retrieve a single email account (sender email) with its warmup details. Returns comprehensive information including email account details (ID, email, name, domain, tags) and warmup metrics (warmup_emails_sent, warmup_replies_received, warmup_emails_saved_from_spam, warmup_score, warmup_bounces_received_count, warmup_bounces_caused_count, warmup_disabled_for_bouncing_count) for the specified date range.",
        inputSchema={
            "type": "object",
            "properties": {
                "sender_email_id": {
                    "type": "string",
                    "description": "The ID (integer) or email address (string) of the email account to retrieve warmup details for.",
                },
                "start_date": {
                    "type": "string",
                    "description": "The start date to fetch warmup stats (format: YYYY-MM-DD).",
                },
                "end_date": {
                    "type": "string",
                    "description": "The end date to fetch warmup stats (format: YYYY-MM-DD).",
                },
            },
            "required": ["sender_email_id", "start_date", "end_date"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="M_List_Sender_Emails",
        title="M. List Sender Emails",
        description=(
            "🚨 REQUIRED FIRST STEP: Retrieve all email accounts (sender emails) associated with the authenticated workspace. "
            "MUST be called before using any sender_email_id in other operations. "
            "Returns detailed information including name, email address, email signature, IMAP/SMTP settings, daily limits, type, status, statistics (emails sent, replies, opens, bounces, etc.), and associated tags. "
            "Supports filtering by search term, tag IDs, excluded tag IDs, and accounts without tags. "
            "If filtering by tags, you MUST first call T_List_Tags to get tag IDs (not names)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "Search term for filtering email accounts.",
                },
                "tag_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of tag IDs to filter by. Use list_tags to get tag IDs.",
                },
                "excluded_tag_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of tag IDs to exclude. Email accounts with these tags will be filtered out.",
                },
                "without_tags": {
                    "type": "boolean",
                    "description": "Only show email accounts that have no tags attached.",
                },
                "filters": {
                    "type": "object",
                    "description": "Additional filter parameters sent in the request body. All filters are nested in this object. Supports excluded_tag_ids (array of integers) and without_tags (boolean). See document:emailbison/filters for complete filter options and examples.",
                    "properties": {
                        "excluded_tag_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Exclude email accounts by tag IDs. Use list_tags to get tag IDs.",
                        },
                        "without_tags": {
                            "type": "boolean",
                            "description": "Only show email accounts that have no tags attached.",
                        },
                    },
                },
            },
            "required": [],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="M_List_Sender_Emails_With_Warmup_Stats",
        title="M. List Sender Emails With Warmup Stats",
        description="Retrieve all email accounts (sender emails) associated with the authenticated workspace, along with their warmup statistics. Returns detailed information including email account details (ID, email, name, domain, tags) and warmup metrics (warmup_emails_sent, warmup_replies_received, warmup_emails_saved_from_spam, warmup_score, warmup_bounces_received_count, warmup_bounces_caused_count, warmup_disabled_for_bouncing_count). Requires start_date and end_date parameters to fetch stats for a specific date range. Supports filtering by search term, tag IDs, excluded tag IDs, accounts without tags, warmup status (enabled/disabled), and MX records status (records missing/records valid).",
        inputSchema={
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "The start date to fetch warmup stats (format: YYYY-MM-DD). Defaults to 10 days ago if not provided.",
                },
                "end_date": {
                    "type": "string",
                    "description": "The end date to fetch warmup stats (format: YYYY-MM-DD). Defaults to today if not provided.",
                },
                "search": {
                    "type": "string",
                    "description": "Search term for filtering email accounts.",
                },
                "tag_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of tag IDs to filter by. Use list_tags to get tag IDs.",
                },
                "excluded_tag_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of tag IDs to exclude. Email accounts with these tags will be filtered out.",
                },
                "without_tags": {
                    "type": "boolean",
                    "description": "Only show email accounts that have no tags attached.",
                },
                "warmup_status": {
                    "type": "string",
                    "enum": ["enabled", "disabled"],
                    "description": "Filter by warmup status. Valid values: enabled, disabled.",
                },
                "mx_records_status": {
                    "type": "string",
                    "enum": ["records missing", "records valid"],
                    "description": "Filter by MX records status. Valid values: records missing, records valid.",
                },
                "filters": {
                    "type": "object",
                    "description": "Additional filter parameters sent in the request body. All filters are nested in this object. Supports excluded_tag_ids (array of integers) and without_tags (boolean). See document:emailbison/filters for complete filter options and examples.",
                    "properties": {
                        "excluded_tag_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Exclude email accounts by tag IDs. Use list_tags to get tag IDs.",
                        },
                        "without_tags": {
                            "type": "boolean",
                            "description": "Only show email accounts that have no tags attached.",
                        },
                    },
                },
            },
            "required": ["start_date", "end_date"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="M_Send_Email",
        title="M. Send Email",
        description=(
            "Send a single ad-hoc email from a sender account. "
            "🚨 REQUIRED FIRST STEP: You MUST first call M_List_Sender_Emails to get the email_account_id."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "email_account_id": {"type": "string", "description": "Sender email account ID to use."},
                "to": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Primary recipients' email addresses.",
                },
                "subject": {"type": "string", "description": "Email subject."},
                "html_body": {"type": "string", "description": "Email HTML body."},
                "cc": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional CC recipients.",
                },
                "bcc": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional BCC recipients.",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tags to associate with the send.",
                },
            },
            "required": ["email_account_id", "to", "subject", "html_body"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="M_Update_Daily_Warmup_Limits",
        title="M. Update Daily Warmup Limits",
        description="Update daily warmup limits for selected email accounts. This operation sets the daily limit of warmup emails to send for the specified sender email IDs. Optionally, you can also set the daily reply limit (can be set to 'auto' string). WARNING: You should only use the daily_reply_limit parameter if explicitly told by your inbox reseller. We cannot be held responsible if you experience low inbox health as a result of controlling your own reply rate. Returns a success message indicating that the daily warmup limits have been updated.",
        inputSchema={
            "type": "object",
            "properties": {
                "sender_email_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of sender email IDs to update daily warmup limits for. Use list_sender_emails to get sender email IDs.",
                },
                "daily_limit": {
                    "type": "integer",
                    "description": "The daily limit of warmup emails to send.",
                },
                "daily_reply_limit": {
                    "type": "string",
                    "description": "The daily limit of warmup reply emails. You can pass 'auto' string to set this to auto. WARNING: You should only use this parameter if explicitly told by your inbox reseller. We cannot be held responsible if you experience low inbox health as a result of controlling your own reply rate.",
                },
            },
            "required": ["sender_email_ids", "daily_limit"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="W_Create_Custom_Variable",
        title="W. Create Custom Variable",
        description="Create a new custom variable for the workspace. Returns the created custom variable with ID, name, and timestamps. Custom variables can be used in email templates and lead data.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the custom variable to create.",
                },
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="W_Create_Workspace",
        title="W. Create Workspace",
        description="Create a new workspace for the authenticated user. Returns the created workspace object with comprehensive information including workspace ID, name, personal_team flag, main flag, parent_id, email verification credits (total monthly, remaining monthly, remaining, total), sender email limit, warmup limit, warmup filter phrase, sender email limit disabled flag, access flags (has_access_to_warmup, has_access_to_healthcheck), and timestamps (created_at, updated_at).",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the new workspace.",
                },
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="W_Get_Account_Details",
        title="W. Get Account Details",
        description="Retrieve information about the authenticated EmailBison user and workspace limits.",
        inputSchema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="W_Get_Workspace_Details",
        title="W. Get Workspace Details",
        description=(
            "Retrieve the details of a specific workspace for the authenticated user. "
            "🚨 REQUIRED FIRST STEP: You MUST first call W_List_Workspaces to find the workspace and get its team_id. "
            "Returns comprehensive information including workspace ID, name, personal_team flag, main flag, parent_id, email verification credits (total monthly, remaining monthly, remaining, total), sender email limit, warmup limit, warmup filter phrase, sender email limit disabled flag, access flags (has_access_to_warmup, has_access_to_healthcheck), and timestamps (created_at, updated_at)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "team_id": {
                    "type": "integer",
                    "description": "The ID of the team (workspace) to retrieve details for. Use list_workspaces to get available workspace IDs.",
                },
            },
            "required": ["team_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="W_Get_Workspace_Line_Area_Chart_Stats",
        title="W. Get Workspace Line Area Chart Stats",
        description="Retrieve full normalized stats by date for a given period for the authenticated user's workspace. Returns time-series data for events: Replied, Total Opens, Unique Opens, Sent, Bounced, Unsubscribed, and Interested. Each event includes a label, color, and dates array containing date-value pairs (format: [\"YYYY-MM-DD\", value]) for charting. Requires start_date and end_date parameters to specify the date range for the statistics.",
        inputSchema={
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "The start date to fetch stats (format: YYYY-MM-DD).",
                },
                "end_date": {
                    "type": "string",
                    "description": "The end date to fetch stats (format: YYYY-MM-DD).",
                },
            },
            "required": ["start_date", "end_date"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="W_Get_Workspace_Stats",
        title="W. Get Workspace Stats",
        description="Retrieve overall statistics for the authenticated user's workspace between two given dates. Returns comprehensive metrics including emails_sent, total_leads_contacted, opened (count and percentage), unique_opens_per_contact (count and percentage), unique_replies_per_contact (count and percentage), bounced (count and percentage), unsubscribed (count and percentage), and interested (count and percentage). Requires start_date and end_date parameters to specify the date range for the statistics.",
        inputSchema={
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "The start date to fetch stats (format: YYYY-MM-DD).",
                },
                "end_date": {
                    "type": "string",
                    "description": "The end date to fetch stats (format: YYYY-MM-DD).",
                },
            },
            "required": ["start_date", "end_date"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="W_Invite_Team_Member",
        title="W. Invite Team Member",
        description="Invite a new member to the authenticated user's team (workspace). Requires the email address and role of the new team member. Returns the created team member invitation object with ID, UUID, workspace_id, email, role, and timestamps (created_at, updated_at).",
        inputSchema={
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "The email address of the new team member to invite.",
                },
                "role": {
                    "type": "string",
                    "description": "The role of the new team member (e.g., 'admin', 'member', etc.).",
                },
            },
            "required": ["email", "role"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="W_List_Custom_Variables",
        title="W. List Custom Variables",
        description="Retrieve all custom variables for the authenticated workspace. Returns a list of custom variables with their IDs, names, and timestamps. Custom variables can be used in email templates and lead data.",
        inputSchema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="W_List_Workspaces",
        title="W. List Workspaces",
        description=(
            "🚨 IMPORTANT: This tool lists workspaces for the CURRENT client's API key. "
            "If you need to access a DIFFERENT workspace, use the `client_name` parameter in other tools instead of switching workspaces. "
            "This tool is only needed for workspace management within a single account. "
            "Retrieve all workspaces for the authenticated user. "
            "Returns an array of workspace objects with comprehensive information including workspace ID (team_id), name, personal_team flag, main flag, parent_id, email verification credits (total monthly, remaining monthly, remaining, total), sender email limit, warmup limit, warmup filter phrase, sender email limit disabled flag, access flags (has_access_to_warmup, has_access_to_healthcheck), and timestamps (created_at, updated_at)."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="W_Switch_Workspace",
        title="W. Switch Workspace",
        description=(
            "🚨 IMPORTANT: DO NOT use this tool to access different workspaces when using multi-account mode. "
            "Instead, use the `client_name` parameter in other tools (e.g., `client_name=\"ATI\"` or `client_name=\"LongRun\"`). "
            "This tool is only for switching workspaces within a single account's API key context. "
            "Switch to a different workspace for the authenticated user. This operation changes the active workspace context. "
            "🚨 REQUIRED FIRST STEP: You MUST first call W_List_Workspaces to find the workspace and get its team_id. "
            "Returns the name of the workspace that was switched to."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "team_id": {
                    "type": "integer",
                    "description": "The ID of the team (workspace) to switch to. Use list_workspaces to get available workspace IDs.",
                },
            },
            "required": ["team_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="W_Update_Workspace",
        title="W. Update Workspace",
        description=(
            "Update workspace information for the authenticated user, specifically the workspace name. "
            "🚨 REQUIRED FIRST STEP: You MUST first call W_List_Workspaces to find the workspace and get its team_id. "
            "Returns the updated workspace name."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "team_id": {
                    "type": "integer",
                    "description": "The ID of the team (workspace) to update. Use list_workspaces to get available workspace IDs.",
                },
                "name": {
                    "type": "string",
                    "description": "The new workspace name.",
                },
            },
            "required": ["team_id", "name"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="T_Attach_Tags_To_Campaigns",
        title="T. Attach Tags To Campaigns",
        description="Attach multiple tags to multiple campaigns in a single operation. Returns a success message confirming the tags were attached. Use list_tags to get tag IDs and list_campaigns to get campaign IDs.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of campaign IDs to attach tags to. Use list_campaigns to get campaign IDs.",
                },
                "tag_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of tag IDs to attach. Use list_tags to get tag IDs.",
                },
                "skip_webhooks": {
                    "type": "boolean",
                    "description": "If set to true, no webhooks will be fired for this action.",
                },
            },
            "required": ["campaign_ids", "tag_ids"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="T_Attach_Tags_To_Leads",
        title="T. Attach Tags To Leads",
        description="Attach multiple tags to multiple leads in a single operation. Returns a success message confirming the tags were attached. Use list_tags to get tag IDs and list_leads to get lead IDs.",
        inputSchema={
            "type": "object",
            "properties": {
                "lead_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of lead IDs to attach tags to. Use list_leads to get lead IDs.",
                },
                "tag_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of tag IDs to attach. Use list_tags to get tag IDs.",
                },
                "skip_webhooks": {
                    "type": "boolean",
                    "description": "If set to true, no webhooks will be fired for this action.",
                },
            },
            "required": ["lead_ids", "tag_ids"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="T_Attach_Tags_To_Sender_Emails",
        title="T. Attach Tags To Sender Emails",
        description="Attach multiple tags to multiple email accounts (sender emails) in a single operation. Returns a success message confirming the tags were attached. Use list_tags to get tag IDs and list_sender_emails to get sender email IDs.",
        inputSchema={
            "type": "object",
            "properties": {
                "sender_email_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of sender email IDs to attach tags to. Use list_sender_emails to get sender email IDs.",
                },
                "tag_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of tag IDs to attach. Use list_tags to get tag IDs.",
                },
                "skip_webhooks": {
                    "type": "boolean",
                    "description": "If set to true, no webhooks will be fired for this action.",
                },
            },
            "required": ["sender_email_ids", "tag_ids"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="T_Create_Tag",
        title="T. Create Tag",
        description="Create a new tag in the workspace. Returns the created tag with ID, name, default status, and timestamps.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the tag to create.",
                },
                "default": {
                    "type": "boolean",
                    "description": "Whether the tag should be marked as default. If not specified, defaults to false.",
                },
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="T_Delete_Tag",
        title="T. Delete Tag",
        description="Delete a tag by its ID. Returns a success message confirming the tag was removed. Use with caution as this action cannot be undone.",
        inputSchema={
            "type": "object",
            "properties": {
                "tag_id": {
                    "type": "integer",
                    "description": "ID of the tag to delete.",
                },
            },
            "required": ["tag_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="T_Get_Tag",
        title="T. Get Tag",
        description="Retrieve a specific tag by its ID. Returns tag details including ID, name, default status, and timestamps (created_at, updated_at).",
        inputSchema={
            "type": "object",
            "properties": {
                "tag_id": {
                    "type": "integer",
                    "description": "ID of the tag to retrieve.",
                },
            },
            "required": ["tag_id"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="T_List_Tags",
        title="T. List Tags",
        description=(
            "🚨 REQUIRED FIRST STEP: Retrieve all tags in the current workspace. "
            "MUST be called before filtering leads, campaigns, or sender emails by tags. "
            "Returns tag IDs that are required for filtering (the API does not accept tag names). "
            "Use the returned tag IDs in tag_ids parameters when filtering."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="T_Remove_Tags_From_Campaigns",
        title="T. Remove Tags From Campaigns",
        description="Detach multiple tags from multiple campaigns in a single operation. Returns a success message confirming the tags were removed. Use list_tags to get tag IDs and list_campaigns to get campaign IDs.",
        inputSchema={
            "type": "object",
            "properties": {
                "campaign_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of campaign IDs to remove tags from. Use list_campaigns to get campaign IDs.",
                },
                "tag_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of tag IDs to remove. Use list_tags to get tag IDs.",
                },
                "skip_webhooks": {
                    "type": "boolean",
                    "description": "If set to true, no webhooks will be fired for this action.",
                },
            },
            "required": ["campaign_ids", "tag_ids"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="T_Remove_Tags_From_Leads",
        title="T. Remove Tags From Leads",
        description="Detach multiple tags from multiple leads in a single operation. Returns a success message confirming the tags were removed. Use list_tags to get tag IDs and list_leads to get lead IDs.",
        inputSchema={
            "type": "object",
            "properties": {
                "lead_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of lead IDs to remove tags from. Use list_leads to get lead IDs.",
                },
                "tag_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of tag IDs to remove. Use list_tags to get tag IDs.",
                },
                "skip_webhooks": {
                    "type": "boolean",
                    "description": "If set to true, no webhooks will be fired for this action.",
                },
            },
            "required": ["lead_ids", "tag_ids"],
            "additionalProperties": False,
        },
    ),
    types.Tool(
        name="T_Remove_Tags_From_Sender_Emails",
        title="T. Remove Tags From Sender Emails",
        description="Detach multiple tags from multiple email accounts (sender emails) in a single operation. Returns a success message confirming the tags were removed. Use list_tags to get tag IDs and list_sender_emails to get sender email IDs.",
        inputSchema={
            "type": "object",
            "properties": {
                "sender_email_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of sender email IDs to remove tags from. Use list_sender_emails to get sender email IDs.",
                },
                "tag_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Array of tag IDs to remove. Use list_tags to get tag IDs.",
                },
                "skip_webhooks": {
                    "type": "boolean",
                    "description": "If set to true, no webhooks will be fired for this action.",
                },
            },
            "required": ["sender_email_ids", "tag_ids"],
            "additionalProperties": False,
        },
    )
]


def _add_client_name_to_tool_schemas(tools: list[types.Tool]) -> None:
    """Add client_name parameter to all tool input schemas."""
    client_name_property = {
        "client_name": {
            "type": "string",
            "description": (
                "Name of the client/account to use. If not provided, uses the default client from config. "
                "Available client names include: ATI, LongRun, COXIT, Chateau, Cloud Avengers, Dextego, "
                "GearLocker, Milengo, Retail Grid, Roundabout, Skyline, Talantir, Trays4Us, Workspark, "
                "and Super-admin. If you specify an invalid client name, the error message will list all available clients."
            ),
        }
    }
    
    for tool in tools:
        if tool.inputSchema and isinstance(tool.inputSchema, dict):
            properties = tool.inputSchema.get("properties", {})
            if isinstance(properties, dict):
                # Add client_name property
                properties.update(client_name_property)
                # Note: client_name is optional, so we don't add it to required list


# Add client_name parameter to all tool definitions
_add_client_name_to_tool_schemas(TOOL_DEFINITIONS)


@server.list_tools()
async def list_tools(_req: types.ListToolsRequest | None = None) -> types.ListToolsResult:
    return types.ListToolsResult(tools=TOOL_DEFINITIONS)


@server.list_resources()
async def list_resources(_req: types.ListResourcesRequest | None = None) -> types.ListResourcesResult:
    resources = [
        types.Resource(
            name=info["name"],
            uri=info["uri"],
            description=info["description"],
            mimeType=info["mime_type"],
            title=info["title"],
        )
        for info in RESOURCE_DEFINITIONS.values()
    ]
    return types.ListResourcesResult(resources=resources)


@server.read_resource()
async def read_resource(uri: str):
    info = RESOURCE_DEFINITIONS_BY_URI.get(str(uri))
    if not info:
        raise ValueError(f"Unknown resource URI: {uri}")
    return [
        types.TextResourceContents(
            uri=info["uri"],
            text=info["content"],
            mimeType=info["mime_type"],
        )
    ]


@server.list_prompts()
async def list_prompts(_req: types.ListPromptsRequest | None = None) -> types.ListPromptsResult:
    return types.ListPromptsResult(prompts=list(PROMPT_DEFINITIONS.values()))


@server.get_prompt()
async def get_prompt(name: str, arguments: dict[str, str] | None = None) -> types.GetPromptResult:
    prompt = PROMPT_DEFINITIONS.get(name)
    if not prompt:
        raise ValueError(f"Prompt '{name}' not found.")
    return types.GetPromptResult(prompt=prompt)


def _require(arguments: dict[str, Any], key: str) -> Any:
    value = arguments.get(key)
    if value in (None, "", [], {}):
        raise ValueError(f"Missing required argument '{key}'.")
    return value


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def _get_client_manager() -> ClientManager:
    """Get the ClientManager instance."""
    client_manager = getattr(server, "client_manager", None)  # type: ignore[attr-defined]
    if client_manager is None:
        raise RuntimeError("ClientManager not initialised.")
    return client_manager


def _get_client_for_account(client_name: str | None = None) -> EmailBisonClient:
    """Get EmailBisonClient for a specific account."""
    client_manager = _get_client_manager()
    try:
        return client_manager.get_or_create_client(client_name)
    except ClientManagerError as e:
        # Enhance error message with available clients if client not found
        available = client_manager.list_clients()
        error_msg = str(e)
        if "not found" in error_msg.lower() and available:
            error_msg += f"\n\nAvailable client names: {', '.join(available)}"
        raise ValueError(error_msg) from e


def _client() -> EmailBisonClient:
    """Get the default EmailBisonClient (for backward compatibility)."""
    return _get_client_for_account(None)


def _extract_filters(arguments: Mapping[str, Any], *, exclude: Iterable[str] = ()) -> dict[str, Any]:
    candidate = arguments.get("filters")
    if not candidate:
        return {}
    if not isinstance(candidate, Mapping):
        raise ValueError("filters must be provided as an object.")
    excluded = set(exclude)
    filtered: dict[str, Any] = {}
    for key, value in candidate.items():
        if key in excluded:
            continue
        if value in (None, "", [], {}):
            continue
        filtered[str(key)] = value
    return filtered


def _flatten_filters(filters: dict[str, Any], prefix: str = "filters") -> dict[str, Any]:
    """Flatten nested filter dict to dot notation keys (e.g., filters.lead_campaign_status). DEPRECATED: Filters are now sent as nested objects in the request body, not flattened."""
    flattened: dict[str, Any] = {}
    for key, value in filters.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            # Recursively flatten nested dicts
            nested = _flatten_filters(value, full_key)
            flattened.update(nested)
        elif isinstance(value, list):
            # For arrays, keep as-is (httpx will handle repeating them)
            flattened[full_key] = value
        else:
            flattened[full_key] = value
    return flattened


def _pagination_reminder(payload: dict[str, Any]) -> str:
    """Generate a pagination reminder message based on the response payload."""
    links = payload.get("links", {})
    meta = payload.get("meta", {})
    
    # Handle different response structures
    current_page = meta.get("current_page") or payload.get("page") or 1
    last_page = meta.get("last_page") or 1
    total = meta.get("total") or payload.get("total") or 0
    per_page = meta.get("per_page") or payload.get("per_page") or payload.get("perPage") or 15
    
    # Calculate last_page from total if not provided
    if last_page == 1 and total > 0 and per_page > 0:
        last_page = (total + per_page - 1) // per_page  # Ceiling division
    
    data_count = len(payload.get("data", []))
    
    reminder_parts = [
        f"\n\n⚠️ PAGINATION REMINDER:",
        f"- Current page: {current_page} of {last_page}",
        f"- Results on this page: {data_count}",
        f"- Total results available: {total}",
        f"- Results per page: {per_page}",
    ]
    
    has_more = links.get("next") is not None or current_page < last_page
    
    if has_more:
        next_page = current_page + 1
        reminder_parts.append(
            f"- ⚠️ MORE PAGES AVAILABLE! There are {last_page - current_page} more page(s)."
        )
        reminder_parts.append(
            f"- ⚠️ To get all results, you MUST fetch pages {next_page} through {last_page} using the 'page' parameter."
        )
        reminder_parts.append(
            f"- ⚠️ Or use 'links.next' URL if available in the response."
        )
    else:
        reminder_parts.append("- ✓ This is the last page (no more results).")
    
    if current_page == 1 and last_page > 1:
        reminder_parts.append(
            f"\n🚨 CRITICAL ACTION REQUIRED: You are only seeing page 1 of {last_page} total pages. "
            f"There are {total} total results, but you're only seeing {data_count} on this page. "
            f"You MUST fetch additional pages (2 through {last_page}) to see all results!"
        )
        reminder_parts.append(
            f"\n📋 PAGINATION WORKFLOW:")
        reminder_parts.append(
            f"   1. You have fetched page {current_page} with {data_count} results"
        )
        reminder_parts.append(
            f"   2. There are {last_page - current_page} more pages to fetch"
        )
        reminder_parts.append(
            f"   3. To get all results, call this tool again with page=2, then page=3, etc. up to page={last_page}"
        )
        reminder_parts.append(
            f"   4. OR loop through pages: for page in range(2, {last_page + 1}): call tool with page=page"
        )
    elif current_page == 1 and total > data_count:
        reminder_parts.append(
            f"\n🚨 CRITICAL ACTION REQUIRED: There are {total} total results, but you're only seeing {data_count} on this page. "
            f"You MUST check for additional pages!"
        )
        reminder_parts.append(
            f"\n📋 NEXT STEPS:")
        reminder_parts.append(
            f"   1. Check if 'links.next' exists in the response - if yes, fetch that URL"
        )
        reminder_parts.append(
            f"   2. OR increment the 'page' parameter and fetch page 2, 3, etc. until no more results"
        )
    
    # Add explicit instruction for common use cases
    if current_page == 1 and has_more:
        reminder_parts.append(
            f"\n💡 EXAMPLE: If user asks for 'first 15 leads' or 'all leads with tag X':"
        )
        reminder_parts.append(
            f"   - You MUST fetch ALL pages, not just page 1"
        )
        reminder_parts.append(
            f"   - Start with page=1, then continue with page=2, page=3, etc. until you reach page={last_page}"
        )
        reminder_parts.append(
            f"   - Combine results from all pages to give the complete answer"
        )
    
    return "\n".join(reminder_parts)


@server.call_tool()
async def call_tool(tool_name: str, arguments: dict[str, Any]) -> types.CallToolResult | tuple[Any, Any]:
    # Extract client_name from arguments if provided (create copy to avoid modifying original)
    arguments_copy = dict(arguments)
    client_name = arguments_copy.pop("client_name", None)
    client = _get_client_for_account(client_name)
    # Use the copy (without client_name) for the rest of the function
    arguments = arguments_copy
    try:
        if tool_name == "L_List_Leads":
            filters = _extract_filters(arguments, exclude={"search", "status", "page", "per_page", "interested"})
            # If tag_ids is provided at top level, move it into filters
            if arguments.get("tag_ids") and (not filters or "tag_ids" not in filters):
                if not filters:
                    filters = {}
                filters["tag_ids"] = arguments.get("tag_ids")
            response = await client.list_leads(
                search=arguments.get("search"),
                status=arguments.get("status"),
                page=int(arguments.get("page") or 1),
                per_page=int(arguments.get("per_page") or 50),
                interested=arguments.get("interested"),
                filters=filters or None,
            )
            payload = response.model_dump(by_alias=True)
            pagination_reminder = _pagination_reminder(payload)
            response_text = _json(payload) + pagination_reminder
            return (
                [types.TextContent(type="text", text=response_text)],
                payload,
            )

        if tool_name == "L_Create_Lead":
            payload = await client.create_lead(
                email=str(_require(arguments, "email")),
                first_name=str(_require(arguments, "first_name")),
                last_name=str(_require(arguments, "last_name")),
                company=arguments.get("company"),
                title=arguments.get("title"),
                notes=arguments.get("notes"),
                custom_variables=arguments.get("custom_variables"),
                tags=arguments.get("tags"),
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "L_Get_Lead":
            lead_id = str(_require(arguments, "lead_id"))
            payload = await client.get_lead(lead_id)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "L_Update_Lead":
            lead_id = str(_require(arguments, "lead_id"))
            payload = await client.update_lead(
                lead_id,
                email=arguments.get("email"),
                first_name=arguments.get("first_name"),
                last_name=arguments.get("last_name"),
                company=arguments.get("company"),
                title=arguments.get("title"),
                notes=arguments.get("notes"),
                custom_variables=arguments.get("custom_variables"),
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "L_Unsubscribe_Lead":
            lead_id = int(_require(arguments, "lead_id"))
            payload = await client.unsubscribe_lead(lead_id)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "L_Bulk_Create_Leads_CSV":
            name = str(_require(arguments, "name"))
            csv_content = str(_require(arguments, "csv_content"))
            columns_to_map = _require(arguments, "columns_to_map")
            existing_lead_behavior = arguments.get("existing_lead_behavior")

            if not isinstance(columns_to_map, list):
                raise ValueError("columns_to_map must be a list")

            payload = await client.bulk_create_leads_csv(
                name=name,
                csv_content=csv_content,
                columns_to_map=columns_to_map,
                existing_lead_behavior=existing_lead_behavior,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_List_Campaigns":
            filters = _extract_filters(arguments, exclude={"search", "status", "page", "per_page"})
            # If tag_ids is provided at top level, move it into filters
            if arguments.get("tag_ids") and (not filters or "tag_ids" not in filters):
                if not filters:
                    filters = {}
                filters["tag_ids"] = arguments.get("tag_ids")
            payload = await client.list_campaigns(
                search=arguments.get("search"),
                status=arguments.get("status"),
                page=int(arguments.get("page") or 1),
                per_page=int(arguments.get("per_page") or 50),
                filters=filters or None,
            )
            pagination_reminder = _pagination_reminder(payload)
            response_text = _json(payload) + pagination_reminder
            return (
                [types.TextContent(type="text", text=response_text)],
                payload,
            )

        if tool_name == "C_Create_Campaign":
            payload = await client.create_campaign(
                name=str(_require(arguments, "name")),
                campaign_type=arguments.get("type"),
                additional_fields=arguments.get("additional_fields"),
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "M_Send_Email":
            payload = await client.send_email(
                email_account_id=str(_require(arguments, "email_account_id")),
                to=_as_list(_require(arguments, "to")),
                subject=str(_require(arguments, "subject")),
                html_body=str(_require(arguments, "html_body")),
                cc=_as_list(arguments.get("cc")) if arguments.get("cc") is not None else None,
                bcc=_as_list(arguments.get("bcc")) if arguments.get("bcc") is not None else None,
                tags=_as_list(arguments.get("tags")) if arguments.get("tags") is not None else None,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "W_Get_Account_Details":
            payload = await client.get_account_details()
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "T_List_Tags":
            payload = await client.list_tags()
            notice = (
                "Always use tag IDs when filtering leads. For example, supply `tag_ids: [<tag_id>]` instead of names."
            )
            return (
                [
                    types.TextContent(type="text", text=_json(payload)),
                    types.TextContent(type="text", text=notice),
                ],
                payload,
            )

        if tool_name == "W_List_Custom_Variables":
            payload = await client.list_custom_variables()
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "W_Create_Custom_Variable":
            name = str(_require(arguments, "name"))
            payload = await client.create_custom_variable(name=name)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "T_Create_Tag":
            name = str(_require(arguments, "name"))
            default = arguments.get("default")

            payload = await client.create_tag(name=name, default=default)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "T_Get_Tag":
            tag_id = int(_require(arguments, "tag_id"))
            payload = await client.get_tag(tag_id)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "T_Delete_Tag":
            tag_id = int(_require(arguments, "tag_id"))
            payload = await client.delete_tag(tag_id)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "T_Attach_Tags_To_Campaigns":
            campaign_ids = _require(arguments, "campaign_ids")
            tag_ids = _require(arguments, "tag_ids")
            skip_webhooks = arguments.get("skip_webhooks")

            if not isinstance(campaign_ids, list):
                raise ValueError("campaign_ids must be a list")
            if not isinstance(tag_ids, list):
                raise ValueError("tag_ids must be a list")

            # Convert to list of integers
            campaign_ids_list = [int(cid) for cid in campaign_ids]
            tag_ids_list = [int(tid) for tid in tag_ids]

            payload = await client.attach_tags_to_campaigns(
                campaign_ids=campaign_ids_list,
                tag_ids=tag_ids_list,
                skip_webhooks=skip_webhooks,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "T_Remove_Tags_From_Campaigns":
            campaign_ids = _require(arguments, "campaign_ids")
            tag_ids = _require(arguments, "tag_ids")
            skip_webhooks = arguments.get("skip_webhooks")

            if not isinstance(campaign_ids, list):
                raise ValueError("campaign_ids must be a list")
            if not isinstance(tag_ids, list):
                raise ValueError("tag_ids must be a list")

            # Convert to list of integers
            campaign_ids_list = [int(cid) for cid in campaign_ids]
            tag_ids_list = [int(tid) for tid in tag_ids]

            payload = await client.remove_tags_from_campaigns(
                campaign_ids=campaign_ids_list,
                tag_ids=tag_ids_list,
                skip_webhooks=skip_webhooks,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "T_Attach_Tags_To_Leads":
            lead_ids = _require(arguments, "lead_ids")
            tag_ids = _require(arguments, "tag_ids")
            skip_webhooks = arguments.get("skip_webhooks")

            if not isinstance(lead_ids, list):
                raise ValueError("lead_ids must be a list")
            if not isinstance(tag_ids, list):
                raise ValueError("tag_ids must be a list")

            # Convert to list of integers
            lead_ids_list = [int(lid) for lid in lead_ids]
            tag_ids_list = [int(tid) for tid in tag_ids]

            payload = await client.attach_tags_to_leads(
                lead_ids=lead_ids_list,
                tag_ids=tag_ids_list,
                skip_webhooks=skip_webhooks,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "T_Remove_Tags_From_Leads":
            lead_ids = _require(arguments, "lead_ids")
            tag_ids = _require(arguments, "tag_ids")
            skip_webhooks = arguments.get("skip_webhooks")

            if not isinstance(lead_ids, list):
                raise ValueError("lead_ids must be a list")
            if not isinstance(tag_ids, list):
                raise ValueError("tag_ids must be a list")

            # Convert to list of integers
            lead_ids_list = [int(lid) for lid in lead_ids]
            tag_ids_list = [int(tid) for tid in tag_ids]

            payload = await client.remove_tags_from_leads(
                lead_ids=lead_ids_list,
                tag_ids=tag_ids_list,
                skip_webhooks=skip_webhooks,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "T_Attach_Tags_To_Sender_Emails":
            sender_email_ids = _require(arguments, "sender_email_ids")
            tag_ids = _require(arguments, "tag_ids")
            skip_webhooks = arguments.get("skip_webhooks")

            if not isinstance(sender_email_ids, list):
                raise ValueError("sender_email_ids must be a list")
            if not isinstance(tag_ids, list):
                raise ValueError("tag_ids must be a list")

            # Convert to list of integers
            sender_email_ids_list = [int(sid) for sid in sender_email_ids]
            tag_ids_list = [int(tid) for tid in tag_ids]

            payload = await client.attach_tags_to_sender_emails(
                sender_email_ids=sender_email_ids_list,
                tag_ids=tag_ids_list,
                skip_webhooks=skip_webhooks,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "T_Remove_Tags_From_Sender_Emails":
            sender_email_ids = _require(arguments, "sender_email_ids")
            tag_ids = _require(arguments, "tag_ids")
            skip_webhooks = arguments.get("skip_webhooks")

            if not isinstance(sender_email_ids, list):
                raise ValueError("sender_email_ids must be a list")
            if not isinstance(tag_ids, list):
                raise ValueError("tag_ids must be a list")

            # Convert to list of integers
            sender_email_ids_list = [int(sid) for sid in sender_email_ids]
            tag_ids_list = [int(tid) for tid in tag_ids]

            payload = await client.remove_tags_from_sender_emails(
                sender_email_ids=sender_email_ids_list,
                tag_ids=tag_ids_list,
                skip_webhooks=skip_webhooks,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Duplicate_Campaign":
            campaign_id = int(_require(arguments, "campaign_id"))
            payload = await client.duplicate_campaign(campaign_id)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Pause_Campaign":
            campaign_id = int(_require(arguments, "campaign_id"))
            payload = await client.pause_campaign(campaign_id)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Resume_Campaign":
            campaign_id = int(_require(arguments, "campaign_id"))
            payload = await client.resume_campaign(campaign_id)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Archive_Campaign":
            campaign_id = int(_require(arguments, "campaign_id"))
            payload = await client.archive_campaign(campaign_id)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Update_Campaign_Settings":
            campaign_id = int(_require(arguments, "campaign_id"))
            updates = arguments.get("updates") or {}
            if not isinstance(updates, Mapping):
                raise ValueError("updates must be an object.")
            payload = await client.update_campaign_settings(campaign_id, updates=updates)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Create_Campaign_Schedule":
            campaign_id = int(_require(arguments, "campaign_id"))
            schedule = arguments.get("schedule")
            if not isinstance(schedule, Mapping):
                raise ValueError("schedule must be an object.")
            required_fields = {
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
                "start_time",
                "end_time",
                "timezone",
            }
            missing = [field for field in required_fields if field not in schedule]
            if missing:
                raise ValueError(f"Missing required schedule fields: {', '.join(missing)}")
            payload = await client.create_campaign_schedule(campaign_id, schedule=schedule)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Get_Campaign_Schedule":
            campaign_id = int(_require(arguments, "campaign_id"))
            payload = await client.get_campaign_schedule(campaign_id)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Update_Campaign_Schedule":
            campaign_id = int(_require(arguments, "campaign_id"))
            schedule = arguments.get("schedule")
            if not isinstance(schedule, Mapping):
                raise ValueError("schedule must be an object.")
            required_fields = {
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
                "start_time",
                "end_time",
                "timezone",
                "save_as_template",
            }
            missing = [field for field in required_fields if field not in schedule]
            if missing:
                raise ValueError(f"Missing required schedule fields: {', '.join(missing)}")
            payload = await client.update_campaign_schedule(campaign_id, schedule=schedule)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_List_Schedule_Templates":
            payload = await client.list_schedule_templates()
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_List_Schedule_Timezones":
            payload = await client.list_schedule_timezones()
            notice = (
                "Use the timezone 'id' field (e.g., 'America/New_York') when creating or updating campaign schedules. "
                "Do not use the 'name' field."
            )
            return (
                [
                    types.TextContent(type="text", text=_json(payload)),
                    types.TextContent(type="text", text=notice),
                ],
                payload,
            )

        if tool_name == "C_Get_Sending_Schedules":
            day = str(_require(arguments, "day"))
            if day not in ("today", "tomorrow", "day_after_tomorrow"):
                raise ValueError(f"day must be one of: today, tomorrow, day_after_tomorrow")
            payload = await client.get_sending_schedules(day=day)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Get_Campaign_Sending_Schedule":
            campaign_id = int(_require(arguments, "campaign_id"))
            day = str(_require(arguments, "day"))
            if day not in ("today", "tomorrow", "day_after_tomorrow"):
                raise ValueError(f"day must be one of: today, tomorrow, day_after_tomorrow")
            payload = await client.get_campaign_sending_schedule(campaign_id, day=day)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Create_Campaign_Schedule_From_Template":
            campaign_id = int(_require(arguments, "campaign_id"))
            schedule_id = int(_require(arguments, "schedule_id"))
            payload = await client.create_campaign_schedule_from_template(
                campaign_id, schedule_id=schedule_id
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Get_Campaign_Sequence_Steps":
            campaign_id = int(_require(arguments, "campaign_id"))
            payload = await client.get_campaign_sequence_steps(campaign_id)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Create_Campaign_Sequence_Steps":
            campaign_id = int(_require(arguments, "campaign_id"))
            title = str(_require(arguments, "title"))
            sequence_steps = list(_require(arguments, "sequence_steps"))
            
            # Validate all steps have order and validate sequential order
            all_steps_with_order = []
            for i, step in enumerate(sequence_steps):
                is_variant = step.get("variant") is True
                
                # Validate that variant_from_step and variant_from_step_id cannot both be used
                if (
                    step.get("variant_from_step") is not None
                    and step.get("variant_from_step_id") is not None
                ):
                    raise ValueError(
                        f"variant_from_step and variant_from_step_id cannot be used together for step at index {i}"
                    )
                
                # Variant steps must have variant_from_step or variant_from_step_id
                if is_variant:
                    if step.get("variant_from_step") is None and step.get("variant_from_step_id") is None:
                        raise ValueError(
                            f"Variant step at index {i} (id: {step.get('id', 'new')}) must include either "
                            "'variant_from_step' or 'variant_from_step_id' to specify the parent step."
                        )
                
                # ALL steps (main and variant) must have order field
                order = step.get("order")
                if order is None:
                    step_type = "variant" if is_variant else "main"
                    raise ValueError(
                        f"{step_type.capitalize()} step at index {i} (id: {step.get('id', 'new')}) must include 'order' field. "
                        "ALL steps (both main and variant) require sequential order values (1, 2, 3, etc.)."
                    )
                all_steps_with_order.append((i, order))
            
            # Validate all steps have correct sequential order
            if all_steps_with_order:
                all_steps_with_order.sort(key=lambda x: x[1])  # Sort by order
                expected_order = 1
                for idx, order in all_steps_with_order:
                    if order != expected_order:
                        raise ValueError(
                            f"Step at index {idx} has order={order}, but expected order={expected_order}. "
                            "ALL steps must have sequential order values starting from 1 (1, 2, 3, etc.) with no gaps."
                        )
                    expected_order += 1
            
            payload = await client.create_campaign_sequence_steps(
                campaign_id, title=title, sequence_steps=sequence_steps
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Update_Campaign_Sequence_Steps":
            sequence_id = int(_require(arguments, "sequence_id"))
            title = str(_require(arguments, "title"))
            sequence_steps = list(_require(arguments, "sequence_steps"))
            
            # Validate all steps have order and validate sequential order
            all_steps_with_order = []
            for i, step in enumerate(sequence_steps):
                is_variant = step.get("variant") is True
                step_id = step.get("id", "unknown")
                
                # Variant steps must have variant_from_step_id when updating (for existing steps)
                if is_variant and step.get("variant_from_step_id") is None:
                    raise ValueError(
                        f"Variant step at index {i} (id: {step_id}) must include 'variant_from_step_id' field. "
                        "This is required when updating existing variant steps. "
                        "The variant_from_step_id should be the ID of the parent step this variant is based on."
                    )
                
                # ALL steps (main and variant) must have order field
                order = step.get("order")
                if order is None:
                    step_type = "variant" if is_variant else "main"
                    raise ValueError(
                        f"{step_type.capitalize()} step at index {i} (id: {step_id}) must include 'order' field. "
                        "ALL steps (both main and variant) require sequential order values (1, 2, 3, etc.)."
                    )
                all_steps_with_order.append((i, order, step_id))
            
            # Validate all steps have correct sequential order
            if all_steps_with_order:
                all_steps_with_order.sort(key=lambda x: x[1])  # Sort by order
                expected_order = 1
                for idx, order, step_id in all_steps_with_order:
                    if order != expected_order:
                        raise ValueError(
                            f"Step at index {idx} (id: {step_id}) has order={order}, but expected order={expected_order}. "
                            "ALL steps must have sequential order values starting from 1 (1, 2, 3, etc.) with no gaps. "
                            "RECHECK and correct the order of all steps before sending the request."
                        )
                    expected_order += 1
            
            payload = await client.update_campaign_sequence_steps(
                sequence_id, title=title, sequence_steps=sequence_steps
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Delete_Sequence_Step":
            sequence_step_id = int(_require(arguments, "sequence_step_id"))
            payload = await client.delete_sequence_step(sequence_step_id)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Send_Sequence_Step_Test_Email":
            sequence_step_id = int(_require(arguments, "sequence_step_id"))
            sender_email_id = int(_require(arguments, "sender_email_id"))
            to_email = str(_require(arguments, "to_email"))
            use_dedicated_ips = arguments.get("use_dedicated_ips")
            payload = await client.send_sequence_step_test_email(
                sequence_step_id,
                sender_email_id=sender_email_id,
                to_email=to_email,
                use_dedicated_ips=bool(use_dedicated_ips) if use_dedicated_ips is not None else None,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Get_Campaign_Replies":
            campaign_id = int(_require(arguments, "campaign_id"))
            page = int(arguments.get("page", 1))
            per_page = int(arguments.get("per_page", 15))
            search = arguments.get("search")
            status = arguments.get("status")
            folder = arguments.get("folder")
            read = arguments.get("read")
            sender_email_id = arguments.get("sender_email_id")
            lead_id = arguments.get("lead_id")
            tag_ids = arguments.get("tag_ids")
            query_campaign_id = arguments.get("query_campaign_id")
            filters = arguments.get("filters") or {}
            # Move all filter parameters into filters object
            if tag_ids and "tag_ids" not in filters:
                filters["tag_ids"] = [int(tid) for tid in tag_ids] if isinstance(tag_ids, list) else tag_ids
            payload = await client.get_campaign_replies(
                campaign_id,
                search=search,
                status=status,
                folder=folder,
                read=bool(read) if read is not None else None,
                sender_email_id=int(sender_email_id) if sender_email_id is not None else None,
                lead_id=int(lead_id) if lead_id is not None else None,
                query_campaign_id=int(query_campaign_id) if query_campaign_id is not None else None,
                page=page,
                per_page=per_page,
                filters=filters if filters else None,
            )
            pagination_reminder = _pagination_reminder(payload)
            response_text = _json(payload) + pagination_reminder
            return (
                [types.TextContent(type="text", text=response_text)],
                payload,
            )

        if tool_name == "C_Get_Campaign_Leads":
            campaign_id = int(_require(arguments, "campaign_id"))
            page = int(arguments.get("page", 1))
            per_page = int(arguments.get("per_page", 15))
            search = arguments.get("search")
            filters = arguments.get("filters")
            payload = await client.get_campaign_leads(
                campaign_id,
                search=search,
                page=page,
                per_page=per_page,
                filters=filters,
            )
            pagination_reminder = _pagination_reminder(payload)
            response_text = _json(payload) + pagination_reminder
            return (
                [types.TextContent(type="text", text=response_text)],
                payload,
            )

        if tool_name == "C_Remove_Campaign_Leads":
            campaign_id = int(_require(arguments, "campaign_id"))
            lead_ids = list(_require(arguments, "lead_ids"))
            if not lead_ids:
                raise ValueError("lead_ids array cannot be empty")
            payload = await client.remove_campaign_leads(
                campaign_id, lead_ids=[int(lid) for lid in lead_ids]
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Import_Leads_From_List":
            campaign_id = int(_require(arguments, "campaign_id"))
            lead_list_id = int(_require(arguments, "lead_list_id"))
            allow_parallel_sending = arguments.get("allow_parallel_sending")
            payload = await client.import_campaign_leads_from_list(
                campaign_id,
                lead_list_id=lead_list_id,
                allow_parallel_sending=allow_parallel_sending,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Import_Leads_By_IDs":
            campaign_id = int(_require(arguments, "campaign_id"))
            lead_ids = list(_require(arguments, "lead_ids"))
            if not lead_ids:
                raise ValueError("lead_ids array cannot be empty")
            allow_parallel_sending = arguments.get("allow_parallel_sending")
            payload = await client.import_campaign_leads_by_ids(
                campaign_id,
                lead_ids=[int(lid) for lid in lead_ids],
                allow_parallel_sending=allow_parallel_sending,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Stop_Future_Emails_For_Leads":
            campaign_id = int(_require(arguments, "campaign_id"))
            lead_ids = list(_require(arguments, "lead_ids"))
            if not lead_ids:
                raise ValueError("lead_ids array cannot be empty")
            payload = await client.stop_future_emails_for_leads(
                campaign_id, lead_ids=[int(lid) for lid in lead_ids]
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Get_Campaign_Scheduled_Emails":
            campaign_id = int(_require(arguments, "campaign_id"))
            scheduled_date = arguments.get("scheduled_date")
            scheduled_date_local = arguments.get("scheduled_date_local")
            status = arguments.get("status")
            payload = await client.get_campaign_scheduled_emails(
                campaign_id,
                scheduled_date=scheduled_date,
                scheduled_date_local=scheduled_date_local,
                status=status,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Get_Campaign_Sender_Emails":
            campaign_id = int(_require(arguments, "campaign_id"))
            payload = await client.get_campaign_sender_emails(campaign_id)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Get_Campaign_Stats":
            campaign_id = int(_require(arguments, "campaign_id"))
            start_date = str(_require(arguments, "start_date"))
            end_date = str(_require(arguments, "end_date"))
            payload = await client.get_campaign_stats(
                campaign_id, start_date=start_date, end_date=end_date
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Attach_Sender_Emails_To_Campaign":
            campaign_id = int(_require(arguments, "campaign_id"))
            sender_email_ids = list(_require(arguments, "sender_email_ids"))
            if not sender_email_ids:
                raise ValueError("sender_email_ids array cannot be empty")
            payload = await client.attach_sender_emails_to_campaign(
                campaign_id, sender_email_ids=[int(sid) for sid in sender_email_ids]
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Remove_Sender_Emails_From_Campaign":
            campaign_id = int(_require(arguments, "campaign_id"))
            sender_email_ids = list(_require(arguments, "sender_email_ids"))
            if not sender_email_ids:
                raise ValueError("sender_email_ids array cannot be empty")
            payload = await client.remove_sender_emails_from_campaign(
                campaign_id, sender_email_ids=[int(sid) for sid in sender_email_ids]
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Get_Campaign_Line_Area_Chart_Stats":
            campaign_id = int(_require(arguments, "campaign_id"))
            start_date = str(_require(arguments, "start_date"))
            end_date = str(_require(arguments, "end_date"))
            payload = await client.get_campaign_line_area_chart_stats(
                campaign_id, start_date=start_date, end_date=end_date
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "C_Get_Campaign_Details":
            campaign_id = int(_require(arguments, "campaign_id"))
            payload = await client.get_campaign_details(campaign_id)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "R_List_Replies":
            page = int(arguments.get("page", 1))
            per_page = int(arguments.get("per_page", 15))
            search = arguments.get("search")
            status = arguments.get("status")
            folder = arguments.get("folder")
            read = arguments.get("read")
            campaign_id = arguments.get("campaign_id")
            sender_email_id = arguments.get("sender_email_id")
            lead_id = arguments.get("lead_id")
            tag_ids = arguments.get("tag_ids")

            # Convert tag_ids to list of integers if provided
            tag_ids_list = None
            if tag_ids is not None:
                tag_ids_list = [int(tid) for tid in tag_ids] if isinstance(tag_ids, list) else None

            payload = await client.list_replies(
                search=search,
                status=status,
                folder=folder,
                read=read,
                campaign_id=int(campaign_id) if campaign_id is not None else None,
                sender_email_id=int(sender_email_id) if sender_email_id is not None else None,
                lead_id=int(lead_id) if lead_id is not None else None,
                tag_ids=tag_ids_list,
                page=page,
                per_page=per_page,
            )

            # Add pagination reminder
            text_content = _json(payload) + _pagination_reminder(payload)

            return (
                [types.TextContent(type="text", text=text_content)],
                payload,
            )

        if tool_name == "R_Get_Lead_Replies":
            lead_id = str(_require(arguments, "lead_id"))
            search = arguments.get("search")
            status = arguments.get("status")
            folder = arguments.get("folder")
            read = arguments.get("read")
            campaign_id = arguments.get("campaign_id")
            sender_email_id = arguments.get("sender_email_id")
            tag_ids = arguments.get("tag_ids")

            # Convert tag_ids to list of integers if provided
            tag_ids_list = None
            if tag_ids is not None:
                tag_ids_list = [int(tid) for tid in tag_ids] if isinstance(tag_ids, list) else None

            payload = await client.get_lead_replies(
                lead_id,
                search=search,
                status=status,
                folder=folder,
                read=read,
                campaign_id=int(campaign_id) if campaign_id is not None else None,
                sender_email_id=int(sender_email_id) if sender_email_id is not None else None,
                tag_ids=tag_ids_list,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "L_Get_Lead_Scheduled_Emails":
            lead_id = str(_require(arguments, "lead_id"))
            payload = await client.get_lead_scheduled_emails(lead_id)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "L_Get_Lead_Sent_Emails":
            lead_id = str(_require(arguments, "lead_id"))
            payload = await client.get_lead_sent_emails(lead_id)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "R_Get_Reply":
            reply_id = int(_require(arguments, "reply_id"))
            payload = await client.get_reply(reply_id)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "R_Compose_New_Email":
            sender_email_id = int(_require(arguments, "sender_email_id"))
            to_emails = _require(arguments, "to_emails")
            if not isinstance(to_emails, list):
                raise ValueError("to_emails must be a list")
            subject = arguments.get("subject")
            message = arguments.get("message")
            content_type = arguments.get("content_type")
            cc_emails = arguments.get("cc_emails")
            bcc_emails = arguments.get("bcc_emails")
            attachments = arguments.get("attachments")
            use_dedicated_ips = arguments.get("use_dedicated_ips")

            payload = await client.compose_new_email(
                sender_email_id=sender_email_id,
                to_emails=to_emails,
                subject=subject,
                message=message,
                content_type=content_type,
                cc_emails=cc_emails,
                bcc_emails=bcc_emails,
                attachments=attachments,
                use_dedicated_ips=use_dedicated_ips,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "R_Create_Reply":
            reply_id = int(_require(arguments, "reply_id"))
            sender_email_id = int(_require(arguments, "sender_email_id"))
            to_emails = _require(arguments, "to_emails")
            if not isinstance(to_emails, list):
                raise ValueError("to_emails must be a list")
            message = arguments.get("message")
            content_type = arguments.get("content_type")
            cc_emails = arguments.get("cc_emails")
            bcc_emails = arguments.get("bcc_emails")
            attachments = arguments.get("attachments")
            inject_previous_email_body = arguments.get("inject_previous_email_body")
            use_dedicated_ips = arguments.get("use_dedicated_ips")

            payload = await client.create_reply(
                reply_id,
                sender_email_id=sender_email_id,
                to_emails=to_emails,
                message=message,
                content_type=content_type,
                cc_emails=cc_emails,
                bcc_emails=bcc_emails,
                attachments=attachments,
                inject_previous_email_body=inject_previous_email_body,
                use_dedicated_ips=use_dedicated_ips,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "M_List_Sender_Emails":
            search = arguments.get("search")
            tag_ids = arguments.get("tag_ids")
            excluded_tag_ids = arguments.get("excluded_tag_ids")
            without_tags = arguments.get("without_tags")
            filters = arguments.get("filters") or {}
            # Move all filter parameters into filters object
            if tag_ids and "tag_ids" not in filters:
                filters["tag_ids"] = [int(tid) for tid in tag_ids] if isinstance(tag_ids, list) else tag_ids
            if excluded_tag_ids and "excluded_tag_ids" not in filters:
                filters["excluded_tag_ids"] = [int(tid) for tid in excluded_tag_ids] if isinstance(excluded_tag_ids, list) else excluded_tag_ids
            if without_tags is not None and "without_tags" not in filters:
                filters["without_tags"] = without_tags
            payload = await client.list_sender_emails(
                search=search,
                filters=filters if filters else None,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "M_List_Sender_Emails_With_Warmup_Stats":
            start_date = str(_require(arguments, "start_date"))
            end_date = str(_require(arguments, "end_date"))
            search = arguments.get("search")
            tag_ids = arguments.get("tag_ids")
            excluded_tag_ids = arguments.get("excluded_tag_ids")
            without_tags = arguments.get("without_tags")
            warmup_status = arguments.get("warmup_status")
            mx_records_status = arguments.get("mx_records_status")
            filters = arguments.get("filters") or {}
            # Move all filter parameters into filters object
            if tag_ids and "tag_ids" not in filters:
                filters["tag_ids"] = [int(tid) for tid in tag_ids] if isinstance(tag_ids, list) else tag_ids
            if excluded_tag_ids and "excluded_tag_ids" not in filters:
                filters["excluded_tag_ids"] = [int(tid) for tid in excluded_tag_ids] if isinstance(excluded_tag_ids, list) else excluded_tag_ids
            if without_tags is not None and "without_tags" not in filters:
                filters["without_tags"] = without_tags
            if warmup_status and "warmup_status" not in filters:
                filters["warmup_status"] = warmup_status
            if mx_records_status and "mx_records_status" not in filters:
                filters["mx_records_status"] = mx_records_status
            payload = await client.list_sender_emails_with_warmup_stats(
                start_date=start_date,
                end_date=end_date,
                search=search,
                filters=filters if filters else None,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "M_Enable_Warmup_For_Sender_Emails":
            sender_email_ids = _require(arguments, "sender_email_ids")
            if not isinstance(sender_email_ids, list):
                raise ValueError("sender_email_ids must be a list")
            sender_email_ids_list = [int(sid) for sid in sender_email_ids]

            payload = await client.enable_warmup_for_sender_emails(
                sender_email_ids=sender_email_ids_list,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "M_Disable_Warmup_For_Sender_Emails":
            sender_email_ids = _require(arguments, "sender_email_ids")
            if not isinstance(sender_email_ids, list):
                raise ValueError("sender_email_ids must be a list")
            sender_email_ids_list = [int(sid) for sid in sender_email_ids]

            payload = await client.disable_warmup_for_sender_emails(
                sender_email_ids=sender_email_ids_list,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "M_Update_Daily_Warmup_Limits":
            sender_email_ids = _require(arguments, "sender_email_ids")
            if not isinstance(sender_email_ids, list):
                raise ValueError("sender_email_ids must be a list")
            sender_email_ids_list = [int(sid) for sid in sender_email_ids]
            daily_limit = int(_require(arguments, "daily_limit"))
            daily_reply_limit = arguments.get("daily_reply_limit")

            payload = await client.update_daily_warmup_limits(
                sender_email_ids=sender_email_ids_list,
                daily_limit=daily_limit,
                daily_reply_limit=daily_reply_limit,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "M_Get_Sender_Email_With_Warmup_Details":
            sender_email_id = str(_require(arguments, "sender_email_id"))
            start_date = str(_require(arguments, "start_date"))
            end_date = str(_require(arguments, "end_date"))

            payload = await client.get_sender_email_with_warmup_details(
                sender_email_id,
                start_date=start_date,
                end_date=end_date,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "W_List_Workspaces":
            payload = await client.list_workspaces()
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "W_Create_Workspace":
            name = str(_require(arguments, "name"))
            payload = await client.create_workspace(name=name)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "W_Switch_Workspace":
            team_id = int(_require(arguments, "team_id"))
            payload = await client.switch_workspace(team_id=team_id)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "W_Update_Workspace":
            team_id = int(_require(arguments, "team_id"))
            name = str(_require(arguments, "name"))
            payload = await client.update_workspace(team_id, name=name)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "W_Get_Workspace_Details":
            team_id = int(_require(arguments, "team_id"))
            payload = await client.get_workspace_details(team_id)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "W_Invite_Team_Member":
            email = str(_require(arguments, "email"))
            role = str(_require(arguments, "role"))
            payload = await client.invite_team_member(email=email, role=role)
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "W_Get_Workspace_Stats":
            start_date = str(_require(arguments, "start_date"))
            end_date = str(_require(arguments, "end_date"))
            payload = await client.get_workspace_stats(
                start_date=start_date,
                end_date=end_date,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        if tool_name == "W_Get_Workspace_Line_Area_Chart_Stats":
            start_date = str(_require(arguments, "start_date"))
            end_date = str(_require(arguments, "end_date"))
            payload = await client.get_workspace_line_area_chart_stats(
                start_date=start_date,
                end_date=end_date,
            )
            return (
                [types.TextContent(type="text", text=_json(payload))],
                payload,
            )

        return types.CallToolResult(
            content=[types.TextContent(type="text", text=f"Unknown tool: {tool_name}")],
            isError=True,
        )
    except EmailBisonError as exc:
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=f"EmailBison API error: {exc}")],
            isError=True,
        )
    except Exception as exc:  # noqa: BLE001
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=f"Tool execution error: {exc}")],
            isError=True,
        )


async def _run() -> None:
    initialization_options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, initialization_options)


def main() -> None:
    anyio.run(_run)


if __name__ == "__main__":
    main()

