import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import caldav
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from icalendar import Calendar


# Carrega as variáveis do arquivo .env
load_dotenv()

APPLE_ID = os.getenv("APPLE_ID")
APPLE_APP_PASSWORD = os.getenv("APPLE_APP_PASSWORD")
CALDAV_URL = os.getenv("CALDAV_URL", "https://caldav.icloud.com/")

app = FastAPI(title="Apple Calendar Reader")


def get_caldav_client():
    """
    Cria a conexão com o calendário do iCloud usando CalDAV.
    """

    if not APPLE_ID or not APPLE_APP_PASSWORD:
        raise ValueError("APPLE_ID e APPLE_APP_PASSWORD precisam estar no arquivo .env")

    return caldav.DAVClient(
        url=CALDAV_URL,
        username=APPLE_ID,
        password=APPLE_APP_PASSWORD,
    )


def parse_event(raw_event: Any, calendar_name: str) -> Dict[str, Any]:
    """
    Recebe um evento bruto do iCloud e extrai as informações principais.
    """

    ical_data = raw_event.data
    parsed_calendar = Calendar.from_ical(ical_data)

    for component in parsed_calendar.walk():
        if component.name == "VEVENT":
            uid = component.get("uid")
            title = component.get("summary")
            notes = component.get("description")

            start = component.get("dtstart")
            start_value = start.dt if start else None

            if isinstance(start_value, datetime):
                event_date = start_value.strftime("%Y-%m-%d")
                event_time = start_value.strftime("%H:%M")
            else:
                event_date = str(start_value) if start_value else ""
                event_time = "Dia inteiro"

            return {
                "uid": str(uid) if uid else None,
                "title": str(title) if title else "Sem título",
                "data": event_date,
                "time": event_time,
                "notes": str(notes) if notes else None,
                "calendar": calendar_name,
            }

    return {}


@app.get("/")
def health_check():
    """
    Teste simples para saber se a API está rodando.
    """

    return {
        "status": "ok",
        "message": "Apple Calendar Reader rodando"
    }


@app.get("/calendars")
def list_calendars():
    """
    Lista os calendários encontrados na conta iCloud.
    """

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
    """
    Busca eventos do calendário chamado 'Trabalho'.
    """

    client = get_caldav_client()
    principal = client.principal()
    calendars = principal.calendars()

    start_date = datetime.now(timezone.utc) - timedelta(days=1)
    end_date = start_date + timedelta(days=days)

    events: List[Dict[str, Any]] = []

    for calendar in calendars:
        # Aqui filtramos apenas o calendário "Trabalho"
        if calendar.name.strip().lower() != "trabalho":
            continue

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
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Erro ao buscar eventos no calendário Trabalho",
                    "details": str(error),
                },
            )

    events = sorted(events, key=lambda item: item.get("title") or "")

    return {
        "calendar": "Trabalho",
        "days": days,
        "total_events": len(events),
        "events": events,
    }


@app.get("/debug/events")
def debug_events(days: int = 30):
    """
    Rota simples de debug para ver quais calendários retornam eventos.
    """

    client = get_caldav_client()
    principal = client.principal()
    calendars = principal.calendars()

    start_date = datetime.now(timezone.utc) - timedelta(days=1)
    end_date = datetime.now(timezone.utc) + timedelta(days=days)

    debug_result = []

    for calendar in calendars:
        item = {
            "calendar": calendar.name,
            "url": str(calendar.url),
            "found": 0,
            "error": None,
        }

        try:
            raw_events = calendar.date_search(
                start=start_date,
                end=end_date,
                expand=True,
            )

            item["found"] = len(raw_events)

        except Exception as error:
            item["error"] = str(error)

        debug_result.append(item)

    return {
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "days": days,
        },
        "calendars": debug_result,
    }