from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, ForeignKey, Table, JSON, Enum
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from app.database import Base


# --- Enums ---

class TicketStatus(str, enum.Enum):
    NEW = "NEW"
    BLOCKED = "BLOCKED"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    SENT = "SENT"
    CLOSED = "CLOSED"


class ConflictStatus(str, enum.Enum):
    NONE = "none"
    WARNING = "warning"
    CONFLICT = "conflict"


class AMLRisk(str, enum.Enum):
    GREEN = "GREEN"
    ORANGE = "ORANGE"
    RED = "RED"


class Urgency(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# --- Association tables ---

user_fields = Table(
    "user_fields",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("field_name", String, primary_key=True),
)

ticket_assigned_users = Table(
    "ticket_assigned_users",
    Base.metadata,
    Column("ticket_id", Integer, ForeignKey("tickets.id"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
)


# --- Models ---

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    acronym = Column(String(4), unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    workload = Column(Float, default=1.0)  # 1=free, 2=normal, 3=overloaded

    fields = relationship("UserField", back_populates="user", cascade="all, delete-orphan")
    assigned_tickets = relationship("Ticket", secondary=ticket_assigned_users, back_populates="assigned_team")


class UserField(Base):
    __tablename__ = "user_fields_detail"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    field_name = Column(String, nullable=False)
    priority = Column(Integer, default=0)  # 0 = primary, 1 = secondary, etc.

    user = relationship("User", back_populates="fields")


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    firm_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    tickets = relationship("Ticket", back_populates="customer")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, default=TicketStatus.NEW.value)
    raw_email = Column(Text, nullable=False)
    sender_email = Column(String, nullable=True)
    language = Column(String, default="sl")

    # Step 1: Classification
    field = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    urgency = Column(String, default=Urgency.MEDIUM.value)
    deadlines = Column(JSON, nullable=True)  # [{"description": "...", "hours_remaining": 48}]

    # Step 2: Deep analysis
    customer_name = Column(String, nullable=True)
    customer_firm = Column(String, nullable=True)
    opposing_parties = Column(JSON, nullable=True)  # ["Company X", "Person Y"]
    aml_indicators = Column(JSON, nullable=True)  # {"high_risk_jurisdiction": false, ...}
    complexity = Column(Integer, default=2)  # 1-3
    unanswered_questions = Column(JSON, nullable=True)  # ["question1", "question2"]
    key_facts = Column(JSON, nullable=True)  # ["fact1", "fact2"]

    # Compliance
    conflict_status = Column(String, default=ConflictStatus.NONE.value)
    conflict_details = Column(Text, nullable=True)
    aml_risk = Column(String, default=AMLRisk.GREEN.value)
    aml_score = Column(Integer, default=0)
    aml_required_documents = Column(JSON, nullable=True)

    # Expense estimation
    estimated_hours_min = Column(Float, nullable=True)
    estimated_hours_max = Column(Float, nullable=True)
    estimated_cost_min = Column(Float, nullable=True)
    estimated_cost_max = Column(Float, nullable=True)

    # Step 3: Generated output
    draft_email = Column(Text, nullable=True)
    similar_tickets = Column(JSON, nullable=True)  # [{"id": 1, "summary": "...", "similarity": 0.85}]
    legal_references = Column(JSON, nullable=True)  # [{law, abbreviation, articles: [{number, title}]}]

    # Relations
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    customer = relationship("Customer", back_populates="tickets")
    assigned_team = relationship("User", secondary=ticket_assigned_users, back_populates="assigned_tickets")

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    reviewed_by = Column(String, nullable=True)
    sent_at = Column(DateTime, nullable=True)
