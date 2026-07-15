import asyncio
from api.db import get_db
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.email_harvester import hunt_for_emails
from scripts.tailor_resume import tailor_resume
from scripts.generate_pdf import build_pdf

async def hunt_email_background(opportunity_id: int):
    """
    Stage 2 background worker:
    1. Hunts for recruiter email (free, no tokens).
    2. If email found, immediately generates the tailored resume + PDF in the background.
    By doing this here, the /prepare endpoint only needs to call Gemini for the email draft
    (1 fast call, ~2-3s) instead of doing everything on the critical path.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM opportunities WHERE id = ?", (opportunity_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return

    company = row['company']
    job_title = row['job_title']
    company_clean = (row['company_clean'] or company).replace(" ", "_")
    skills = row['skills_required'] or ''
    why = row['why_relevant'] or ''

    # --- Step 1: Hunt Email (free, no tokens) ---
    emails = await asyncio.to_thread(hunt_for_emails, company)

    if emails and len(emails) > 0:
        found_email = emails[0]
        # Basic name inference
        name_guess = "Hiring Team"
        local_part = found_email.split("@")[0]
        if "." in local_part:
            parts = local_part.split(".")
            name_guess = " ".join(p.capitalize() for p in parts)

        cursor.execute("""
            UPDATE opportunities
            SET recruiter_email = ?, recruiter_name = ?, email_hunt_status = 'email_found'
            WHERE id = ?
        """, (found_email, name_guess, opportunity_id))
        conn.commit()
        # --- Step 2: Tailor Resume + Build PDF in background ---
        base_resume = os.path.join("data", "resume_base.json")
        tailored_json = os.path.join("output", "resumes", f"Shikhar_Sinha_{company_clean}.json")
        tailored_pdf = os.path.join("output", "resumes", f"Shikhar_Sinha_{company_clean}.pdf")
        jd_mock = f"Role: {job_title}\nCompany: {company}\nRequired: {skills}\nRelevance: {why}"

        def build_resume():
            os.makedirs(os.path.dirname(tailored_json), exist_ok=True)
            tailor_resume(base_resume, jd_mock, tailored_json)
            build_pdf(tailored_json, tailored_pdf)
            return tailored_pdf

        try:
            pdf_path = await asyncio.to_thread(build_resume)
            cursor.execute("""
                UPDATE opportunities SET resume_path = ? WHERE id = ?
            """, (pdf_path, opportunity_id))
            conn.commit()
        except Exception as e:
            print(f"[Background] Resume generation failed for {company}: {e}")

    else:
        # Email not found: mark as email_failed. This job goes to the Manual Queue.
        cursor.execute("""
            UPDATE opportunities
            SET email_hunt_status = 'email_failed'
            WHERE id = ?
        """, (opportunity_id,))
        conn.commit()

    conn.close()

