# Importa o módulo os para acessar variáveis de ambiente do arquivo .env
import os

# Importa ferramentas para trabalhar com datas, horários e fusos
from datetime import datetime, timedelta, timezone

# Importa tipos auxiliares para deixar o código mais claro
# Any = qualquer tipo
# Dict = dicionário
# List = lista
from typing import Any, Dict, List

# Biblioteca que permite conectar com calendários via protocolo CalDAV
# É ela que conversa com o iCloud Calendar
import caldav

# Função que carrega as variáveis do arquivo .env
from dotenv import load_dotenv

# FastAPI é o framework usado para criar a API/backend
# Query permite receber parâmetros pela URL, como ?days=30
from fastapi import FastAPI, Query

# JSONResponse permite devolver respostas JSON customizadas, principalmente em erros
from fastapi.responses import JSONResponse

# Calendar serve para interpretar os dados brutos dos eventos no formato iCalendar/.ics
from icalendar import Calendar

# Imports do SQLAlchemy, usado para conectar e manipular o banco de dados
from sqlalchemy import create_engine, Column, BigInteger, Text, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker


# Carrega as variáveis definidas no arquivo .env
load_dotenv()

# Lê o Apple ID do arquivo .env
APPLE_ID = os.getenv("APPLE_ID")

# Lê a senha específica de app da Apple, não é a senha normal da conta Apple
APPLE_APP_PASSWORD = os.getenv("APPLE_APP_PASSWORD")

# Lê a URL do servidor CalDAV da Apple
# Se não existir no .env, usa https://caldav.icloud.com/ como padrão
CALDAV_URL = os.getenv("CALDAV_URL", "https://caldav.icloud.com/")

# Lê a URL de conexão com o banco de dados, no seu caso, Supabase/Postgres
DATABASE_URL = os.getenv("DATABASE_URL")


# Se não existir DATABASE_URL no .env, o sistema para e avisa o erro
# Isso evita rodar o backend sem conexão configurada com o banco
if not DATABASE_URL:
    raise ValueError("DATABASE_URL precisa estar no arquivo .env")


# Cria a aplicação FastAPI
# Esse título aparece na documentação automática da API
app = FastAPI(title="Apple Calendar Backend")


# ============================================================
# BANCO DE DADOS
# ============================================================

# Cria a "engine" de conexão com o banco
# A engine é o motor que o SQLAlchemy usa para conversar com o Supabase/Postgres
#
# pool_pre_ping=True testa se a conexão está viva antes de usar
# Isso evita alguns erros quando a conexão fica parada por muito tempo
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

# Cria uma fábrica de sessões do banco
# Cada vez que precisamos consultar ou salvar algo, abrimos uma sessão
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Base é usada pelo SQLAlchemy para mapear classes Python para tabelas do banco
Base = declarative_base()


# Classe que representa a tabela calendar_events no banco de dados
# Cada objeto CalendarEvent representa uma linha da tabela
class CalendarEvent(Base):
    # Nome da tabela no banco
    __tablename__ = "calendar_events"

    # ID interno do banco
    # primary_key=True indica que é a chave principal
    id = Column(BigInteger, primary_key=True, index=True)

    # UID é o identificador único do evento vindo do calendário Apple
    # unique=True evita duplicar o mesmo evento no banco
    uid = Column(Text, unique=True, index=True, nullable=True)

    # Título/nome do evento
    title = Column(Text, nullable=False)

    # Data do evento, armazenada como texto
    # Exemplo: "2026-05-17"
    data = Column(Text, nullable=False)

    # Hora do evento, armazenada como texto
    # Exemplo: "14:30" ou "Dia inteiro"
    time = Column(Text, nullable=False)

    # Notas/descrição do evento
    notes = Column(Text, nullable=True)

    # Nome do calendário de origem
    # Exemplo: "Trabalho"
    calendar = Column(Text, nullable=True)

    # Data/hora em que o registro foi criado no banco
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Data/hora em que o registro foi atualizado pela última vez
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# Esta linha criaria as tabelas automaticamente no banco, caso não existissem
# Como você já criou a tabela direto no Supabase, pode deixar comentado
# para evitar problemas na inicialização.
#
# Base.metadata.create_all(bind=engine)


# ============================================================
# APPLE CALENDAR / CALDAV
# ============================================================

def get_caldav_client():
    """
    Cria e retorna um cliente CalDAV autenticado no iCloud.

    Esse cliente é o responsável por acessar os calendários da conta Apple.
    """

    # Verifica se as credenciais da Apple existem no .env
    if not APPLE_ID or not APPLE_APP_PASSWORD:
        raise ValueError("APPLE_ID e APPLE_APP_PASSWORD precisam estar no arquivo .env")

    # Cria o cliente CalDAV usando:
    # url = servidor CalDAV do iCloud
    # username = Apple ID
    # password = senha específica de app da Apple
    client = caldav.DAVClient(
        url=CALDAV_URL,
        username=APPLE_ID,
        password=APPLE_APP_PASSWORD,
    )

    return client


def parse_event(raw_event: Any, calendar_name: str) -> Dict[str, Any]:
    """
    Recebe um evento bruto vindo do iCloud e transforma em um dicionário limpo.

    O evento vem em formato iCalendar/.ics.
    Aqui extraímos:
    - uid
    - title
    - data
    - time
    - notes
    - calendar
    """

    # Pega os dados brutos do evento
    ical_data = raw_event.data

    # Converte o texto iCalendar em um objeto que o Python consegue navegar
    parsed_calendar = Calendar.from_ical(ical_data)

    # Percorre os componentes do arquivo iCalendar
    # Um arquivo pode ter vários componentes, mas queremos o VEVENT
    for component in parsed_calendar.walk():
        if component.name == "VEVENT":
            # UID único do evento
            uid = component.get("uid")

            # Nome/título do evento
            # No padrão iCalendar, esse campo se chama summary
            title = component.get("summary")

            # Notas/descrição do evento
            # No padrão iCalendar, esse campo se chama description
            notes = component.get("description")

            # Data/hora de início do evento
            # No padrão iCalendar, esse campo se chama dtstart
            start = component.get("dtstart")

            # Pega o valor real de data/hora, se existir
            start_value = start.dt if start else None

            # Se o valor for datetime, significa que o evento tem data e hora
            if isinstance(start_value, datetime):
                # Formata a data como ano-mês-dia
                event_date = start_value.strftime("%Y-%m-%d")

                # Formata a hora como hora:minuto
                event_time = start_value.strftime("%H:%M")

            # Se não for datetime, pode ser evento de dia inteiro
            else:
                # Para evento de dia inteiro, normalmente vem apenas uma data
                event_date = str(start_value) if start_value else ""

                # Marca o horário como "Dia inteiro"
                event_time = "Dia inteiro"

            # Retorna os dados já limpos e prontos para salvar no banco
            return {
                "uid": str(uid) if uid else None,
                "title": str(title) if title else "Sem título",
                "data": event_date,
                "time": event_time,
                "notes": str(notes) if notes else None,
                "calendar": calendar_name,
            }

    # Se não encontrar nenhum VEVENT, retorna um dicionário vazio
    return {}


def save_event_to_database(event_data: Dict[str, Any]):
    """
    Salva um evento no banco de dados.

    Se o evento já existir, atualiza.
    Se não existir, cria um novo registro.

    Isso evita duplicar eventos quando o endpoint /sync-events roda várias vezes.
    """

    # Abre uma sessão com o banco
    db = SessionLocal()

    try:
        # Pega o UID do evento
        uid = event_data.get("uid")

        # Variável para armazenar um evento já existente, se houver
        existing_event = None

        # Se o evento tiver UID, procuramos no banco se ele já existe
        if uid:
            existing_event = db.query(CalendarEvent).filter(
                CalendarEvent.uid == uid
            ).first()

        # Se já existe, atualiza os dados
        if existing_event:
            existing_event.title = event_data.get("title")
            existing_event.data = event_data.get("data")
            existing_event.time = event_data.get("time")
            existing_event.notes = event_data.get("notes")
            existing_event.calendar = event_data.get("calendar")

        # Se não existe, cria um novo registro
        else:
            new_event = CalendarEvent(
                uid=event_data.get("uid"),
                title=event_data.get("title"),
                data=event_data.get("data"),
                time=event_data.get("time"),
                notes=event_data.get("notes"),
                calendar=event_data.get("calendar"),
            )

            # Adiciona o novo evento na sessão
            db.add(new_event)

        # Confirma a transação no banco
        db.commit()

    except Exception:
        # Se der qualquer erro, desfaz a transação
        db.rollback()
        raise

    finally:
        # Fecha a conexão/sessão com o banco
        db.close()


# ============================================================
# ROTAS DA API
# ============================================================

@app.get("/")
def health_check():
    """
    Rota simples para testar se o backend está rodando.
    """

    return {
        "status": "ok",
        "message": "Apple Calendar Backend rodando"
    }


@app.get("/calendars")
def list_calendars():
    """
    Lista todos os calendários encontrados na conta iCloud.

    Essa rota é útil para verificar se a conexão com a Apple está funcionando
    e para conferir os nomes exatos dos calendários.
    """

    # Cria cliente CalDAV
    client = get_caldav_client()

    # Pega o usuário principal da conta iCloud
    principal = client.principal()

    # Lista os calendários disponíveis
    calendars = principal.calendars()

    result = []

    # Monta a resposta com nome e URL de cada calendário
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
    Busca eventos no calendário Trabalho, mas NÃO salva no banco.

    Use essa rota para testar se os eventos estão sendo encontrados.
    """

    # Cria cliente CalDAV
    client = get_caldav_client()

    # Pega o usuário principal da conta
    principal = client.principal()

    # Lista os calendários
    calendars = principal.calendars()

    # Define a data inicial da busca
    # Começa um dia antes para evitar problemas de fuso/horário
    start_date = datetime.now(timezone.utc) - timedelta(days=1)

    # Define a data final da busca
    end_date = start_date + timedelta(days=days)

    # Lista onde os eventos encontrados serão armazenados
    events: List[Dict[str, Any]] = []

    # Percorre todos os calendários da conta
    for calendar in calendars:
        # Busca somente o calendário chamado "Trabalho"
        # Se não for "Trabalho", pula para o próximo
        if calendar.name.strip().lower() != "trabalho":
            continue

        try:
            # Busca os eventos dentro do intervalo de datas
            raw_events = calendar.date_search(
                start=start_date,
                end=end_date,
                expand=True,
            )

            # Processa cada evento bruto
            for raw_event in raw_events:
                event_data = parse_event(raw_event, calendar.name)

                # Se conseguiu extrair dados do evento, adiciona na lista
                if event_data:
                    events.append(event_data)

        except Exception as error:
            # Se der erro ao buscar eventos, retorna erro 500 com detalhes
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Erro ao buscar eventos no calendário Trabalho",
                    "details": str(error),
                },
            )

    # Ordena os eventos pelo título
    events = sorted(events, key=lambda item: item.get("title") or "")

    # Retorna os eventos encontrados
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
    """
    Busca eventos no calendário Trabalho e salva no banco de dados.

    Essa é a rota principal da integração:
    iCloud Calendar → Backend → Supabase
    """

    # Cria cliente CalDAV
    client = get_caldav_client()

    # Pega o usuário principal da conta
    principal = client.principal()

    # Lista os calendários
    calendars = principal.calendars()

    # Define a data inicial da busca
    start_date = datetime.now(timezone.utc) - timedelta(days=1)

    # Define a data final da busca
    end_date = start_date + timedelta(days=days)

    # Lista para armazenar os eventos salvos
    saved_events: List[Dict[str, Any]] = []

    # Percorre todos os calendários da conta
    for calendar in calendars:
        # Filtra apenas o calendário "Trabalho"
        if calendar.name.strip().lower() != "trabalho":
            continue

        try:
            # Busca eventos no intervalo definido
            raw_events = calendar.date_search(
                start=start_date,
                end=end_date,
                expand=True,
            )

            # Processa e salva cada evento encontrado
            for raw_event in raw_events:
                event_data = parse_event(raw_event, calendar.name)

                if event_data:
                    # Salva ou atualiza o evento no banco
                    save_event_to_database(event_data)

                    # Adiciona na lista de resposta
                    saved_events.append(event_data)

        except Exception as error:
            # Se der erro, retorna JSON com mensagem e detalhes
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Erro ao sincronizar eventos no banco de dados",
                    "details": str(error),
                },
            )

    # Ordena os eventos pelo título
    saved_events = sorted(saved_events, key=lambda item: item.get("title") or "")

    # Retorna o resumo da sincronização
    return {
        "message": "Eventos sincronizados com sucesso",
        "calendar": "Trabalho",
        "days": days,
        "total_saved": len(saved_events),
        "events": saved_events,
    }


@app.get("/database-events")
def get_database_events():
    """
    Consulta os eventos que já estão salvos no banco de dados.
    """

    # Abre uma sessão com o banco
    db = SessionLocal()

    try:
        # Busca todos os eventos, ordenando do mais recente para o mais antigo
        events = db.query(CalendarEvent).order_by(CalendarEvent.id.desc()).all()

        result = []

        # Transforma cada linha do banco em um dicionário para retornar como JSON
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
        # Fecha a sessão do banco mesmo se der erro
        db.close()


@app.get("/debug/events")
def debug_events(days: int = 30):
    """
    Rota de debug para investigar eventos brutos vindos do iCloud.

    Ela mostra:
    - quais calendários foram encontrados;
    - quantos eventos cada calendário retornou;
    - uma prévia dos dados brutos dos eventos.

    Use quando a API não encontrar eventos que você acha que deveriam aparecer.
    """

    # Cria cliente CalDAV
    client = get_caldav_client()

    # Pega o usuário principal da conta
    principal = client.principal()

    # Lista calendários
    calendars = principal.calendars()

    # Define período de busca
    start_date = datetime.now(timezone.utc) - timedelta(days=1)
    end_date = datetime.now(timezone.utc) + timedelta(days=days)

    debug_result = []

    # Percorre cada calendário encontrado
    for calendar in calendars:
        # Estrutura inicial de debug para aquele calendário
        item = {
            "calendar": calendar.name,
            "url": str(calendar.url),
            "found": 0,
            "events": [],
            "error": None,
        }

        try:
            # Busca eventos no calendário atual
            raw_events = calendar.date_search(
                start=start_date,
                end=end_date,
                expand=True,
            )

            # Guarda quantos eventos foram encontrados
            item["found"] = len(raw_events)

            # Guarda uma prévia dos 10 primeiros eventos encontrados
            for raw_event in raw_events[:10]:
                item["events"].append({
                    "url": str(raw_event.url),

                    # Mostra só os primeiros 500 caracteres do evento bruto
                    # para não devolver uma resposta gigante
                    "raw_preview": raw_event.data[:500],
                })

        except Exception as error:
            # Se algum calendário der erro, registra o erro nele
            item["error"] = str(error)

        # Adiciona o resultado daquele calendário na resposta final
        debug_result.append(item)

    # Retorna o diagnóstico completo
    return {
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "days": days,
        },
        "calendars": debug_result,
    }