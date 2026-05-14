import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import caldav
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from icalendar import Calendar


load_dotenv()

APPLE_ID = os.getenv("APPLE_ID")
APPLE_APP_PASSWORD = os.getenv("APPLE_APP_PASSWORD")
CALDAV_URL = os.getenv("CALDAV_URL", "https://caldav.icloud.com/")

app = FastAPI(title="Apple Calendar Backend")


def get_caldav_client():
    if not APPLE_ID or not APPLE_APP_PASSWORD:
        raise ValueError("APPLE_ID e APPLE_APP_PASSWORD precisam estar no arquivo .env")

    client = caldav.DAVClient(
        url=CALDAV_URL,
        username=APPLE_ID,
        password=APPLE_APP_PASSWORD,
    )

    return client


def parse_event(raw_event: Any, calendar_name: str) -> Dict[str, Any]:
    ical_data = raw_event.data
    parsed_calendar = Calendar.from_ical(ical_data)

    for component in parsed_calendar.walk():
        if component.name == "VEVENT":
            title = str(component.get("summary", "Sem título"))

            start = component.get("dtstart")
            end = component.get("dtend")
            location = component.get("location")
            description = component.get("description")
            uid = component.get("uid")

            start_value = start.dt if start else None
            end_value = end.dt if end else None

            return {
                "uid": str(uid) if uid else None,
                "calendar": calendar_name,
                "title": title,
                "start": start_value.isoformat() if start_value else None,
                "end": end_value.isoformat() if end_value else None,
                "location": str(location) if location else None,
                "description": str(description) if description else None,
            }

    return {}


@app.get("/")
def health_check():
    return {
        "status": "ok",
        "message": "Apple Calendar Backend rodando"
    }


@app.get("/calendars")
def list_calendars():
    client = get_caldav_client()
    principal = client.principal()
    calendars = principal.calendars()

    result = []

    for calendar in calendars:
        result.append({
            "name": calendar.name,
            "url": str(calendar.url),
        })

    return result


@app.get("/events")
def list_events(
    days: int = Query(default=7, description="Quantidade de dias para buscar eventos"),
):
    client = get_caldav_client()
    principal = client.principal()
    calendars = principal.calendars()

    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(days=days)

    events: List[Dict[str, Any]] = []

    for calendar in calendars:
        try:
            raw_events = calendar.date_search(
                start=start_date,
                end=end_date,
                expand=True,
            )

            for raw_event in raw_events:
                event_data = parse_event(raw_event, calendar.name)
                if event_data:
                    events.append(event_data)

        except Exception as error:
            events.append({
                "calendar": calendar.name,
                "error": str(error),
            })

    events = sorted(events, key=lambda item: item.get("start") or "")

    return JSONResponse(content={
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "days": days,
        },
        "total_events": len(events),
        "events": events,
    })