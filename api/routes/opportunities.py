from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from api.db import get_db
from api.background_outreach import hunt_email_background

router = APIRouter()

class ApproveRequest(BaseModel):
    ids: list[int]

class RemoveRequest(BaseModel):
    id: int

@router.post("/approve")
def approve_opportunities(req: ApproveRequest, bg_tasks: BackgroundTasks):
    if not req.ids:
        return {"message": "No IDs provided"}
        
    conn = get_db()
    cursor = conn.cursor()
    placeholders = ','.join('?' * len(req.ids))
    cursor.execute(f"UPDATE opportunities SET status = 'approved', email_hunt_status = 'hunting' WHERE id IN ({placeholders})", req.ids)
    conn.commit()
    conn.close()
    
    # Spawn a background task for each approved ID to hunt for emails
    for job_id in req.ids:
        bg_tasks.add_task(hunt_email_background, job_id)
    
    return {"message": f"Approved {len(req.ids)} opportunities and started email hunters."}

@router.get("/email-status/{job_id}")
def get_email_status(job_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT email_hunt_status, recruiter_email, recruiter_name FROM opportunities WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"email_hunt_status": "unknown"}

@router.post("/remove")
def remove_opportunity(req: RemoveRequest):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE opportunities SET status = 'archived' WHERE id = ?", (req.id,))
    conn.commit()
    conn.close()
    
    return {"message": "Opportunity archived."}

@router.get("/approved")
def get_approved_opportunities():
    """Only returns jobs where email was found. Used for the main outreach queue."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM opportunities WHERE status = 'approved' AND email_hunt_status = 'email_found' ORDER BY id ASC")
    jobs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jobs

@router.get("/manual-queue")
def get_manual_queue():
    """Returns jobs that are approved but email was not found. User must manually supply email."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM opportunities WHERE status = 'approved' AND email_hunt_status = 'email_failed' ORDER BY id ASC")
    jobs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jobs
