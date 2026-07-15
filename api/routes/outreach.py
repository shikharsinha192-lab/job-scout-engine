from fastapi import APIRouter
from pydantic import BaseModel
import sys
import os
import asyncio

from api.stream import log
from api.db import get_db

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.send_email import draft_cold_email, secure_smtp_send

router = APIRouter()

class SendRequest(BaseModel):
    subject: str
    body: str
    manual_email: str = ""  # Allow manual override for email_failed jobs

@router.post("/prepare/{id}")
async def prepare_outreach(id: int):
    """
    Stage 3: Only generates the email draft (1 fast Gemini call, ~2-3s).
    Resume/PDF was already built in Stage 2 background worker.
    This is the only thing on the on-demand critical path.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM opportunities WHERE id = ?", (id,))
    job = cursor.fetchone()

    if not job:
        conn.close()
        return {"error": "Opportunity not found"}

    company = job['company']
    title = job['job_title']
    recruiter_name = job['recruiter_name'] or ''
    recruiter_email = job['recruiter_email'] or ''
    resume_path = job['resume_path'] or ''
    skills = job['skills_required'] or ''
    why = job['why_relevant'] or ''

    # If draft already generated (user re-opens modal), return cached version instantly. Free.
    if job['draft_body'] and resume_path and os.path.exists(resume_path):
        conn.close()
        filename = os.path.basename(resume_path)
        return {
            "recruiter_email": recruiter_email,
            "recruiter_name": recruiter_name,
            "subject": job['draft_subject'],
            "body": job['draft_body'],
            "resume_filename": filename,
            "resume_path": resume_path
        }

    # Only on-demand step: generate email draft (1 Gemini call)
    def generate_draft():
        return draft_cold_email(
            recruiter_name=recruiter_name,
            company_name=company,
            job_title=title,
            skills_required=skills,
            why_relevant=why
        )

    subject, body = await asyncio.to_thread(generate_draft)

    # Cache it so re-opening modal is instant
    cursor.execute("""
        UPDATE opportunities SET draft_subject = ?, draft_body = ? WHERE id = ?
    """, (subject, body, id))
    conn.commit()
    conn.close()

    filename = os.path.basename(resume_path) if resume_path else "Resume not ready yet"
    return {
        "recruiter_email": recruiter_email,
        "recruiter_name": recruiter_name,
        "subject": subject,
        "body": body,
        "resume_filename": filename,
        "resume_path": resume_path
    }

from scripts.tailor_resume import tailor_resume
from scripts.generate_pdf import build_pdf

from fastapi import BackgroundTasks

def process_and_send_background(job_id: int, company: str, company_clean: str, job_title: str, skills: str, why: str, to_email: str, subject: str, body: str, env_email: str, env_password: str, initial_resume_path: str):
    conn = get_db()
    cursor = conn.cursor()
    
    resume_path = initial_resume_path or ''
    
    # --- JUST-IN-TIME RESUME GENERATION ---
    if not resume_path or not os.path.exists(resume_path):
        company_clean_str = (company_clean or company).replace(" ", "_")
        base_resume = os.path.join("data", "resume_base.json")
        tailored_json = os.path.join("output", "resumes", f"Shikhar_Sinha_{company_clean_str}.json")
        tailored_pdf = os.path.join("output", "resumes", f"Shikhar_Sinha_{company_clean_str}.pdf")
        jd_mock = f"Role: {job_title}\nCompany: {company}\nRequired: {skills}\nRelevance: {why}"

        os.makedirs(os.path.dirname(tailored_json), exist_ok=True)
        try:
            tailor_resume(base_resume, jd_mock, tailored_json)
            build_pdf(tailored_json, tailored_pdf)
            resume_path = tailored_pdf
            cursor.execute("UPDATE opportunities SET resume_path = ? WHERE id = ?", (resume_path, job_id))
            conn.commit()
        except Exception as e:
            print(f"[send_outreach] JIT Resume Failed for Job {job_id}: {e}")
            cursor.execute("UPDATE opportunities SET status = 'outreach_failed' WHERE id = ?", (job_id,))
            conn.commit()
            conn.close()
            return

    # --- SEND EMAIL ---
    success = secure_smtp_send(
        sender_email=env_email.strip(),
        sender_password=env_password.strip(),
        receiver_email=to_email,
        subject=subject,
        body_text=body,
        attachment_path=resume_path
    )

    if success:
        cursor.execute("""
            INSERT INTO outreach (opportunity_id, email_to, subject, status)
            VALUES (?, ?, ?, 'sent')
        """, (job_id, to_email, subject))
        cursor.execute("UPDATE opportunities SET status = 'outreach_sent', outreach_sent_at = datetime('now') WHERE id = ?", (job_id,))
        print(f"[send_outreach] Successfully dispatched email for Job {job_id}")
    else:
        cursor.execute("UPDATE opportunities SET status = 'outreach_failed' WHERE id = ?", (job_id,))
        print(f"[send_outreach] SMTP failed for Job {job_id}")

    conn.commit()
    conn.close()


@router.post("/send/{id}")
async def send_outreach(id: int, req: SendRequest, background_tasks: BackgroundTasks):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM opportunities WHERE id = ?", (id,))
    job = cursor.fetchone()

    if not job:
        conn.close()
        return {"error": "Opportunity not found"}

    env_email = os.environ.get("GMAIL_EMAIL")
    env_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not env_email or not env_password:
        conn.close()
        return {"error": "Missing GMAIL_EMAIL or GMAIL_APP_PASSWORD in .env"}

    # Support manual email override for email_failed jobs
    to_email = req.manual_email.strip() if req.manual_email else (job['recruiter_email'] or '').strip()
    if not to_email or "@" not in to_email:
        conn.close()
        return {"error": "No valid recipient email found."}

    # Mark as processing immediately so it disappears from the UI queue
    cursor.execute("UPDATE opportunities SET status = 'outreach_processing' WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    # Hand off to background task
    background_tasks.add_task(
        process_and_send_background,
        job_id=id,
        company=job['company'],
        company_clean=job['company_clean'],
        job_title=job['job_title'],
        skills=job['skills_required'] or '',
        why=job['why_relevant'] or '',
        to_email=to_email,
        subject=req.subject,
        body=req.body,
        env_email=env_email,
        env_password=env_password,
        initial_resume_path=job['resume_path']
    )

    return {"message": "Email processing started in background!"}

