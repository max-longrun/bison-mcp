 # EmailBison MCP Server

Python implementation of a Model Context Protocol (MCP) server that connects Claude to the [EmailBison](https://docs.emailbison.com/get-started) API. The server exposes curated tools for managing leads, campaigns, and direct sends within an EmailBison workspace.

## Features

- **Multi-account support**: Manage multiple EmailBison accounts via `config.json`
- Securely connect using API keys (via `config.json` or `EMAILBISON_API_KEY` environment variable)
- List and create leads
- List campaigns and draft new campaigns with optional immediate send
- Send ad-hoc emails from any configured EmailBison sender account
- JSON schema validation for tool arguments and structured results for Claude
- Rich MCP metadata: resources surface quick-reference docs, and prompts illustrate common automation flows

## Project Layout

- `emailbison_mcp/client.py` – lightweight async HTTP client for EmailBison
- `emailbison_mcp/server.py` – MCP server definition and tool handlers
- `pyproject.toml` – project metadata and runtime dependencies

## Prerequisites

- Python 3.10+
- An EmailBison API key with access to your workspace
- `pipx` or `pip` for installing dependencies

## Installation

```bash
pip install -e .
```

Alternatively, in a virtual environment:

```bash
python -m venv .venv
.venv\\Scripts\\activate  # PowerShell
pip install -e .
```

## Configuration

### Multi-Account Mode (Recommended)

Create a `config.json` file in the `emailbison_mcp/` directory with the following structure:

```json
{
  "clients": {
    "Account1": {
      "mcp_key": "your-api-key-here",
      "mcp_url": "https://send.longrun.agency/api"
    },
    "Account2": {
      "mcp_key": "another-api-key-here",
      "mcp_url": ""
    }
  },
  "default_client": "Account1"
}
```

**Important**: Never commit `config.json` to version control. Add it to `.gitignore`.

All tools accept an optional `client_name` parameter to specify which account to use. If not provided, the `default_client` from config.json is used.

See `document:emailbison/multi-account-config` for detailed configuration documentation.

### Single-Account Mode (Backward Compatible)

If `config.json` is not found, the server falls back to environment variables. Copy `.env.example` to `.env` (or configure your shell) with:

```
EMAILBISON_API_KEY=51|LYXIxPC5LeEsdEwK3Yn37hOfeQkcLsOBbKEsfsID07a9c1cc
EMAILBISON_BASE_URL=https://send.longrun.agency/api
EMAILBISON_TIMEOUT_SECONDS=30
```

`EMAILBISON_BASE_URL` and `EMAILBISON_TIMEOUT_SECONDS` are optional overrides. The default base URL is `https://send.longrun.agency/api`.

## Running the Server

```bash
python -m emailbison_mcp.server
```

The entry point speaks MCP over stdio. To connect Claude Desktop or another MCP-compatible client:

1. Register the executable (`python -m emailbison_mcp.server`) as a custom tool.
2. Ensure the environment variables are available to the process.
3. Start the client – Claude will auto-discover the EmailBison tools.

## Available Tools

- `list_leads` – Paginated lead lookup.
- `get_lead` – Retrieve the details of a specific lead by its ID or email address. Returns comprehensive information including contact details, status, custom variables, campaign data, and statistics.
- `create_lead` – Create a single lead (contact) record. Requires email, first_name, and last_name. Supports optional company, title, notes, custom variables (array of name/value objects), and tags.
- `update_lead` – Update the details of a specific lead by its ID or email address. All fields are optional. Only fields passed in the request will be updated; fields and custom variables not passed will remain unchanged.
- `unsubscribe_lead` – Unsubscribe a lead from scheduled emails. Stops all future scheduled emails from being sent to the lead. Returns the updated lead with status set to 'unsubscribed'.
- `bulk_create_leads_csv` – Create multiple leads in a single request using a CSV file. Requires CSV content as a string, column mapping configuration (email, first_name, last_name required; company, title, custom_variable optional), and list name. Supports existing lead behavior options (put, patch, skip).
- `list_campaigns` – View campaigns with optional search, status, and tag ID filters.
- `create_campaign` – Create a campaign with a name, optional type, and advanced settings payload.
- `send_email` – Send a direct email via a sender account.
- `get_account_details` – Inspect the authenticated user's profile and workspace limits.
- `list_workspaces` – Retrieve all workspaces for the authenticated user. Returns workspace details including ID, name, personal_team flag, main flag, email verification credits, sender email limit, warmup limit, access flags, and timestamps.
- `create_workspace` – Create a new workspace for the authenticated user. Requires a workspace name. Returns the created workspace object with all workspace details including ID, name, flags, limits, credits, and timestamps.
- `switch_workspace` – Switch to a different workspace for the authenticated user. Changes the active workspace context. Requires the team_id (workspace ID) of the target workspace. Use list_workspaces to get available workspace IDs. Returns the name of the workspace that was switched to.
- `update_workspace` – Update workspace information for the authenticated user, specifically the workspace name. Requires the team_id (workspace ID) of the workspace to update and the new name. Use list_workspaces to get available workspace IDs. Returns the updated workspace name.
- `get_workspace_details` – Retrieve the details of a specific workspace for the authenticated user. Returns comprehensive workspace information including ID, name, flags, email verification credits, sender email limit, warmup limit, access flags, and timestamps. Requires the team_id (workspace ID) of the workspace to retrieve. Use list_workspaces to get available workspace IDs.
- `invite_team_member` – Invite a new member to the authenticated user's team (workspace). Requires the email address and role of the new team member. Returns the created team member invitation object with ID, UUID, workspace_id, email, role, and timestamps.
- `get_workspace_stats` – Retrieve overall statistics for the authenticated user's workspace between two given dates. Returns comprehensive metrics including emails sent, total leads contacted, opens (count and percentage), unique opens per contact (count and percentage), unique replies per contact (count and percentage), bounced (count and percentage), unsubscribed (count and percentage), and interested (count and percentage). Requires start_date and end_date parameters.
- `get_workspace_line_area_chart_stats` – Retrieve full normalized stats by date for a given period for the authenticated user's workspace. Returns time-series data for events: Replied, Total Opens, Unique Opens, Sent, Bounced, Unsubscribed, and Interested. Each event includes a label, color, and dates array containing date-value pairs for charting. Requires start_date and end_date parameters.
- `list_tags` – Retrieve workspace tags; use returned IDs when filtering leads.
- `list_custom_variables` – Retrieve all custom variables for the workspace. Returns variables with IDs, names, and timestamps. Custom variables can be used in email templates and lead data.
- `create_custom_variable` – Create a new custom variable for the workspace. Specify the variable name. Returns the created variable with ID, name, and timestamps.
- `get_tag` – Retrieve a specific tag by its ID. Returns tag details including name, default status, and timestamps.
- `create_tag` – Create a new tag in the workspace. Specify the tag name and optionally mark it as default.
- `delete_tag` – Delete a tag by its ID. Returns a success message confirming the tag was removed.
- `attach_tags_to_campaigns` – Attach multiple tags to multiple campaigns in a single operation. Requires arrays of campaign IDs and tag IDs.
- `remove_tags_from_campaigns` – Detach multiple tags from multiple campaigns in a single operation. Requires arrays of campaign IDs and tag IDs.
- `attach_tags_to_leads` – Attach multiple tags to multiple leads in a single operation. Requires arrays of lead IDs and tag IDs.
- `remove_tags_from_leads` – Detach multiple tags from multiple leads in a single operation. Requires arrays of lead IDs and tag IDs.
- `attach_tags_to_sender_emails` – Attach multiple tags to multiple email accounts (sender emails) in a single operation. Requires arrays of sender email IDs and tag IDs.
- `remove_tags_from_sender_emails` – Detach multiple tags from multiple email accounts (sender emails) in a single operation. Requires arrays of sender email IDs and tag IDs.
- `duplicate_campaign` – Clone an existing campaign by ID.
- `pause_campaign` – Pause a campaign using its ID.
- `resume_campaign` – Resume a paused campaign using its ID.
- `archive_campaign` – Archive a campaign using its ID.
- `update_campaign_settings` – Patch campaign limits, unsubscribe text, and other flags.
- `create_campaign_schedule` – Define campaign sending days, times, and timezone.
- `get_campaign_schedule` – Retrieve the current schedule configuration for a campaign.
- `update_campaign_schedule` – Replace an existing campaign schedule.
- `list_schedule_templates` – View all saved schedule templates for the workspace.
- `list_schedule_timezones` – View all available timezones for campaign schedules (use the ID field).
- `get_sending_schedules` – View sending schedules for campaigns on a specific day (today, tomorrow, or day_after_tomorrow).
- `get_campaign_sending_schedule` – View the sending schedule for a specific campaign on a given day.
- `create_campaign_schedule_from_template` – Create a campaign schedule using a saved schedule template.
- `get_campaign_sequence_steps` – View the sequence steps of a campaign, including email subjects, bodies, wait times, and other details.
- `create_campaign_sequence_steps` – Create campaign sequence steps from scratch with email subjects, bodies, wait times, and optional variant settings.
- `update_campaign_sequence_steps` – Update existing campaign sequence steps. Include step IDs for existing steps to update them.
- `delete_sequence_step` – Delete a specific sequence step from a sequence.
- `send_sequence_step_test_email` – Send a test email from a sequence step. Requires at least one lead in the campaign.
- `get_campaign_details` – Retrieve the details of a specific campaign. Returns comprehensive information including ID, UUID, name, type, status, completion percentage, email statistics, lead counts, settings, timestamps, and tags.
- `list_replies` – Retrieve all replies for the authenticated user across all campaigns. Supports filtering by search, status, folder, read status, campaign, sender email, lead, tags, and more. Returns paginated results.
- `get_lead_replies` – Retrieve all replies for a specific lead by its ID or email address. Supports filtering by search, status, folder, read status, campaign, sender email, and tags.
- `get_lead_scheduled_emails` – Retrieve all scheduled emails for a specific lead by its ID or email address. Returns scheduled email details including status, scheduled dates, engagement metrics, and full lead and sender email information.
- `get_lead_sent_emails` – Retrieve all sent campaign emails for a specific lead by its ID or email address. Returns sent email details including status, scheduled dates, sent date, and engagement metrics (opens, clicks, replies, interested).
- `get_reply` – Retrieve a specific reply by its ID. Returns comprehensive information including reply details, message content, attachments, and associated metadata.
- `compose_new_email` – Send a one-off email in a new email thread (not a reply to an existing conversation). Supports HTML/text content, multiple recipients (to, CC, BCC), attachments, and dedicated IP options.
- `create_reply` – Reply to an existing email thread. Supports HTML/text content, multiple recipients (to, CC, BCC), attachments, option to inject previous email body, and dedicated IP options.
- `get_campaign_replies` – Retrieve all replies associated with a specific campaign. Supports filtering by search, status, folder, read status, sender email, lead, tags, and more. Returns paginated results.
- `get_campaign_leads` – Retrieve all leads associated with a campaign. Supports filtering by search term and complex filters for status, emails sent, opens, replies, verification statuses, tags, and dates.
- `remove_campaign_leads` – Remove one or more leads from a campaign by providing their lead IDs.
- `import_campaign_leads_from_list` – Import leads from an existing lead list into a campaign. Allows adding multiple leads at once by referencing a lead list ID.
- `import_campaign_leads_by_ids` – Import leads by their IDs into a campaign. For active campaigns, leads are cached locally and synced every 5 minutes. For reply followup campaigns, starts from the last sent reply.
- `stop_future_emails_for_leads` – Stop future emails for selected leads in a campaign. Prevents the campaign from sending additional emails to the specified leads.
- `get_campaign_scheduled_emails` – Retrieve all scheduled emails associated with a campaign. Returns detailed information including subject, body, status, scheduled dates, lead information, and sender email details. Supports filtering by scheduled date, local scheduled date, and status.
- `list_sender_emails` – Retrieve all email accounts (sender emails) associated with the authenticated workspace. Returns detailed information including name, email address, email signature, IMAP/SMTP settings, daily limits, type, status, statistics, and tags. Supports filtering by search term, tag IDs, excluded tag IDs, and accounts without tags.
- `list_sender_emails_with_warmup_stats` – Retrieve all email accounts (sender emails) with warmup statistics. Returns email account details plus warmup metrics (emails sent, replies received, emails saved from spam, warmup score, bounce counts). Requires start_date and end_date parameters. Supports filtering by search term, tag IDs, excluded tag IDs, accounts without tags, warmup status (enabled/disabled), and MX records status (records missing/records valid).
- `enable_warmup_for_sender_emails` – Enable warmup for selected email accounts. This operation enables the warmup process for all specified sender email IDs to improve email deliverability by gradually increasing sending volume. Returns a success message. Note: This operation can take a few minutes if the list of email accounts is long.
- `disable_warmup_for_sender_emails` – Disable warmup for selected email accounts. This operation disables the warmup process for all specified sender email IDs. Warmup emails will slowly ramp down over a period of 24 hours. Returns a success message. Note: This operation can take a few minutes if the list of email accounts is long.
- `update_daily_warmup_limits` – Update daily warmup limits for selected email accounts. Sets the daily limit of warmup emails to send for the specified sender email IDs. Optionally, you can also set the daily reply limit (can be set to 'auto' string). WARNING: You should only use the daily_reply_limit parameter if explicitly told by your inbox reseller. Returns a success message.
- `get_sender_email_with_warmup_details` – Retrieve a single email account (sender email) with its warmup details. Returns email account details (ID, email, name, domain, tags) and warmup metrics (emails sent, replies received, emails saved from spam, warmup score, bounce counts) for the specified date range. Requires sender_email_id (ID or email address), start_date, and end_date parameters.
- `get_campaign_sender_emails` – Retrieve all email accounts (sender emails) associated with a campaign. Returns detailed information including name, email address, IMAP/SMTP settings, daily limits, status, statistics, and tags.
- `get_campaign_stats` – Retrieve campaign statistics (summary) for a specified date range. Returns overall metrics (emails sent, opens, replies, bounces, etc.) and per-sequence-step statistics.
- `get_campaign_line_area_chart_stats` – Retrieve full normalized stats by date for a given period. Returns time-series data for events: Replied, Total Opens, Unique Opens, Sent, Bounced, Unsubscribed, and Interested. Each event includes date-value pairs for charting.
- `attach_sender_emails_to_campaign` – Attach sender emails to a campaign by providing their sender email IDs. Configures which email accounts will be used to send emails for the campaign.
- `remove_sender_emails_from_campaign` – Remove sender emails from a draft or paused campaign by providing their sender email IDs. Note: This operation can only be performed on campaigns that are in draft or paused status.

Each tool returns a structured JSON payload plus a formatted text summary for Claude.

**Important: Pagination** - Many endpoints return paginated results (15 entries per page by default). Always use pagination when fetching data. Check the `links.next` field in responses to get the next page, or use the `page` parameter to fetch specific pages. See the pagination resource for details.

### Resources

- `document:emailbison/api-reference` – Key REST endpoints and filter hints.
- `document:emailbison/mcp-variables` – Configuration options (multi-account and single-account modes).
- `document:emailbison/multi-account-config` – Detailed guide for setting up multiple accounts.
- `document:emailbison/pagination` – Guide for handling paginated API responses.
- `document:emailbison/account-details` – Usage notes for the `GET /users` account metadata endpoint.
- `document:emailbison/tags` – Guidance on retrieving tag IDs and using them in filters.

Claude can read these docs via the MCP resource browser for quick reminders.

### Prompt Templates

- `list-interested-leads` – Example request for surfacing responsive leads.
- `review-active-campaigns` – Audit ongoing outreach with engagement metrics.
- `summarise-account-limits` – Pull account metadata and highlight quota-related fields.
- `filter-leads-by-tag` – Walkthrough that fetches tag IDs before filtering leads.

Use them as-is or adapt them when orchestrating workflows with Claude.

## Development

```bash
pip install -r requirements.txt  # if you prefer requirements files
ruff check
pytest
```

The project currently uses `httpx`, `pydantic`, `anyio`, and `mcp`.

## References

- EmailBison API docs: https://docs.emailbison.com/get-started
- Model Context Protocol spec: https://docs.anthropic.com/en/docs/model-context-protocol

## License

MIT – see `LICENSE` if added.

