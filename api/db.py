import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "job_scout.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS opportunities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_title TEXT,
        company TEXT,
        company_clean TEXT,
        job_url TEXT,
        source TEXT,
        posted_date TEXT,
        is_remote INTEGER,
        legitimacy_score INTEGER,
        relevance_score INTEGER,
        outreach_priority TEXT,
        why_relevant TEXT,
        skills_required TEXT,
        recruiter_email TEXT,
        recruiter_name TEXT,
        draft_subject TEXT,
        draft_body TEXT,
        resume_path TEXT,
        email_hunt_status TEXT DEFAULT 'pending',
        model_used TEXT,
        output_confidence TEXT,
        status TEXT DEFAULT 'new',
        batch_tag TEXT,
        geo_mode TEXT,
        company_stage TEXT,
        role_category TEXT,
        seniority_band TEXT,
        custom_pitch_hook TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        outreach_sent_at TEXT,
        replied_at TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS outreach (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        opportunity_id INTEGER,
        email_to TEXT,
        subject TEXT,
        body_preview TEXT,
        sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'sent',
        FOREIGN KEY (opportunity_id) REFERENCES opportunities(id)
    )
    ''')
    
    # Analytics cache for quick dashboard stats
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS analytics_cache (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Execute init on import
init_db()
