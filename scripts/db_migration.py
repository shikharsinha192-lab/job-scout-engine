import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "job_scout.db")

# Each column migration is isolated so one existing column doesn't abort the rest.
MIGRATIONS = [
    ("recruiter_name",      "ALTER TABLE opportunities ADD COLUMN recruiter_name TEXT"),
    ("draft_subject",       "ALTER TABLE opportunities ADD COLUMN draft_subject TEXT"),
    ("draft_body",          "ALTER TABLE opportunities ADD COLUMN draft_body TEXT"),
    ("resume_path",         "ALTER TABLE opportunities ADD COLUMN resume_path TEXT"),
    ("email_hunt_status",   "ALTER TABLE opportunities ADD COLUMN email_hunt_status TEXT DEFAULT 'pending'"),
]

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get existing columns so we can skip gracefully
    existing = {col[1] for col in cursor.execute("PRAGMA table_info(opportunities)").fetchall()}

    applied = []
    skipped = []
    for col_name, sql in MIGRATIONS:
        if col_name in existing:
            skipped.append(col_name)
            continue
        try:
            cursor.execute(sql)
            applied.append(col_name)
        except sqlite3.OperationalError as e:
            print(f"  [WARN] Could not add column '{col_name}': {e}")

    if applied:
        conn.commit()
        print(f"Migration applied columns: {applied}")
    if skipped:
        print(f"Migration skipped (already present): {skipped}")
    if not applied and not skipped:
        print("Nothing to migrate.")

    conn.close()

if __name__ == "__main__":
    migrate()
