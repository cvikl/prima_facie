"""
Orchestrator: chains LLM calls with DB lookups and compliance checks.
Email → Step 1 (classify) → DB lookups → Step 2 (analyze) → compliance → Step 3 (draft) → Ticket
"""

from sqlalchemy.orm import Session
from app.models import Ticket, User, UserField, Customer
from app.llm_client import parse_intent, summarize
from app.compliance import calculate_aml_score, check_conflicts, estimate_expenses, generate_rejection_email
from app.prompts import STEP1_SYSTEM_PROMPT, STEP2_SYSTEM_PROMPT, build_step3_prompt
from app.vector_store import find_similar, add_ticket
from app.legal_references import get_legal_references


async def process_email(raw_email: str, sender_email: str, subject: str, db: Session) -> Ticket:
    """Full orchestration pipeline. Returns a populated Ticket."""

    full_email = f"Zadeva: {subject}\n\n{raw_email}"

    # --- Step 1: Classify ---
    step1 = await parse_intent(STEP1_SYSTEM_PROMPT, full_email)

    field = step1.get("field", "")
    summary = step1.get("summary", "")
    urgency = step1.get("urgency", "medium")
    deadlines = step1.get("deadlines", [])
    language = step1.get("language", "sl")

    # --- DB Lookup: find team for this field ---
    team_candidates = (
        db.query(User)
        .join(UserField, User.id == UserField.user_id)
        .filter(UserField.field_name == field)
        .order_by(UserField.priority, User.workload)
        .all()
    )

    # Pick top 2-3 with lowest workload
    assigned = sorted(team_candidates, key=lambda u: (u.workload, ))[:3]

    team_info = []
    for u in assigned:
        user_fields = [uf.field_name for uf in u.fields]
        team_info.append({
            "name": u.name,
            "acronym": u.acronym,
            "fields": user_fields,
            "workload": u.workload,
        })

    # --- Step 2: Deep analysis ---
    step2_input = f"{full_email}\n\nKlasifikacija:\nPodročje: {field}\nPovzetek: {summary}\nNujnost: {urgency}"
    step2 = await parse_intent(STEP2_SYSTEM_PROMPT, step2_input)

    customer_name = step2.get("customer_name", "")
    customer_firm = step2.get("customer_firm")
    opposing_parties = step2.get("opposing_parties", [])
    aml_indicators = step2.get("aml_indicators", {})
    complexity = step2.get("complexity", 2)
    unanswered_questions = step2.get("unanswered_questions", [])
    key_facts = step2.get("key_facts", [])

    # --- Conflict check (deterministic) ---
    conflict_status, conflict_details = check_conflicts(
        opposing_parties, db,
        field=field,
        customer_name=customer_name,
        customer_firm=customer_firm or "",
    )

    # --- AML scoring (deterministic, ZPPDFT-2) ---
    aml_score, aml_risk, aml_docs = calculate_aml_score(aml_indicators)

    # --- Expense estimation (deterministic) ---
    min_h, max_h, min_cost, max_cost = estimate_expenses(complexity, len(assigned))

    # --- Save/find customer ---
    customer = None
    if customer_name:
        customer = db.query(Customer).filter(
            (Customer.name.ilike(f"%{customer_name}%")) |
            (Customer.email == sender_email)
        ).first()
        if not customer:
            customer = Customer(
                name=customer_name,
                firm_name=customer_firm,
                email=sender_email,
            )
            db.add(customer)
            db.flush()

    # --- Vector DB: find similar past tickets ---
    ticket_data = {
        "field": field,
        "summary": summary,
        "urgency": urgency,
        "language": language,
        "unanswered_questions": unanswered_questions,
        "key_facts": key_facts,
    }
    similar_tickets = find_similar(ticket_data, n_results=3)

    # Enrich similar tickets with customer info for past-case references
    for st in similar_tickets:
        past_ticket = db.query(Ticket).filter(Ticket.id == st["id"]).first()
        if past_ticket:
            st["customer_name"] = past_ticket.customer_name or ""
            st["customer_firm"] = past_ticket.customer_firm or ""

    # --- Mini-TFL: Legal references (deterministic, no external API) ---
    legal_refs = get_legal_references(
        field=field,
        aml_indicators=aml_indicators,
        aml_risk=aml_risk,
        raw_email=full_email,
        key_facts=key_facts,
    )

    # --- Step 3: Generate draft email (or rejection if conflict) ---
    if conflict_status == "conflict":
        draft_email = generate_rejection_email(customer_name, language)
    else:
        step3_prompt = build_step3_prompt(ticket_data, team_info, similar_tickets)
        draft_email = await summarize(step3_prompt, full_email)

    # --- Build ticket ---
    ticket = Ticket(
        status="BLOCKED" if conflict_status == "conflict" else "NEW",
        raw_email=raw_email,
        sender_email=sender_email,
        language=language,
        field=field,
        summary=summary,
        urgency=urgency,
        deadlines=deadlines,
        customer_name=customer_name,
        customer_firm=customer_firm,
        opposing_parties=opposing_parties,
        aml_indicators=aml_indicators,
        complexity=complexity,
        unanswered_questions=unanswered_questions,
        key_facts=key_facts,
        conflict_status=conflict_status,
        conflict_details=conflict_details,
        aml_risk=aml_risk,
        aml_score=aml_score,
        aml_required_documents=aml_docs,
        estimated_hours_min=min_h,
        estimated_hours_max=max_h,
        estimated_cost_min=min_cost,
        estimated_cost_max=max_cost,
        draft_email=draft_email,
        similar_tickets=similar_tickets,
        legal_references=legal_refs,
        customer_id=customer.id if customer else None,
    )

    db.add(ticket)
    db.flush()

    # Assign team
    for u in assigned:
        ticket.assigned_team.append(u)

    db.commit()
    db.refresh(ticket)

    # --- Embed ticket into vector DB for future similarity search ---
    add_ticket(ticket.id, ticket_data)

    return ticket
