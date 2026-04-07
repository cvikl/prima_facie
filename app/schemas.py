from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# --- Request schemas ---

class EmailIngest(BaseModel):
    sender_email: str
    subject: str
    body: str


class N8NEmailWebhook(BaseModel):
    """Format from n8n Gmail trigger HTTP request."""
    name: str  # From field, e.g. "Google <no-reply@accounts.google.com>"
    subject: str
    body: str


class TicketUpdate(BaseModel):
    status: Optional[str] = None
    draft_email: Optional[str] = None
    reviewed_by: Optional[str] = None


# --- Response schemas ---

class UserOut(BaseModel):
    id: int
    acronym: str
    name: str
    workload: float
    fields: list[str] = []

    class Config:
        from_attributes = True


class DeadlineOut(BaseModel):
    description: str
    hours_remaining: float


class AMLIndicatorsOut(BaseModel):
    high_risk_jurisdiction: bool = False
    complex_ownership: bool = False
    cash_intensive: bool = False
    pep_involved: bool = False
    sanctioned_country: bool = False
    opaque_fund_source: bool = False
    novel_structure: bool = False


class TicketListOut(BaseModel):
    id: int
    status: str
    customer_name: Optional[str]
    customer_firm: Optional[str]
    field: Optional[str]
    urgency: str
    conflict_status: str
    aml_risk: str
    summary: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TicketDetailOut(BaseModel):
    id: int
    status: str
    raw_email: str
    sender_email: Optional[str]
    language: str

    # Classification
    field: Optional[str]
    summary: Optional[str]
    urgency: str
    deadlines: Optional[list[dict]]

    # Analysis
    customer_name: Optional[str]
    customer_firm: Optional[str]
    opposing_parties: Optional[list[str]]
    aml_indicators: Optional[dict]
    complexity: int
    unanswered_questions: Optional[list[str]]
    key_facts: Optional[list[str]]

    # Compliance
    conflict_status: str
    conflict_details: Optional[str]
    aml_risk: str
    aml_score: int
    aml_required_documents: Optional[list[str]]

    # Expenses
    estimated_hours_min: Optional[float]
    estimated_hours_max: Optional[float]
    estimated_cost_min: Optional[float]
    estimated_cost_max: Optional[float]

    # Output
    draft_email: Optional[str]
    similar_tickets: Optional[list[dict]]
    legal_references: Optional[dict | list]  # Mini-TFL dict or legacy list format
    assigned_team: list[UserOut] = []

    # Meta
    created_at: datetime
    reviewed_by: Optional[str]
    sent_at: Optional[datetime]

    class Config:
        from_attributes = True
