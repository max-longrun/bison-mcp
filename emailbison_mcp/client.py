from __future__ import annotations

# Lightweight EmailBison REST client helpers.

import json
from typing import Any, Dict, Iterable, Mapping, Optional

import httpx
from pydantic import BaseModel, Field


class EmailBisonError(RuntimeError):
    """Raised when the EmailBison API returns a non-successful response."""


class PaginatedLeadsResponse(BaseModel):
    data: list[dict[str, Any]]
    page: int = 1
    per_page: int = Field(default=50, alias="perPage")
    total: int = 0


class EmailBisonClient:
    """Minimal async-friendly client for the EmailBison REST API."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.emailbison.com/v1",
        timeout: float = 30.0,
    ) -> None:
        if not api_key:
            raise ValueError("EmailBison API key is required.")

        self._api_key = api_key
        self._timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=timeout,
        )

    @property
    def client(self) -> httpx.AsyncClient:
        return self._client

    async def close(self) -> None:
        await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json_body: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        """Execute an HTTP request and raise EmailBisonError on failure."""
        response = await self._client.request(
            method,
            path,
            params=params,
            json=json_body,
        )
        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = {"message": response.text or "Unknown error"}
            detail = payload.get("message") or payload
            raise EmailBisonError(f"EmailBison API error ({response.status_code}): {detail}")
        if response.headers.get("Content-Type", "").startswith("application/json"):
            return response.json()
        return response.text

    @staticmethod
    def _to_camel(snake_key: str) -> str:
        parts = snake_key.split("_")
        return parts[0] + "".join(part.capitalize() for part in parts[1:]) if parts else snake_key

    @staticmethod
    def _serialize_param_value(value: Any) -> Any:
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, (list, tuple, set)):
            return ",".join(str(item) for item in value)
        return value

    def _prepare_query(
        self,
        base: Mapping[str, Any],
        extra_filters: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        for key, value in base.items():
            if value is None or value == "":
                continue
            # Preserve dot notation (e.g., "filters.lead_campaign_status")
            param_key = key if "." in key else self._to_camel(key)
            # For filter keys with dot notation, pass arrays as-is (httpx will repeat them)
            if "." in param_key and isinstance(value, (list, tuple, set)):
                params[param_key] = list(value)
            else:
                params[param_key] = self._serialize_param_value(value)
        if extra_filters:
            for key, value in extra_filters.items():
                if value is None or value == "":
                    continue
                # Preserve dot notation for filter keys
                param_key = str(key) if "." in str(key) else self._to_camel(str(key))
                # For filter keys with dot notation, pass arrays as-is (httpx will repeat them)
                if "." in param_key and isinstance(value, (list, tuple, set)):
                    params[param_key] = list(value)
                else:
                    params[param_key] = self._serialize_param_value(value)
        return params

    async def list_leads(
        self,
        *,
        search: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
        tag_ids: Optional[Iterable[str]] = None,
        interested: Optional[bool] = None,
        filters: Optional[Mapping[str, Any]] = None,
    ) -> PaginatedLeadsResponse:
        # GET request uses body for filters
        body: Dict[str, Any] = {
            "page": page,
            "per_page": per_page,
        }
        if search is not None:
            body["search"] = search
        if status is not None:
            body["status"] = status
        if interested is not None:
            body["interested"] = interested
        if filters:
            body["filters"] = dict(filters)
        # If tag_ids is provided separately, add it to filters (for backward compatibility)
        if tag_ids and (not filters or "tag_ids" not in filters):
            if "filters" not in body:
                body["filters"] = {}
            body["filters"]["tag_ids"] = list(tag_ids)
        payload = await self.request("GET", "/leads", json_body=body)
        return PaginatedLeadsResponse.model_validate(payload)

    async def create_lead(
        self,
        *,
        email: str,
        first_name: str,
        last_name: str,
        company: Optional[str] = None,
        title: Optional[str] = None,
        notes: Optional[str] = None,
        custom_variables: Optional[list[dict[str, str]]] = None,
        tags: Optional[Iterable[str]] = None,
    ) -> dict[str, Any]:
        body: Dict[str, Any] = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
        }
        if company is not None:
            body["company"] = company
        if title is not None:
            body["title"] = title
        if notes is not None:
            body["notes"] = notes
        if custom_variables is not None:
            body["custom_variables"] = custom_variables
        if tags:
            body["tags"] = list(tags)
        return await self.request("POST", "/leads", json_body=body)

    async def get_lead(self, lead_id: int | str) -> dict[str, Any]:
        """Get a specific lead by its ID or email address."""
        return await self.request("GET", f"/leads/{lead_id}")

    async def update_lead(
        self,
        lead_id: int | str,
        *,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        company: Optional[str] = None,
        title: Optional[str] = None,
        notes: Optional[str] = None,
        custom_variables: Optional[list[dict[str, str]]] = None,
    ) -> dict[str, Any]:
        """Update the details of a specific lead. Fields not passed will remain unchanged."""
        body: Dict[str, Any] = {}
        if email is not None:
            body["email"] = email
        if first_name is not None:
            body["first_name"] = first_name
        if last_name is not None:
            body["last_name"] = last_name
        if company is not None:
            body["company"] = company
        if title is not None:
            body["title"] = title
        if notes is not None:
            body["notes"] = notes
        if custom_variables is not None:
            body["custom_variables"] = custom_variables
        return await self.request("PATCH", f"/leads/{lead_id}", json_body=body)

    async def unsubscribe_lead(self, lead_id: int | str) -> dict[str, Any]:
        """Unsubscribe a lead from scheduled emails."""
        return await self.request("PATCH", f"/leads/{lead_id}/unsubscribe")

    async def bulk_create_leads_csv(
        self,
        *,
        name: str,
        csv_content: str,
        columns_to_map: list[dict[str, str]],
        existing_lead_behavior: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create multiple leads in a single request using CSV. Requires multipart/form-data."""
        # Prepare form data
        data: Dict[str, Any] = {
            "name": name,
            "csv": csv_content,
        }
        if existing_lead_behavior is not None:
            data["existing_lead_behavior"] = existing_lead_behavior
        
        # Convert columns_to_map to JSON string for form data
        if columns_to_map:
            data["columnsToMap"] = json.dumps(columns_to_map)
        
        # Use httpx's form data handling (data parameter automatically sets multipart/form-data)
        # Need to override headers to not include Content-Type (httpx will set it with boundary)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }
        response = await self._client.post(
            "/leads/bulk/csv",
            data=data,
            headers=headers,
        )
        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = {"message": response.text or "Unknown error"}
            detail = payload.get("message") or payload
            raise EmailBisonError(f"EmailBison API error ({response.status_code}): {detail}")
        if response.headers.get("Content-Type", "").startswith("application/json"):
            return response.json()
        return response.text

    async def list_campaigns(
        self,
        *,
        search: Optional[str] = None,
        status: Optional[str] = None,
        tag_ids: Optional[Iterable[str | int]] = None,
        page: int = 1,
        per_page: int = 50,
        filters: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        # Use GET with body for filters
        # POST /campaigns is for creating campaigns (requires 'name' field)
        body: Dict[str, Any] = {
            "page": page,
            "per_page": per_page,
        }
        if search is not None:
            body["search"] = search
        if status is not None:
            body["status"] = status
        if filters:
            body["filters"] = dict(filters)
        # If tag_ids is provided separately, add it to filters (for backward compatibility)
        if tag_ids and (not filters or "tag_ids" not in filters):
            if "filters" not in body:
                body["filters"] = {}
            body["filters"]["tag_ids"] = [int(tid) for tid in tag_ids]
        return await self.request("GET", "/campaigns", json_body=body)

    async def create_campaign(
        self,
        *,
        name: str,
        campaign_type: Optional[str] = None,
        additional_fields: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        body: Dict[str, Any] = {"name": name}
        if campaign_type:
            body["type"] = campaign_type
        if additional_fields:
            for key, value in additional_fields.items():
                if value is not None:
                    body[key] = value
        return await self.request("POST", "/campaigns", json_body=body)

    async def send_email(
        self,
        *,
        email_account_id: str,
        to: Iterable[str],
        subject: str,
        html_body: str,
        cc: Optional[Iterable[str]] = None,
        bcc: Optional[Iterable[str]] = None,
        tags: Optional[Iterable[str]] = None,
    ) -> dict[str, Any]:
        body: Dict[str, Any] = {
            "emailAccountId": email_account_id,
            "to": list(to),
            "subject": subject,
            "htmlBody": html_body,
        }
        if cc:
            body["cc"] = list(cc)
        if bcc:
            body["bcc"] = list(bcc)
        if tags:
            body["tags"] = list(tags)
        return await self.request("POST", "/emails/send", json_body=body)

    async def get_account_details(self) -> dict[str, Any]:
        """Return details about the authenticated user and their workspace."""
        return await self.request("GET", "/users")

    async def list_tags(self) -> dict[str, Any]:
        """Return all tags available in the authenticated workspace."""
        return await self.request("GET", "/tags")

    async def list_custom_variables(self) -> dict[str, Any]:
        """Return all custom variables for the authenticated workspace."""
        return await self.request("GET", "/custom-variables")

    async def create_custom_variable(
        self,
        *,
        name: str,
    ) -> dict[str, Any]:
        """Create a new custom variable for the workspace."""
        body: Dict[str, Any] = {"name": name}
        return await self.request("POST", "/custom-variables", json_body=body)

    async def create_tag(
        self,
        *,
        name: str,
        default: Optional[bool] = None,
    ) -> dict[str, Any]:
        """Create a new tag."""
        body: Dict[str, Any] = {"name": name}
        if default is not None:
            body["default"] = default
        return await self.request("POST", "/tags", json_body=body)

    async def get_tag(self, tag_id: int | str) -> dict[str, Any]:
        """Get a specific tag by its ID."""
        return await self.request("GET", f"/tags/{tag_id}")

    async def delete_tag(self, tag_id: int | str) -> dict[str, Any]:
        """Delete a tag by its ID."""
        return await self.request("DELETE", f"/tags/{tag_id}")

    async def attach_tags_to_campaigns(
        self,
        *,
        campaign_ids: list[int],
        tag_ids: list[int],
        skip_webhooks: Optional[bool] = None,
    ) -> dict[str, Any]:
        """Attach multiple tags to campaigns."""
        body: Dict[str, Any] = {
            "campaign_ids": campaign_ids,
            "tag_ids": tag_ids,
        }
        if skip_webhooks is not None:
            body["skip_webhooks"] = skip_webhooks
        return await self.request("POST", "/tags/attach-to-campaigns", json_body=body)

    async def remove_tags_from_campaigns(
        self,
        *,
        campaign_ids: list[int],
        tag_ids: list[int],
        skip_webhooks: Optional[bool] = None,
    ) -> dict[str, Any]:
        """Detach multiple tags from campaigns."""
        body: Dict[str, Any] = {
            "campaign_ids": campaign_ids,
            "tag_ids": tag_ids,
        }
        if skip_webhooks is not None:
            body["skip_webhooks"] = skip_webhooks
        return await self.request("POST", "/tags/remove-from-campaigns", json_body=body)

    async def attach_tags_to_leads(
        self,
        *,
        lead_ids: list[int],
        tag_ids: list[int],
        skip_webhooks: Optional[bool] = None,
    ) -> dict[str, Any]:
        """Attach multiple tags to leads."""
        body: Dict[str, Any] = {
            "lead_ids": lead_ids,
            "tag_ids": tag_ids,
        }
        if skip_webhooks is not None:
            body["skip_webhooks"] = skip_webhooks
        return await self.request("POST", "/tags/attach-to-leads", json_body=body)

    async def remove_tags_from_leads(
        self,
        *,
        lead_ids: list[int],
        tag_ids: list[int],
        skip_webhooks: Optional[bool] = None,
    ) -> dict[str, Any]:
        """Detach multiple tags from leads."""
        body: Dict[str, Any] = {
            "lead_ids": lead_ids,
            "tag_ids": tag_ids,
        }
        if skip_webhooks is not None:
            body["skip_webhooks"] = skip_webhooks
        return await self.request("POST", "/tags/remove-from-leads", json_body=body)

    async def attach_tags_to_sender_emails(
        self,
        *,
        sender_email_ids: list[int],
        tag_ids: list[int],
        skip_webhooks: Optional[bool] = None,
    ) -> dict[str, Any]:
        """Attach multiple tags to email accounts (sender emails)."""
        body: Dict[str, Any] = {
            "sender_email_ids": sender_email_ids,
            "tag_ids": tag_ids,
        }
        if skip_webhooks is not None:
            body["skip_webhooks"] = skip_webhooks
        return await self.request("POST", "/tags/attach-to-sender-emails", json_body=body)

    async def remove_tags_from_sender_emails(
        self,
        *,
        sender_email_ids: list[int],
        tag_ids: list[int],
        skip_webhooks: Optional[bool] = None,
    ) -> dict[str, Any]:
        """Detach multiple tags from email accounts (sender emails)."""
        body: Dict[str, Any] = {
            "sender_email_ids": sender_email_ids,
            "tag_ids": tag_ids,
        }
        if skip_webhooks is not None:
            body["skip_webhooks"] = skip_webhooks
        return await self.request("POST", "/tags/remove-from-sender-emails", json_body=body)

    async def duplicate_campaign(self, campaign_id: int | str) -> dict[str, Any]:
        """Duplicate an existing campaign and return the cloned campaign payload."""
        return await self.request("POST", f"/campaigns/{campaign_id}/duplicate")

    async def pause_campaign(self, campaign_id: int | str) -> dict[str, Any]:
        """Pause a campaign by ID and return the updated campaign payload."""
        return await self.request("PATCH", f"/campaigns/{campaign_id}/pause")

    async def resume_campaign(self, campaign_id: int | str) -> dict[str, Any]:
        """Resume a paused campaign by ID and return the queued campaign payload."""
        return await self.request("PATCH", f"/campaigns/{campaign_id}/resume")

    async def archive_campaign(self, campaign_id: int | str) -> dict[str, Any]:
        """Archive a campaign by ID and return the archived campaign payload."""
        return await self.request("PATCH", f"/campaigns/{campaign_id}/archive")

    async def update_campaign_settings(
        self,
        campaign_id: int | str,
        *,
        updates: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Update campaign settings with provided fields."""
        body = {key: value for key, value in updates.items() if value is not None}
        return await self.request("PATCH", f"/campaigns/{campaign_id}/update", json_body=body)

    async def create_campaign_schedule(
        self,
        campaign_id: int | str,
        *,
        schedule: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Create or replace the schedule for a campaign."""
        body = dict(schedule)
        return await self.request("POST", f"/campaigns/{campaign_id}/schedule", json_body=body)

    async def get_campaign_schedule(self, campaign_id: int | str) -> dict[str, Any]:
        """Fetch the sending schedule for a campaign."""
        return await self.request("GET", f"/campaigns/{campaign_id}/schedule")

    async def update_campaign_schedule(
        self,
        campaign_id: int | str,
        *,
        schedule: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Completely replace the schedule for a campaign."""
        body = dict(schedule)
        return await self.request("PUT", f"/campaigns/{campaign_id}/schedule", json_body=body)

    async def list_schedule_templates(self) -> dict[str, Any]:
        """Return all saved schedule templates for the workspace."""
        return await self.request("GET", "/campaigns/schedule/templates")

    async def list_schedule_timezones(self) -> dict[str, Any]:
        """Return all available timezones for campaign schedules."""
        return await self.request("GET", "/campaigns/schedule/available-timezones")

    async def get_sending_schedules(self, *, day: str) -> dict[str, Any]:
        """Get sending schedules for campaigns on a specific day (today, tomorrow, or day_after_tomorrow)."""
        return await self.request("GET", "/campaigns/sending-schedules", json_body={"day": day})

    async def get_campaign_sending_schedule(
        self, campaign_id: int | str, *, day: str
    ) -> dict[str, Any]:
        """Get the sending schedule for a specific campaign on a given day."""
        return await self.request(
            "GET", f"/campaigns/{campaign_id}/sending-schedule", json_body={"day": day}
        )

    async def create_campaign_schedule_from_template(
        self, campaign_id: int | str, *, schedule_id: int
    ) -> dict[str, Any]:
        """Create a campaign schedule from a saved template."""
        return await self.request(
            "POST",
            f"/campaigns/{campaign_id}/create-schedule-from-template",
            json_body={"schedule_id": schedule_id},
        )

    async def delete_sequence_step(self, sequence_step_id: int | str) -> dict[str, Any]:
        """Delete a specific sequence step from a sequence."""
        return await self.request("DELETE", f"/campaigns/sequence-steps/{sequence_step_id}")

    async def get_campaign_sequence_steps(self, campaign_id: int | str) -> dict[str, Any]:
        """Get the sequence steps for a campaign."""
        return await self.request("GET", f"/campaigns/v1.1/{campaign_id}/sequence-steps")

    async def create_campaign_sequence_steps(
        self,
        campaign_id: int | str,
        *,
        title: str,
        sequence_steps: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Create campaign sequence steps from scratch."""
        body = {"title": title, "sequence_steps": sequence_steps}
        return await self.request(
            "POST", f"/campaigns/v1.1/{campaign_id}/sequence-steps", json_body=body
        )

    async def update_campaign_sequence_steps(
        self,
        sequence_id: int | str,
        *,
        title: str,
        sequence_steps: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Update campaign sequence steps. Sequence ID can be found in the Campaign object."""
        body = {"title": title, "sequence_steps": sequence_steps}
        return await self.request(
            "PUT", f"/campaigns/v1.1/sequence-steps/{sequence_id}", json_body=body
        )

    async def send_sequence_step_test_email(
        self,
        sequence_step_id: int | str,
        *,
        sender_email_id: int,
        to_email: str,
        use_dedicated_ips: bool | None = None,
    ) -> dict[str, Any]:
        """Send a test email from a sequence step. Requires at least one lead in the campaign."""
        body: dict[str, Any] = {
            "sender_email_id": sender_email_id,
            "to_email": to_email,
        }
        if use_dedicated_ips is not None:
            body["use_dedicated_ips"] = use_dedicated_ips
        return await self.request(
            "POST",
            f"/campaigns/sequence-steps/{sequence_step_id}/test-email",
            json_body=body,
        )

    async def get_campaign_replies(
        self,
        campaign_id: int | str,
        *,
        search: Optional[str] = None,
        status: Optional[str] = None,
        folder: Optional[str] = None,
        read: Optional[bool] = None,
        sender_email_id: Optional[int] = None,
        lead_id: Optional[int] = None,
        query_campaign_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 15,
        filters: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        """Get all replies associated with a campaign. Returns paginated results. All filter parameters are sent in the request body."""
        # All filter parameters go in the request body, not query parameters
        body: Dict[str, Any] = {
            "page": page,
            "per_page": per_page,
        }
        if search is not None:
            body["search"] = search
        if status is not None:
            body["status"] = status
        if folder is not None:
            body["folder"] = folder
        if read is not None:
            body["read"] = read
        if sender_email_id is not None:
            body["sender_email_id"] = sender_email_id
        if lead_id is not None:
            body["lead_id"] = lead_id
        if query_campaign_id is not None:
            body["campaign_id"] = query_campaign_id
        if filters:
            body["filters"] = dict(filters)
        return await self.request("POST", f"/campaigns/{campaign_id}/replies", json_body=body)

    async def get_campaign_leads(
        self,
        campaign_id: int | str,
        *,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 15,
        filters: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        """Get all leads associated with a campaign. Returns paginated results. GET request uses body for filters."""
        # GET request uses body for filters
        body: Dict[str, Any] = {
            "page": page,
            "per_page": per_page,
        }
        if search is not None:
            body["search"] = search
        if filters:
            body["filters"] = dict(filters)
        return await self.request("GET", f"/campaigns/{campaign_id}/leads", json_body=body)

    async def remove_campaign_leads(
        self, campaign_id: int | str, *, lead_ids: Iterable[int]
    ) -> dict[str, Any]:
        """Remove leads from a campaign."""
        body = {"lead_ids": [int(lead_id) for lead_id in lead_ids]}
        return await self.request(
            "DELETE", f"/campaigns/{campaign_id}/leads", json_body=body
        )

    async def import_campaign_leads_from_list(
        self,
        campaign_id: int | str,
        *,
        lead_list_id: int,
        allow_parallel_sending: bool | None = None,
    ) -> dict[str, Any]:
        """Import leads from an existing lead list into a campaign."""
        body: dict[str, Any] = {"lead_list_id": lead_list_id}
        if allow_parallel_sending is not None:
            body["allow_parallel_sending"] = allow_parallel_sending
        return await self.request(
            "POST",
            f"/campaigns/{campaign_id}/leads/attach-lead-list",
            json_body=body,
        )

    async def import_campaign_leads_by_ids(
        self,
        campaign_id: int | str,
        *,
        lead_ids: Iterable[int],
        allow_parallel_sending: bool | None = None,
    ) -> dict[str, Any]:
        """Import leads by their IDs into a campaign. For active campaigns, leads are cached locally and synced every 5 minutes. For reply followup campaigns, this will start from the last sent reply."""
        body: dict[str, Any] = {"lead_ids": [int(lead_id) for lead_id in lead_ids]}
        if allow_parallel_sending is not None:
            body["allow_parallel_sending"] = allow_parallel_sending
        return await self.request(
            "POST",
            f"/campaigns/{campaign_id}/leads/attach-leads",
            json_body=body,
        )

    async def stop_future_emails_for_leads(
        self, campaign_id: int | str, *, lead_ids: Iterable[int]
    ) -> dict[str, Any]:
        """Stop future emails for selected leads in a campaign."""
        body = {"lead_ids": [int(lead_id) for lead_id in lead_ids]}
        return await self.request(
            "POST",
            f"/campaigns/{campaign_id}/leads/stop-future-emails",
            json_body=body,
        )

    async def get_campaign_scheduled_emails(
        self,
        campaign_id: int | str,
        *,
        scheduled_date: str | None = None,
        scheduled_date_local: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """Get all scheduled emails for a campaign. Supports filtering by scheduled date, local scheduled date, and status."""
        body: dict[str, Any] = {}
        if scheduled_date is not None:
            body["scheduled_date"] = scheduled_date
        if scheduled_date_local is not None:
            body["scheduled_date_local"] = scheduled_date_local
        if status is not None:
            body["status"] = status
        # Note: API documentation shows GET with body, but we use POST for requests with bodies
        return await self.request(
            "POST",
            f"/campaigns/{campaign_id}/scheduled-emails",
            json_body=body if body else None,
        )

    async def get_campaign_sender_emails(
        self, campaign_id: int | str
    ) -> dict[str, Any]:
        """Get all email accounts (sender emails) associated with a campaign."""
        return await self.request("GET", f"/campaigns/{campaign_id}/sender-emails")

    async def get_campaign_stats(
        self, campaign_id: int | str, *, start_date: str, end_date: str
    ) -> dict[str, Any]:
        """Get campaign statistics (summary) for a date range. Returns overall stats and per-sequence-step stats."""
        body = {"start_date": start_date, "end_date": end_date}
        return await self.request(
            "POST", f"/campaigns/{campaign_id}/stats", json_body=body
        )

    async def attach_sender_emails_to_campaign(
        self, campaign_id: int | str, *, sender_email_ids: Iterable[int]
    ) -> dict[str, Any]:
        """Attach sender emails to a campaign by their IDs."""
        body = {"sender_email_ids": [int(sender_id) for sender_id in sender_email_ids]}
        return await self.request(
            "POST",
            f"/campaigns/{campaign_id}/attach-sender-emails",
            json_body=body,
        )

    async def remove_sender_emails_from_campaign(
        self, campaign_id: int | str, *, sender_email_ids: Iterable[int]
    ) -> dict[str, Any]:
        """Remove sender emails from a draft or paused campaign by their IDs."""
        body = {"sender_email_ids": [int(sender_id) for sender_id in sender_email_ids]}
        return await self.request(
            "DELETE",
            f"/campaigns/{campaign_id}/remove-sender-emails",
            json_body=body,
        )

    async def get_campaign_line_area_chart_stats(
        self, campaign_id: int | str, *, start_date: str, end_date: str
    ) -> dict[str, Any]:
        """Get full normalized stats by date for a given period. Returns events: Replied, Total Opens, Unique Opens, Sent, Bounced, Unsubscribed, Interested."""
        params = {"start_date": start_date, "end_date": end_date}
        return await self.request(
            "GET",
            f"/campaigns/{campaign_id}/line-area-chart-stats",
            params=params,
        )

    async def get_campaign_details(self, campaign_id: int | str) -> dict[str, Any]:
        """Get the details of a specific campaign."""
        return await self.request("GET", f"/campaigns/{campaign_id}")

    async def list_replies(
        self,
        *,
        search: Optional[str] = None,
        status: Optional[str] = None,
        folder: Optional[str] = None,
        read: Optional[bool] = None,
        campaign_id: Optional[int] = None,
        sender_email_id: Optional[int] = None,
        lead_id: Optional[int] = None,
        tag_ids: Optional[Iterable[int]] = None,
        page: int = 1,
        per_page: int = 15,
    ) -> dict[str, Any]:
        """Get all replies for the authenticated user. Returns paginated results. Uses GET request with query parameters."""
        base_filters: Dict[str, Any] = {
            "page": page,
            "per_page": per_page,
        }
        if search is not None:
            base_filters["search"] = search
        if status is not None:
            base_filters["status"] = status
        if folder is not None:
            base_filters["folder"] = folder
        if read is not None:
            base_filters["read"] = read
        if campaign_id is not None:
            base_filters["campaign_id"] = campaign_id
        if sender_email_id is not None:
            base_filters["sender_email_id"] = sender_email_id
        if lead_id is not None:
            base_filters["lead_id"] = lead_id
        if tag_ids:
            base_filters["tag_ids"] = list(tag_ids)
        params = self._prepare_query(base_filters)
        return await self.request("GET", "/replies", params=params)

    async def get_lead_replies(
        self,
        lead_id: int | str,
        *,
        search: Optional[str] = None,
        status: Optional[str] = None,
        folder: Optional[str] = None,
        read: Optional[bool] = None,
        campaign_id: Optional[int] = None,
        sender_email_id: Optional[int] = None,
        tag_ids: Optional[Iterable[int]] = None,
    ) -> dict[str, Any]:
        """Get all replies for a specific lead. Uses GET request with query parameters."""
        base_filters: Dict[str, Any] = {}
        if search is not None:
            base_filters["search"] = search
        if status is not None:
            base_filters["status"] = status
        if folder is not None:
            base_filters["folder"] = folder
        if read is not None:
            base_filters["read"] = read
        if campaign_id is not None:
            base_filters["campaign_id"] = campaign_id
        if sender_email_id is not None:
            base_filters["sender_email_id"] = sender_email_id
        if tag_ids:
            base_filters["tag_ids"] = list(tag_ids)
        params = self._prepare_query(base_filters)
        return await self.request("GET", f"/leads/{lead_id}/replies", params=params)

    async def get_lead_scheduled_emails(self, lead_id: int | str) -> dict[str, Any]:
        """Get all scheduled emails for a specific lead."""
        return await self.request("GET", f"/leads/{lead_id}/scheduled-emails")

    async def get_lead_sent_emails(self, lead_id: int | str) -> dict[str, Any]:
        """Get all sent campaign emails for a specific lead."""
        return await self.request("GET", f"/leads/{lead_id}/sent-emails")

    async def get_reply(self, reply_id: int | str) -> dict[str, Any]:
        """Get a specific reply by its ID."""
        return await self.request("GET", f"/replies/{reply_id}")

    async def compose_new_email(
        self,
        *,
        sender_email_id: int,
        to_emails: list[dict[str, str]],
        subject: Optional[str] = None,
        message: Optional[str] = None,
        content_type: Optional[str] = None,
        cc_emails: Optional[list[dict[str, str]]] = None,
        bcc_emails: Optional[list[dict[str, str]]] = None,
        attachments: Optional[list[str]] = None,
        use_dedicated_ips: Optional[bool] = None,
    ) -> dict[str, Any]:
        """Send a one-off email in a new email thread."""
        body: Dict[str, Any] = {
            "sender_email_id": sender_email_id,
            "to_emails": to_emails,
        }
        if subject is not None:
            body["subject"] = subject
        if message is not None:
            body["message"] = message
        if content_type is not None:
            body["content_type"] = content_type
        if cc_emails is not None:
            body["cc_emails"] = cc_emails
        if bcc_emails is not None:
            body["bcc_emails"] = bcc_emails
        if attachments is not None:
            body["attachments"] = attachments
        if use_dedicated_ips is not None:
            body["use_dedicated_ips"] = use_dedicated_ips
        return await self.request("POST", "/replies/new", json_body=body)

    async def create_reply(
        self,
        reply_id: int | str,
        *,
        sender_email_id: int,
        to_emails: list[dict[str, str]],
        message: Optional[str] = None,
        content_type: Optional[str] = None,
        cc_emails: Optional[list[dict[str, str]]] = None,
        bcc_emails: Optional[list[dict[str, str]]] = None,
        attachments: Optional[list[str]] = None,
        inject_previous_email_body: Optional[bool] = None,
        use_dedicated_ips: Optional[bool] = None,
    ) -> dict[str, Any]:
        """Reply to an existing email thread."""
        body: Dict[str, Any] = {
            "sender_email_id": sender_email_id,
            "to_emails": to_emails,
        }
        if message is not None:
            body["message"] = message
        if content_type is not None:
            body["content_type"] = content_type
        if cc_emails is not None:
            body["cc_emails"] = cc_emails
        if bcc_emails is not None:
            body["bcc_emails"] = bcc_emails
        if attachments is not None:
            body["attachments"] = attachments
        if inject_previous_email_body is not None:
            body["inject_previous_email_body"] = inject_previous_email_body
        if use_dedicated_ips is not None:
            body["use_dedicated_ips"] = use_dedicated_ips
        return await self.request("POST", f"/replies/{reply_id}/reply", json_body=body)

    async def list_sender_emails(
        self,
        *,
        search: Optional[str] = None,
        filters: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        """Get all email accounts (sender emails) for the authenticated workspace. Uses GET request with body for filters."""
        body: Dict[str, Any] = {}
        if search is not None:
            body["search"] = search
        if filters:
            body["filters"] = dict(filters)
        return await self.request("GET", "/sender-emails", json_body=body)

    async def list_sender_emails_with_warmup_stats(
        self,
        *,
        start_date: str,
        end_date: str,
        search: Optional[str] = None,
        filters: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        """Get all email accounts with warmup stats for the authenticated workspace. Uses GET request with body for filters."""
        body: Dict[str, Any] = {
            "start_date": start_date,
            "end_date": end_date,
        }
        if search is not None:
            body["search"] = search
        if filters:
            body["filters"] = dict(filters)
        return await self.request("GET", "/warmup/sender-emails", json_body=body)

    async def enable_warmup_for_sender_emails(
        self,
        *,
        sender_email_ids: Iterable[int],
    ) -> dict[str, Any]:
        """Enable warmup for selected email accounts."""
        json_body = {
            "sender_email_ids": list(sender_email_ids),
        }
        return await self.request("PATCH", "/warmup/sender-emails/enable", json_body=json_body)

    async def disable_warmup_for_sender_emails(
        self,
        *,
        sender_email_ids: Iterable[int],
    ) -> dict[str, Any]:
        """Disable warmup for selected email accounts."""
        json_body = {
            "sender_email_ids": list(sender_email_ids),
        }
        return await self.request("PATCH", "/warmup/sender-emails/disable", json_body=json_body)

    async def update_daily_warmup_limits(
        self,
        *,
        sender_email_ids: Iterable[int],
        daily_limit: int,
        daily_reply_limit: Optional[str] = None,
    ) -> dict[str, Any]:
        """Update daily warmup limits for selected email accounts."""
        json_body: Dict[str, Any] = {
            "sender_email_ids": list(sender_email_ids),
            "daily_limit": daily_limit,
        }
        if daily_reply_limit is not None:
            json_body["daily_reply_limit"] = daily_reply_limit
        return await self.request("PATCH", "/warmup/sender-emails/update-daily-warmup-limits", json_body=json_body)

    async def get_sender_email_with_warmup_details(
        self,
        sender_email_id: int | str,
        *,
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        """Get a single email account (sender email) with its warmup details."""
        params = {
            "start_date": start_date,
            "end_date": end_date,
        }
        return await self.request("GET", f"/warmup/sender-emails/{sender_email_id}", params=params)

    async def list_workspaces(self) -> dict[str, Any]:
        """Get all workspaces for the authenticated user."""
        return await self.request("GET", "/workspaces/v1.1")

    async def create_workspace(self, *, name: str) -> dict[str, Any]:
        """Create a new workspace."""
        json_body = {
            "name": name,
        }
        return await self.request("POST", "/workspaces/v1.1", json_body=json_body)

    async def switch_workspace(self, *, team_id: int) -> dict[str, Any]:
        """Switch to a different workspace."""
        json_body = {
            "team_id": team_id,
        }
        return await self.request("POST", "/workspaces/v1.1/switch-workspace", json_body=json_body)

    async def update_workspace(self, team_id: int, *, name: str) -> dict[str, Any]:
        """Update workspace information, specifically the workspace name."""
        json_body = {
            "name": name,
        }
        return await self.request("PUT", f"/workspaces/v1.1/{team_id}", json_body=json_body)

    async def get_workspace_details(self, team_id: int) -> dict[str, Any]:
        """Get the details of a specific workspace."""
        return await self.request("GET", f"/workspaces/v1.1/{team_id}")

    async def invite_team_member(self, *, email: str, role: str) -> dict[str, Any]:
        """Invite a new member to the team."""
        json_body = {
            "email": email,
            "role": role,
        }
        return await self.request("POST", "/workspaces/v1.1/invite-members", json_body=json_body)

    async def get_workspace_stats(
        self,
        *,
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        """Get overall stats for the workspace between two given dates."""
        params = {
            "start_date": start_date,
            "end_date": end_date,
        }
        return await self.request("GET", "/workspaces/v1.1/stats", params=params)

    async def get_workspace_line_area_chart_stats(
        self,
        *,
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        """Get full normalized stats by date for a given period for the workspace."""
        params = {
            "start_date": start_date,
            "end_date": end_date,
        }
        return await self.request("GET", "/workspaces/v1.1/line-area-chart-stats", params=params)


