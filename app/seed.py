"""Seed the database with lawyer data from the Excel file."""

from app.database import engine, SessionLocal, Base
from app.models import User, UserField, Customer

# Lawyer-to-field assignments (anonymized for public repo)
FIELD_ASSIGNMENTS = {
    "DELOVNO PRAVO": ["IRPE", "NIBA", "ANOŠ"],
    "BANČNIŠTVO IN FINANCE": ["ANJA", "NAME", "OŽME"],
    "DAVČNO PRAVO": ["DORO", "VEKN", "MIPJ"],
    "ENERGETIKA": ["ANJA", "JULE"],
    "TEHNOLOGIJA, MEDIJI IN ELEKTRONSKE KOMUNIKACIJE": ["MIPO", "JULE", "ALJA"],
    "INSOLVENČNO PRAVO IN PRESTRUKTURIRANJA": ["OŽME", "ANJA", "NAME"],
    "INTELEKTUALNA LASTNINA": ["SAJE", "NESE", "EVGO"],
    "JAVNO NAROČANJE": ["GRKO", "BOLE", "PAPE"],
    "KOMERCIALNE POGODBE": ["SAJE", "JAZA", "EVGO"],
    "KONKURENČNO PRAVO": ["PAPE", "JAZA", "ALCA"],
    "KORPORACIJSKO PRAVO": ["ANJA", "SAJE", "NAME"],
    "MIGRACIJSKO PRAVO": ["ANOŠ", "NIBA", "IRPE"],
    "NALOŽBENI SKLADI": ["ANJA"],
    "NEPREMIČNINE, GRADBENIŠTVO IN INFRASTRUKTURA": ["GRKO", "PAPE", "BOLE", "EVGO"],
    "PREPREČEVANJE IN REŠEVANJE SPOROV": ["MIPO", "JULE", "BOLE", "IRPE"],
    "PREVZEMI IN ZDRUŽITVE": ["OŽME", "ANJA", "NAME", "PAPE"],
    "REGULACIJA S PODROČJA ZDRAVIL": ["SAJE", "EVGO"],
    "VARSTVO OSEBNIH PODATKOV": ["NESE", "MIPO"],
}

LAWYERS = {
    # Names anonymized for public repo — replace with real names in private deployment
    "IRPE": ("Lawyer A", 2.0),
    "ANJA": ("Lawyer B", 3.0),
    "DORO": ("Lawyer C", 2.5),
    "MIPO": ("Lawyer D", 1.5),
    "OŽME": ("Lawyer E", 2.0),
    "SAJE": ("Lawyer F", 2.0),
    "GRKO": ("Lawyer G", 1.0),
    "PAPE": ("Lawyer H", 1.0),
    "NIBA": ("Lawyer I", 3.0),
    "NAME": ("Lawyer J", 2.5),
    "VEKN": ("Lawyer K", 3.0),
    "JULE": ("Lawyer L", 2.5),
    "NESE": ("Lawyer M", 2.0),
    "JAZA": ("Lawyer N", 3.0),
    "EVGO": ("Lawyer O", 2.5),
    "BOLE": ("Lawyer P", 2.5),
    "ANOŠ": ("Lawyer Q", 1.5),
}

# Note: MIPJ and ALJA and ALCA appear in field assignments but not in the lawyer list.
# We'll create placeholder entries for them.
EXTRA_LAWYERS = {
    "MIPJ": ("Lawyer R", 2.0),
    "ALJA": ("Lawyer S", 2.0),
    "ALCA": ("Lawyer T", 2.0),
}


def seed_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Check if already seeded
        if db.query(User).count() > 0:
            print("Database already seeded. Skipping.")
            return

        # Create all lawyers
        all_lawyers = {**LAWYERS, **EXTRA_LAWYERS}
        user_objects = {}

        for acronym, (name, workload) in all_lawyers.items():
            user = User(acronym=acronym, name=name, workload=workload)
            db.add(user)
            db.flush()
            user_objects[acronym] = user

        # Assign fields to lawyers
        for field_name, acronyms in FIELD_ASSIGNMENTS.items():
            for priority, acronym in enumerate(acronyms):
                if acronym in user_objects:
                    user_field = UserField(
                        user_id=user_objects[acronym].id,
                        field_name=field_name,
                        priority=priority,
                    )
                    db.add(user_field)

        # Seed some existing customers for conflict-of-interest checks
        # (based on the test scenarios in the brief)
        # Anonymized demo customers for conflict-of-interest testing
        demo_customers = [
            Customer(name="Acme Corp", firm_name="Acme Corp", email="info@acme-example.com"),
            Customer(name="Jane Doe", firm_name="FlowData d.o.o.", email="jane@flowdata-example.com"),
            Customer(name="Target Company d.o.o.", firm_name="Target Company d.o.o.", email="info@target-example.com"),
        ]
        for c in demo_customers:
            db.add(c)

        db.commit()
        print(f"Seeded {len(user_objects)} lawyers, {len(FIELD_ASSIGNMENTS)} fields, {len(demo_customers)} demo customers.")

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
