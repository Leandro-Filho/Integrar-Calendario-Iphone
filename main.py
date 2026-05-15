import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import caldav
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from icalendar import Calendar

from sqlalchemy import create_engine, Column, BigInteger, Text, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker


load_dotenv()

APPLE_ID = os.getenv("APPLE_ID")
APPLE_APP_PASSWORD = os.getenv("APPLE_APP_PASSWORD")
CALDAV_URL = os.getenv("CALDAV_URL", "https://caldav.icloud.com/")
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL precisa estar no arquivo .env")

app = FastAPI(title="Apple Calendar Backend")


# =========================
# BANCO DE DADOS
# =========================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


class CalendarEvent(Base):
    __tablename__ = "calendar_events"


    id = Column(BigInteger, primary_key=True, index=True)
    uid = Column(Text, unique=True, index=True, nullable=True)
    title = Column(Text, nullable=False)
    data = Column(Text, nullable=False)
    time = Column(Text, nullable=False)
    notes = Column(Text, nullable=True)
    calendar = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


Base.metadata.create_all(bind=engine)


# =========================
# APPLE CALENDAR
# =========================

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


def save_event_to_database(event_data: Dict[str, Any]):
    db = SessionLocal()

    try:
        uid = event_data.get("uid")

        existing_event = None

        if uid:
            existing_event = db.query(CalendarEvent).filter(
                CalendarEvent.uid == uid
            ).first()

        if existing_event:
            existing_event.title = event_data.get("title")
            existing_event.data = event_data.get("data")
            existing_event.time = event_data.get("time")
            existing_event.notes = event_data.get("notes")
            existing_event.calendar = event_data.get("calendar")
        else:
            new_event = CalendarEvent(
                uid=event_data.get("uid"),
                title=event_data.get("title"),
                data=event_data.get("data"),
                time=event_data.get("time"),
                notes=event_data.get("notes"),
                calendar=event_data.get("calendar"),
            )

            db.add(new_event)

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

# =========================
# ROTAS
# =========================

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

    start_date = datetime.now(timezone.utc) - timedelta(days=1)
    end_date = start_date + timedelta(days=days)

    events: List[Dict[str, Any]] = []

    for calendar in calendars:
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


@app.get("/sync-events")
def sync_events(
    days: int = Query(default=7, description="Quantidade de dias para buscar e salvar eventos"),
):
    client = get_caldav_client()
    principal = client.principal()
    calendars = principal.calendars()

    start_date = datetime.now(timezone.utc) - timedelta(days=1)
    end_date = start_date + timedelta(days=days)

    saved_events: List[Dict[str, Any]] = []

    for calendar in calendars:
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
                    save_event_to_database(event_data)
                    saved_events.append(event_data)

        except Exception as error:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Erro ao sincronizar eventos no banco de dados",
                    "details": str(error),
                },
            )

    saved_events = sorted(saved_events, key=lambda item: item.get("title") or "")

    return {
        "message": "Eventos sincronizados com sucesso",
        "calendar": "Trabalho",
        "days": days,
        "total_saved": len(saved_events),
        "events": saved_events,
    }


@app.get("/database-events")
def get_database_events():
    db = SessionLocal()

    try:
        events = db.query(CalendarEvent).order_by(CalendarEvent.id.desc()).all()

        result = []

        for event in events:
            result.append({
                "id": event.id,
                "uid": event.uid,
                "title": event.title,
                "data": event.data,
                "time": event.time,
                "notes": event.notes,
                "calendar": event.calendar,
                "created_at": event.created_at.isoformat() if event.created_at else None,
                "updated_at": event.updated_at.isoformat() if event.updated_at else None,
            })

        return {
            "total": len(result),
            "events": result,
        }

    finally:
        db.close()


@app.get("/debug/events")
def debug_events(days: int = 30):
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
            "events": [],
            "error": None,
        }

        try:
            raw_events = calendar.date_search(
                start=start_date,
                end=end_date,
                expand=True,
            )

            item["found"] = len(raw_events)

            for raw_event in raw_events[:10]:
                item["events"].append({
                    "url": str(raw_event.url),
                    "raw_preview": raw_event.data[:500],
                })

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