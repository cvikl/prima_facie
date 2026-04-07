"""Deterministic compliance checks: AML scoring, conflict detection, expense estimation."""

from sqlalchemy.orm import Session
from app.models import Customer, Ticket


# --- AML Risk Scoring (ZPPDFT-2 based) ---

def calculate_aml_score(indicators: dict) -> tuple[int, str, list[str]]:
    """
    Returns (score, risk_level, required_documents).
    Rule-based scoring grounded in ZPPDFT-2 risk factors.
    """
    score = 0

    # High-weight customer indicators
    if indicators.get("high_risk_jurisdiction"):
        score += 3
    if indicators.get("sanctioned_country"):
        score += 5
    if indicators.get("complex_ownership"):
        score += 2
    if indicators.get("cash_intensive"):
        score += 2
    if indicators.get("pep_involved"):
        score += 2
    if indicators.get("opaque_fund_source"):
        score += 2

    # Medium-weight indicators
    if indicators.get("novel_structure"):
        score += 1

    # Classify risk
    if score <= 2:
        risk = "GREEN"
    elif score <= 5:
        risk = "ORANGE"
    else:
        risk = "RED"

    # Required documents based on risk level
    docs = [
        "Osebni dokument (ID / potni list)",
        "Dokazilo o naslovu",
        "Izjava o dejanskem lastniku (UBO)",
    ]
    if risk in ("ORANGE", "RED"):
        docs.extend([
            "Dokumentacija o izvoru sredstev",
            "Izjava o poslovnem namenu",
            "Potrdilo o registraciji podjetja",
        ])
    if risk == "RED":
        docs.extend([
            "Poglobljena preveritev (Enhanced Due Diligence)",
            "Odobritev višjega vodstva za sprejem stranke",
            "Načrt stalnega spremljanja poslovanja",
            "Preverjanje na seznamu sankcij EU/UN",
        ])

    return score, risk, docs


# --- Conflict of Interest Check (Multi-level) ---

# Critical industries where representing multiple clients creates conflict risk.
# In these fields, having two clients in the same sector is problematic because:
# - They may be competitors or counterparties
# - Confidential information from one could advantage the other
# - Regulatory proceedings may pit clients against each other
CRITICAL_FIELDS = {
    "BANČNIŠTVO IN FINANCE": "Zastopanje več strank v bančnem/finančnem sektorju lahko povzroči konflikt — stranke so pogosto nasprotne v kreditnih, investicijskih ali regulatornih zadevah.",
    "PREVZEMI IN ZDRUŽITVE": "V M&A transakcijah pogosto zastopamo eno stran — zastopanje več strank v istem sektorju pomeni tveganje, da bosta stranki na nasprotnih straneh prihodnje transakcije.",
    "NEPREMIČNINE, GRADBENIŠTVO IN INFRASTRUKTURA": "Gradbeni in nepremičninski sektor vključuje pogoste spore med investitorji, izvajalci in podizvajalci — zastopanje več strank povečuje tveganje konflikta.",
    "ENERGETIKA": "Energetski sektor je regulatorno intenziven — stranke pogosto tekmujejo za iste koncesije, dovoljenja ali javne razpise.",
    "JAVNO NAROČANJE": "Stranke v javnem naročanju pogosto tekmujejo za iste razpise — zastopanje več ponudnikov je neposredni konflikt interesov.",
    "KONKURENČNO PRAVO": "Konkurenčnopravne zadeve po definiciji vključujejo nasprotujoče si interese med podjetji v istem sektorju.",
    "REGULACIJA S PODROČJA ZDRAVIL": "Farmacevtski sektor vključuje regulatorne postopke kjer stranke tekmujejo za odobritve, patente in tržne deleže.",
    "NALOŽBENI SKLADI": "Investicijski skladi pogosto tekmujejo za iste naložbe — zastopanje več skladov ustvarja tveganje prenosa zaupnih informacij.",
    "INSOLVENČNO PRAVO IN PRESTRUKTURIRANJA": "V insolvenčnih postopkih zastopamo bodisi dolžnika bodisi upnike — zastopanje obeh strani je neposredni konflikt.",
    "TEHNOLOGIJA, MEDIJI IN ELEKTRONSKE KOMUNIKACIJE": "Tehnološki in telekomunikacijski sektor vključuje spore o patentih, licencah in tržnih deležih med konkurenti.",
}


def check_conflicts(
    opposing_parties: list[str],
    db: Session,
    field: str = "",
    customer_name: str = "",
    customer_firm: str = "",
) -> tuple[str, str]:
    """
    Multi-level conflict of interest check.

    Level 1 (RED — conflict): Opposing party matches an existing customer by name.
        → Ticket is BLOCKED. Cannot approve or send. Rejection email auto-generated.

    Level 2 (YELLOW — warning): Client's legal field is a "critical industry" and we
        already represent another client in the same field.
        → Warning for lawyer to review. Not blocked, but flagged.

    Returns (conflict_status, details).
    """
    all_customers = db.query(Customer).all()
    conflicts = []
    warnings = []

    # --- Level 1: Name-based conflict (RED) ---
    if opposing_parties:
        for party in opposing_parties:
            party_lower = party.lower().strip()
            for customer in all_customers:
                cust_name = customer.name.lower().strip()
                cust_firm = (customer.firm_name or "").lower().strip()

                # Exact match
                if party_lower == cust_name or party_lower == cust_firm:
                    conflicts.append(
                        f"KONFLIKT: '{party}' je obstoječa stranka ({customer.name}, {customer.firm_name})"
                    )
                # Partial / fuzzy match
                elif (party_lower in cust_name or cust_name in party_lower or
                      party_lower in cust_firm or cust_firm in party_lower):
                    if len(party_lower) > 3:  # avoid trivial matches
                        warnings.append(
                            f"DELNO UJEMANJE: '{party}' se delno ujema s stranko ({customer.name}, {customer.firm_name})"
                        )

    # --- Level 2: Industry-based conflict (YELLOW) ---
    if field and field in CRITICAL_FIELDS:
        # Check if we have other tickets in the same critical field from different clients
        existing_tickets = (
            db.query(Ticket)
            .filter(Ticket.field == field)
            .filter(Ticket.conflict_status != "conflict")  # ignore already-blocked tickets
            .all()
        )

        other_clients = set()
        current_client = (customer_name or "").lower().strip()
        current_firm = (customer_firm or "").lower().strip()

        for t in existing_tickets:
            t_name = (t.customer_name or "").lower().strip()
            t_firm = (t.customer_firm or "").lower().strip()

            # Skip if same client
            if current_client and (t_name == current_client or t_firm == current_firm):
                continue
            if t_name or t_firm:
                other_clients.add(t.customer_name or t.customer_firm)

        if other_clients:
            client_list = ", ".join(sorted(other_clients))
            reason = CRITICAL_FIELDS[field]
            warnings.append(
                f"INDUSTRIJA: Področje '{field}' je kritično za konflikte. "
                f"Že zastopamo stranke v istem sektorju: {client_list}. {reason}"
            )

    # --- Determine final status ---
    if conflicts:
        return "conflict", "; ".join(conflicts + warnings)
    elif warnings:
        return "warning", "; ".join(warnings)
    return "none", ""


# --- Rejection Email for Blocked Tickets ---

REJECTION_EMAIL_SL = """Zadeva: Odgovor na vašo poizvedbo

Spoštovani{name_greeting},

zahvaljujemo se vam za zaupanje in poizvedbo, ki ste jo naslovili na odvetniško pisarno Jadek & Pensa d.o.o.

Po skrbnem pregledu vaše zadeve moramo žal sporočiti, da vašega primera v tem trenutku ne moremo prevzeti. Razlog za to je potencialni konflikt interesov, ki bi lahko ogrozil našo sposobnost nepristranskega in kakovostnega zastopanja vaših interesov.

Kot odvetniška pisarna smo zavezani najvišjim etičnim standardom, ki vključujejo dolžnost izogibanja nasprotju interesov v skladu z Zakonom o odvetništvu (ZOdv) in Kodeksom odvetniške poklicne etike. Ravno zato vas želimo na to opozoriti pravočasno in transparentno.

Priporočamo vam, da se za pomoč obrnete na drugo ugledne odvetniške pisarne, ki vam bodo lahko nudile kakovostno pravno podporo brez omejitev.

Iskreno se opravičujemo za nevšečnosti in vam želimo vse dobro pri reševanju vaše zadeve.

S spoštovanjem,
Odvetniška pisarna Jadek & Pensa d.o.o.
"""

REJECTION_EMAIL_EN = """Subject: Response to your inquiry

Dear{name_greeting},

Thank you for your trust and for reaching out to the law firm Jadek & Pensa d.o.o.

After careful review of your matter, we regret to inform you that we are unable to take on your case at this time. The reason for this is a potential conflict of interest that could compromise our ability to provide impartial and high-quality representation of your interests.

As a law firm, we are committed to the highest ethical standards, which include the duty to avoid conflicts of interest in accordance with the Slovenian Attorneys Act (ZOdv) and the Code of Professional Ethics for Attorneys. It is precisely for this reason that we wish to inform you of this promptly and transparently.

We recommend that you seek assistance from other reputable law firms that will be able to provide you with quality legal support without limitations.

We sincerely apologize for any inconvenience and wish you all the best in resolving your matter.

Yours sincerely,
Law firm Jadek & Pensa d.o.o.
"""


def generate_rejection_email(customer_name: str, language: str = "sl") -> str:
    """Generate a polite rejection email for blocked (conflict) tickets."""
    if customer_name:
        # Extract surname for greeting
        parts = customer_name.strip().split()
        surname = parts[-1] if parts else ""
        name_greeting = f" gospod/gospa {surname}" if language == "sl" else f" Mr./Ms. {surname}"
    else:
        name_greeting = ""

    if language == "en" or language == "mixed":
        return REJECTION_EMAIL_EN.format(name_greeting=name_greeting).strip()
    return REJECTION_EMAIL_SL.format(name_greeting=name_greeting).strip()


# --- Expense Estimation ---

COMPLEXITY_HOURS = {
    1: (5, 15),
    2: (15, 40),
    3: (40, 100),
}

HOURLY_RATE = 200  # EUR base rate


def estimate_expenses(complexity: int, team_size: int = 2) -> tuple[float, float, float, float]:
    """
    Returns (min_hours, max_hours, min_cost, max_cost).
    """
    min_h, max_h = COMPLEXITY_HOURS.get(complexity, (15, 40))
    min_cost = min_h * HOURLY_RATE
    max_cost = max_h * HOURLY_RATE
    return min_h, max_h, min_cost, max_cost
