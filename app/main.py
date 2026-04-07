from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import asyncio

from app.database import get_db, engine, Base, SessionLocal
from app.models import Ticket, User, UserField
from app.schemas import EmailIngest, N8NEmailWebhook, TicketUpdate, TicketListOut, TicketDetailOut, UserOut
import re
from app.orchestrator import process_email
from app.seed import seed_database

# Create tables & seed on startup
Base.metadata.create_all(bind=engine)
seed_database()

app = FastAPI(title="Prima Facie", description="AI Legal Intake System for Jadek & Pensa")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Static files & SPA ---

@app.get("/")
async def serve_spa():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")


# --- Health ---

@app.get("/health")
async def health():
    return {"status": "ok", "service": "prima_facie"}


# --- Ticket ingestion ---

def _parse_email_from_field(from_field: str) -> str:
    """Extract email address from 'Name <email@example.com>' format."""
    # Try to extract email from angle brackets
    match = re.search(r'<([^>]+)>', from_field)
    if match:
        return match.group(1)
    # If no brackets, check if it's already just an email
    if '@' in from_field:
        return from_field.strip()
    return from_field


@app.post("/tickets/ingest", response_model=TicketDetailOut)
async def ingest_email(payload: EmailIngest, db: Session = Depends(get_db)):
    """Receive an email and run the full LLM orchestration pipeline."""
    ticket = await process_email(
        raw_email=payload.body,
        sender_email=payload.sender_email,
        subject=payload.subject,
        db=db,
    )
    return _ticket_to_detail(ticket, db)


@app.get("/webhook/n8n")
async def webhook_n8n_info():
    """Info endpoint - use POST to send data."""
    return {
        "status": "ok",
        "message": "n8n webhook is active. Use POST method with JSON body containing: name, subject, body",
        "example": {
            "name": "John Doe <john@example.com>",
            "subject": "Email subject",
            "body": "Email content"
        }
    }


async def _process_email_background(sender_email: str, subject: str, body: str):
    """Process email in background - runs after response is sent."""
    db = SessionLocal()
    try:
        await process_email(
            raw_email=body,
            sender_email=sender_email,
            subject=subject,
            db=db,
        )
        print(f"[OK] Processed email from {sender_email}: {subject}")
    except Exception as e:
        print(f"[ERROR] Failed to process email from {sender_email}: {e}")
    finally:
        db.close()


@app.post("/webhook/n8n")
async def webhook_n8n(payload: N8NEmailWebhook, background_tasks: BackgroundTasks):
    """Webhook endpoint for n8n Gmail trigger integration.
    
    Returns immediately and processes email in background.
    
    Expects:
    - name: From field (e.g., "John Doe <john@example.com>")
    - subject: Email subject
    - body: Email body/snippet
    """
    sender_email = _parse_email_from_field(payload.name)
    
    # Queue for background processing
    background_tasks.add_task(
        _process_email_background,
        sender_email,
        payload.subject,
        payload.body,
    )
    
    return {
        "status": "queued",
        "message": "Email received and queued for processing",
        "sender_email": sender_email,
        "subject": payload.subject,
    }


@app.post("/webhook/n8n/sync", response_model=TicketDetailOut)
async def webhook_n8n_sync(payload: N8NEmailWebhook, db: Session = Depends(get_db)):
    """Synchronous webhook - waits for full processing (may timeout)."""
    sender_email = _parse_email_from_field(payload.name)
    
    ticket = await process_email(
        raw_email=payload.body,
        sender_email=sender_email,
        subject=payload.subject,
        db=db,
    )
    return _ticket_to_detail(ticket, db)


# --- Ticket CRUD ---

@app.get("/tickets", response_model=list[TicketListOut])
async def list_tickets(
    status: str | None = None,
    field: str | None = None,
    urgency: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Ticket).order_by(Ticket.created_at.desc())
    if status:
        query = query.filter(Ticket.status == status)
    if field:
        query = query.filter(Ticket.field == field)
    if urgency:
        query = query.filter(Ticket.urgency == urgency)
    return query.all()


@app.get("/tickets/{ticket_id}", response_model=TicketDetailOut)
async def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return _ticket_to_detail(ticket, db)


@app.patch("/tickets/{ticket_id}", response_model=TicketDetailOut)
async def update_ticket(ticket_id: int, payload: TicketUpdate, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if payload.status:
        # Block sending if conflict is active
        if payload.status == "APPROVED" and ticket.conflict_status == "conflict":
            raise HTTPException(
                status_code=400,
                detail="Cannot approve ticket with active conflict of interest. Resolve conflict first.",
            )
        ticket.status = payload.status

    if payload.draft_email is not None:
        ticket.draft_email = payload.draft_email

    if payload.reviewed_by:
        ticket.reviewed_by = payload.reviewed_by

    if payload.status == "SENT":
        ticket.sent_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(ticket)
    return _ticket_to_detail(ticket, db)


@app.post("/tickets/{ticket_id}/send", response_model=TicketDetailOut)
async def send_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.conflict_status == "conflict":
        raise HTTPException(status_code=400, detail="Cannot send — active conflict of interest.")
    if ticket.status not in ("APPROVED", "IN_REVIEW"):
        raise HTTPException(status_code=400, detail=f"Ticket must be APPROVED before sending. Current: {ticket.status}")

    ticket.status = "SENT"
    ticket.sent_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ticket)
    return _ticket_to_detail(ticket, db)


# --- Users ---

@app.get("/users", response_model=list[UserOut])
async def list_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.name).all()
    result = []
    for u in users:
        result.append(UserOut(
            id=u.id,
            acronym=u.acronym,
            name=u.name,
            workload=u.workload,
            fields=[uf.field_name for uf in u.fields],
        ))
    return result


# --- Helpers ---

def _ticket_to_detail(ticket: Ticket, db: Session) -> TicketDetailOut:
    team = []
    for u in ticket.assigned_team:
        team.append(UserOut(
            id=u.id,
            acronym=u.acronym,
            name=u.name,
            workload=u.workload,
            fields=[uf.field_name for uf in u.fields],
        ))

    return TicketDetailOut(
        id=ticket.id,
        status=ticket.status,
        raw_email=ticket.raw_email,
        sender_email=ticket.sender_email,
        language=ticket.language,
        field=ticket.field,
        summary=ticket.summary,
        urgency=ticket.urgency,
        deadlines=ticket.deadlines,
        customer_name=ticket.customer_name,
        customer_firm=ticket.customer_firm,
        opposing_parties=ticket.opposing_parties,
        aml_indicators=ticket.aml_indicators,
        complexity=ticket.complexity,
        unanswered_questions=ticket.unanswered_questions,
        key_facts=ticket.key_facts,
        conflict_status=ticket.conflict_status,
        conflict_details=ticket.conflict_details,
        aml_risk=ticket.aml_risk,
        aml_score=ticket.aml_score,
        aml_required_documents=ticket.aml_required_documents,
        estimated_hours_min=ticket.estimated_hours_min,
        estimated_hours_max=ticket.estimated_hours_max,
        estimated_cost_min=ticket.estimated_cost_min,
        estimated_cost_max=ticket.estimated_cost_max,
        draft_email=ticket.draft_email,
        similar_tickets=ticket.similar_tickets,
        legal_references=ticket.legal_references,
        assigned_team=team,
        created_at=ticket.created_at,
        reviewed_by=ticket.reviewed_by,
        sent_at=ticket.sent_at,
    )
