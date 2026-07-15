import sqlite3
import os
import sys
import time
import re
import asyncio
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db
from scripts.email_harvester import hunt_for_emails
from scripts.send_email import draft_cold_email, secure_smtp_send

load_dotenv()

async def run_auto_pilot():
    print("\nStarting Job Scout Auto Pilot...")
    
    env_email = os.environ.get("GMAIL_EMAIL")
    env_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not env_email or not env_password:
        print("❌ CRITICAL: Missing GMAIL_EMAIL or GMAIL_APP_PASSWORD in .env. Exiting.")
        return

    conn = get_db()
    cursor = conn.cursor()
    
    # Selection Criteria:
    # 1. status = 'new'
    # 2. relevance_score >= 80 (Relaxed slightly)
    # 3. legitimacy_score >= 75 (Relaxed slightly)
    # 4. posted_date within the last 7 days
    # 5. LIMIT 50 to cap the maximum sends in one session
    query = """
        SELECT * FROM opportunities 
        WHERE status = 'new' 
          AND relevance_score >= 80 
          AND legitimacy_score >= 75
          AND date(posted_date) >= date('now', '-10 days')
        ORDER BY relevance_score DESC, legitimacy_score DESC
        LIMIT 50
    """
    
    cursor.execute(query)
    jobs = cursor.fetchall()
    print(f"🎯 Found {len(jobs)} highly qualified jobs posted in the last week.")

    if not jobs:
        print("😴 No jobs match the Auto Pilot criteria. Exiting.")
        conn.close()
        return

    successful_sends = 0

    for idx, job in enumerate(jobs, 1):
        job_id = job['id']
        company = job['company']
        title = job['job_title']
        skills = job['skills_required'] or ''
        why = job['why_relevant'] or ''
        custom_pitch = job['custom_pitch_hook'] or ''
        company_clean = (job['company_clean'] or company).replace(" ", "_")
        
        print(f"\n--- [{idx}/{len(jobs)}] Processing {company} - {title} ---")
        
        # --- Step 1: Hunt Email ---
        # Strip YC batch markers like (W26), (S20), etc.
        clean_name = re.sub(r'\([WS]\d+\)', '', company).strip()
        target_company = job['company_clean'] or clean_name
        
        existing_email = job['recruiter_email']
        if existing_email:
            print(f"🔍 Using existing email from database: {existing_email}")
            emails = [existing_email]
        else:
            print(f"🔍 Hunting for HR email using clean name: {target_company}...")
            emails = await asyncio.to_thread(hunt_for_emails, target_company)
        
        if not emails or len(emails) == 0:
            print(f"⚠️ No email found for {target_company}. Sending to manual queue.")
            cursor.execute("UPDATE opportunities SET email_hunt_status = 'email_failed' WHERE id = ?", (job_id,))
            conn.commit()
            continue
            
        found_email = emails[0]
        
        # Basic name inference
        name_guess = "Hiring Team"
        local_part = found_email.split("@")[0]
        if "." in local_part:
            parts = local_part.split(".")
            name_guess = " ".join(p.capitalize() for p in parts)
            
        print(f"✅ Found email: {found_email} (Assumed Name: {name_guess})")
        
        # --- Step 2: Use Master Resume ---
        print(f"📄 Using Master Resume...")
        master_pdf = os.getenv("MASTER_RESUME_PDF_PATH", "master_resume.pdf")
        if not os.path.exists(master_pdf):
            print(f"❌ CRITICAL: Master resume not found at {master_pdf}. Sending to manual queue.")
            cursor.execute("UPDATE opportunities SET email_hunt_status = 'email_failed' WHERE id = ?", (job_id,))
            conn.commit()
            continue

        # --- Step 3: Draft Email ---
        print(f"✍️ Drafting email via Gemini...")
        try:
            def generate_draft():
                return draft_cold_email(
                    recruiter_name=name_guess,
                    company_name=target_company,
                    job_title=title,
                    role_context=custom_pitch,
                    skills_required=skills,
                    why_relevant=why
                )
            
            subject, body = await asyncio.to_thread(generate_draft)
        except Exception as e:
            print(f"❌ Failed to draft email for {company}: {e}")
            continue
            
        # --- Step 4: Send SMTP ---
        print(f"🚀 Sending email to {found_email}...")
        success = await asyncio.to_thread(
            secure_smtp_send,
            sender_email=env_email.strip(),
            sender_password=env_password.strip(),
            receiver_email=found_email,
            subject=subject,
            body_text=body,
            attachment_path=master_pdf
        )
        
        if success:
            successful_sends += 1
            print(f"✅ Email sent successfully to {company}!")
            
            # DB Updates
            cursor.execute("""
                UPDATE opportunities 
                SET recruiter_email = ?, 
                    recruiter_name = ?, 
                    email_hunt_status = 'email_found',
                    resume_path = ?,
                    draft_subject = ?,
                    draft_body = ?,
                    status = 'outreach_sent', 
                    outreach_sent_at = datetime('now') 
                WHERE id = ?
            """, (found_email, name_guess, master_pdf, subject, body, job_id))
            
            cursor.execute("""
                INSERT INTO outreach (opportunity_id, email_to, subject, status)
                VALUES (?, ?, ?, 'sent')
            """, (job_id, found_email, subject))
            
            conn.commit()
            
            # If we still have more to process, sleep to avoid spam filters
            if idx < len(jobs):
                print("⏳ Sleeping for 72 seconds to prevent spam flagging (50 emails/hour pace)...")
                await asyncio.sleep(72)
        else:
            print(f"❌ SMTP failed for {company}.")
            
    print(f"\n🎉 Auto Pilot Finished! Successfully sent {successful_sends} tailored emails.")
    conn.close()

if __name__ == "__main__":
    asyncio.run(run_auto_pilot())
