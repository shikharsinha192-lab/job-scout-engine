from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from api.db import get_db
from api.background_outreach import hunt_email_background

router = APIRouter()

class ScheduleRequest(BaseModel):
    type: str
    size: int
    freshness_days: int

@router.post("/generate-batch")
def generate_batch(req: ScheduleRequest, bg_tasks: BackgroundTasks):
    # Pull the best unprocessed records from SQLite and approve them as a batch.
    # Also kicks off background email-hunting so jobs can eventually reach the
    # outreach queue (which filters on email_hunt_status = 'email_found').

    conn = get_db()
    cursor = conn.cursor()

    # Filter by freshness
    cursor.execute("""
        SELECT * FROM opportunities
        WHERE status = 'new'
        AND created_at >= datetime('now', ?)
        ORDER BY relevance_score DESC, legitimacy_score DESC
        LIMIT ?
    """, (f'-{req.freshness_days} days', req.size))

    jobs = [dict(row) for row in cursor.fetchall()]

    # Approve and immediately set email_hunt_status = 'hunting' so the
    # background worker knows to process them and they don't stall at 'pending'.
    if jobs:
        ids = [j['id'] for j in jobs]
        placeholders = ','.join('?' * len(ids))
        cursor.execute(
            f"UPDATE opportunities SET status = 'approved', email_hunt_status = 'hunting' WHERE id IN ({placeholders})",
            ids
        )
        conn.commit()

        # Spawn background email-hunter for each job (mirrors /approve endpoint logic)
        for job_id in ids:
            bg_tasks.add_task(hunt_email_background, job_id)

    conn.close()

    return {"message": f"Generated batch of {len(jobs)} jobs, email hunting started.", "jobs": jobs}
