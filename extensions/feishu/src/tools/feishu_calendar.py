"""feishu_calendar tool — read and manage Feishu Calendar events.

Provides the agent with the ability to list, create, get, update, and delete
calendar events on behalf of the bot or on the user's primary calendar.

Required Feishu app scopes:
  - calendar:calendar:readonly  (list/get)
  - calendar:calendar           (create/update/delete)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

TOOL_NAME = "feishu_calendar"
TOOL_DESCRIPTION = (
    "Manage Feishu calendar events. "
    "Supports: list_events (upcoming events), get_event, create_event, "
    "update_event, delete_event. "
    "Use this to check the user's schedule, create meetings, or find free time slots."
)
TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "list_events",
                "get_event",
                "create_event",
                "update_event",
                "delete_event",
            ],
            "description": (
                "Action to perform. "
                "'list_events': list upcoming events (use start_time/end_time to filter). "
                "'get_event': get full details of one event (requires event_id). "
                "'create_event': create a new calendar event. "
                "'update_event': update an existing event (requires event_id). "
                "'delete_event': delete an event (requires event_id)."
            ),
        },
        "calendar_id": {
            "type": "string",
            "description": (
                "Calendar ID. Use 'primary' or omit to use the bot's primary calendar. "
                "Example: 'feishu.cn_xxxxxxxx@group.calendar.feishu.cn'."
            ),
        },
        "event_id": {
            "type": "string",
            "description": "Event ID — required for get_event, update_event, delete_event.",
        },
        "summary": {
            "type": "string",
            "description": "Event title / summary.",
        },
        "description": {
            "type": "string",
            "description": "Event description body.",
        },
        "start_time": {
            "type": "string",
            "description": (
                "For list_events: filter start (Unix timestamp string, e.g. '1700000000'). "
                "For create/update: event start time as Unix timestamp string."
            ),
        },
        "end_time": {
            "type": "string",
            "description": (
                "For list_events: filter end (Unix timestamp string). "
                "For create/update: event end time as Unix timestamp string."
            ),
        },
        "timezone": {
            "type": "string",
            "description": "Timezone for the event, e.g. 'Asia/Shanghai'. Defaults to 'Asia/Shanghai'.",
        },
        "location": {
            "type": "string",
            "description": "Location name for the event.",
        },
        "attendees": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of attendee open_ids (user IDs) to invite.",
        },
        "visibility": {
            "type": "string",
            "enum": ["default", "public", "private"],
            "description": "Event visibility. Defaults to 'default'.",
        },
        "page_size": {
            "type": "integer",
            "description": "Max events to return for list_events (default 20, max 50).",
        },
        "page_token": {
            "type": "string",
            "description": "Pagination token for list_events.",
        },
    },
    "required": ["action"],
}


def _fmt_event(evt: Any) -> dict:
    """Serialize a CalendarEvent object to a plain dict."""
    start = getattr(evt, "start_time", None)
    end = getattr(evt, "end_time", None)
    loc = getattr(evt, "location", None)
    return {
        "event_id": getattr(evt, "event_id", ""),
        "summary": getattr(evt, "summary", ""),
        "description": getattr(evt, "description", ""),
        "status": getattr(evt, "status", ""),
        "start_time": getattr(start, "timestamp", "") if start else "",
        "start_date": getattr(start, "date", "") if start else "",
        "end_time": getattr(end, "timestamp", "") if end else "",
        "end_date": getattr(end, "date", "") if end else "",
        "location": getattr(loc, "name", "") if loc else "",
        "visibility": getattr(evt, "visibility", ""),
        "app_link": getattr(evt, "app_link", ""),
    }


async def run_feishu_calendar(
    params: dict[str, Any],
    client: Any,
) -> dict[str, Any]:
    """Execute feishu_calendar tool call."""
    action = params.get("action", "list_events")
    calendar_id = params.get("calendar_id") or "primary"
    event_id = params.get("event_id", "")
    timezone = params.get("timezone", "Asia/Shanghai")

    loop = asyncio.get_running_loop()

    # ------------------------------------------------------------------
    # Resolve "primary" to the bot's actual primary calendar ID
    # ------------------------------------------------------------------
    if calendar_id == "primary":
        try:
            from lark_oapi.api.calendar.v4 import (
                GetPrimaryCalendarRequest,
                GetPrimaryCalendarRequestBody,
            )
            req = (
                GetPrimaryCalendarRequest.builder()
                .user_id_type("open_id")
                .request_body(GetPrimaryCalendarRequestBody.builder().build())
                .build()
            )
            resp = await loop.run_in_executor(
                None, lambda: client.calendar.v4.calendar.primary(req)
            )
            if resp.success() and resp.data and resp.data.calendars:
                first = resp.data.calendars[0]
                cal = getattr(first, "calendar", None)
                if cal:
                    calendar_id = getattr(cal, "calendar_id", "primary")
        except Exception as e:
            logger.debug("[feishu_calendar] Could not resolve primary calendar: %s", e)

    # ------------------------------------------------------------------
    # list_events
    # ------------------------------------------------------------------
    if action == "list_events":
        from lark_oapi.api.calendar.v4 import ListCalendarEventRequest

        try:
            page_size = min(int(params.get("page_size") or 20), 50)
            builder = (
                ListCalendarEventRequest.builder()
                .calendar_id(calendar_id)
                .page_size(page_size)
                .user_id_type("open_id")
            )
            if params.get("start_time"):
                builder = builder.start_time(str(params["start_time"]))
            if params.get("end_time"):
                builder = builder.end_time(str(params["end_time"]))
            if params.get("page_token"):
                builder = builder.page_token(params["page_token"])

            request = builder.build()
            response = await loop.run_in_executor(
                None, lambda: client.calendar.v4.calendar_event.list(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}

            events = [_fmt_event(e) for e in (getattr(response.data, "items", None) or [])]
            return {
                "calendar_id": calendar_id,
                "events": events,
                "count": len(events),
                "has_more": getattr(response.data, "has_more", False),
                "page_token": getattr(response.data, "page_token", ""),
            }
        except Exception as e:
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # get_event
    # ------------------------------------------------------------------
    elif action == "get_event":
        if not event_id:
            return {"error": "event_id is required for get_event"}
        from lark_oapi.api.calendar.v4 import GetCalendarEventRequest

        try:
            request = (
                GetCalendarEventRequest.builder()
                .calendar_id(calendar_id)
                .event_id(event_id)
                .user_id_type("open_id")
                .build()
            )
            response = await loop.run_in_executor(
                None, lambda: client.calendar.v4.calendar_event.get(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            return _fmt_event(response.data.event) if response.data else {"error": "no data"}
        except Exception as e:
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # create_event
    # ------------------------------------------------------------------
    elif action == "create_event":
        from lark_oapi.api.calendar.v4 import (
            CreateCalendarEventRequest, CreateCalendarEventRequestBody,
            CalendarEvent, TimeInfo,
        )

        try:
            start_ts = str(params.get("start_time", ""))
            end_ts = str(params.get("end_time", ""))
            if not start_ts or not end_ts:
                return {"error": "start_time and end_time are required for create_event"}

            start = TimeInfo.builder().timestamp(start_ts).timezone(timezone).build()
            end = TimeInfo.builder().timestamp(end_ts).timezone(timezone).build()

            evt_builder = (
                CalendarEvent.builder()
                .start_time(start)
                .end_time(end)
            )
            if params.get("summary"):
                evt_builder = evt_builder.summary(params["summary"])
            if params.get("description"):
                evt_builder = evt_builder.description(params["description"])
            if params.get("visibility"):
                evt_builder = evt_builder.visibility(params["visibility"])

            if params.get("location"):
                from lark_oapi.api.calendar.v4 import EventLocation
                loc = EventLocation.builder().name(params["location"]).build()
                evt_builder = evt_builder.location(loc)

            request = (
                CreateCalendarEventRequest.builder()
                .calendar_id(calendar_id)
                .user_id_type("open_id")
                .request_body(
                    CreateCalendarEventRequestBody.builder()
                    .event(evt_builder.build())
                    .build()
                )
                .build()
            )
            response = await loop.run_in_executor(
                None, lambda: client.calendar.v4.calendar_event.create(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}

            result = _fmt_event(response.data.event) if response.data else {}

            # Add attendees if specified
            attendees = params.get("attendees") or []
            if attendees and result.get("event_id"):
                await _add_attendees(client, calendar_id, result["event_id"], attendees, loop)

            return {"status": "created", **result}
        except Exception as e:
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # update_event
    # ------------------------------------------------------------------
    elif action == "update_event":
        if not event_id:
            return {"error": "event_id is required for update_event"}
        from lark_oapi.api.calendar.v4 import (
            PatchCalendarEventRequest, PatchCalendarEventRequestBody,
            CalendarEvent, TimeInfo,
        )

        try:
            evt_builder = CalendarEvent.builder()
            if params.get("summary"):
                evt_builder = evt_builder.summary(params["summary"])
            if params.get("description"):
                evt_builder = evt_builder.description(params["description"])
            if params.get("visibility"):
                evt_builder = evt_builder.visibility(params["visibility"])
            if params.get("start_time"):
                start = TimeInfo.builder().timestamp(str(params["start_time"])).timezone(timezone).build()
                evt_builder = evt_builder.start_time(start)
            if params.get("end_time"):
                end = TimeInfo.builder().timestamp(str(params["end_time"])).timezone(timezone).build()
                evt_builder = evt_builder.end_time(end)
            if params.get("location"):
                from lark_oapi.api.calendar.v4 import EventLocation
                loc = EventLocation.builder().name(params["location"]).build()
                evt_builder = evt_builder.location(loc)

            request = (
                PatchCalendarEventRequest.builder()
                .calendar_id(calendar_id)
                .event_id(event_id)
                .user_id_type("open_id")
                .request_body(
                    PatchCalendarEventRequestBody.builder()
                    .event(evt_builder.build())
                    .build()
                )
                .build()
            )
            response = await loop.run_in_executor(
                None, lambda: client.calendar.v4.calendar_event.patch(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            return {"status": "updated", "event_id": event_id}
        except Exception as e:
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # delete_event
    # ------------------------------------------------------------------
    elif action == "delete_event":
        if not event_id:
            return {"error": "event_id is required for delete_event"}
        from lark_oapi.api.calendar.v4 import DeleteCalendarEventRequest

        try:
            request = (
                DeleteCalendarEventRequest.builder()
                .calendar_id(calendar_id)
                .event_id(event_id)
                .build()
            )
            response = await loop.run_in_executor(
                None, lambda: client.calendar.v4.calendar_event.delete(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            return {"status": "deleted", "event_id": event_id}
        except Exception as e:
            return {"error": str(e)}

    return {"error": f"Unknown action: {action}"}


async def _add_attendees(
    client: Any,
    calendar_id: str,
    event_id: str,
    open_ids: list[str],
    loop: Any,
) -> None:
    """Add attendees to an event after creation."""
    from lark_oapi.api.calendar.v4 import (
        CreateCalendarEventAttendeeRequest,
        CreateCalendarEventAttendeeRequestBody,
        CalendarEventAttendee,
    )

    try:
        attendees = [
            CalendarEventAttendee.builder()
            .type("user")
            .user_id(uid)
            .build()
            for uid in open_ids
        ]
        request = (
            CreateCalendarEventAttendeeRequest.builder()
            .calendar_id(calendar_id)
            .event_id(event_id)
            .user_id_type("open_id")
            .request_body(
                CreateCalendarEventAttendeeRequestBody.builder()
                .attendees(attendees)
                .build()
            )
            .build()
        )
        await loop.run_in_executor(
            None,
            lambda: client.calendar.v4.calendar_event_attendee.create(request),
        )
    except Exception as e:
        logger.warning("[feishu_calendar] Failed to add attendees: %s", e)
