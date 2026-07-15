import os
import sys
import argparse
import shutil
import time

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.send_email import draft_cold_email
from scripts.email_harvester import hunt_for_emails
from scripts.tailor_resume import tailor_resume
from scripts.generate_pdf import build_pdf

def main():
    parser = argparse.ArgumentParser(description="Batch process jobs into a dispatch queue.")
    parser.add_argument("--start", type=int, default=1, help="Starting Job ID")
    parser.add_argument("--end", type=int, default=15, help="Ending Job ID (inclusive)")
    args = parser.parse_args()

    md_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "filtered_recent_job_listings_1_150.md")
    base_resume = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "resume_base.json")
    
    # Setup Queue Directories
    base_dir = os.path.dirname(os.path.dirname(__file__))
    emails_pending = os.path.join(base_dir, "output", "emails", "pending")
    resumes_pending = os.path.join(base_dir, "output", "resumes", "pending")
    
    os.makedirs(emails_pending, exist_ok=True)
    os.makedirs(resumes_pending, exist_ok=True)
    
    with open(md_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    jobs = []
    for line in lines:
        if line.strip().startswith('|'):
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 3:
                try:
                    job_id = int(parts[1])
                    if args.start <= job_id <= args.end:
                        raw_title_company = parts[2]
                        cleaned = raw_title_company.replace("**", "").strip()
                        split_chars = ["—", "–", "-"]
                        title = cleaned
                        company = "Target Company"
                        
                        for char in split_chars:
                            if char in cleaned:
                                splits = cleaned.split(char, 1)
                                title = splits[0].strip()
                                company = splits[1].strip()
                                break
                                
                        if "(" in company:
                            company = company.split("(", 1)[0].strip()
                            
                        if company != "Target Company":
                            jobs.append({
                                "id": job_id,
                                "title": title,
                                "company": company
                            })
                except ValueError:
                    pass
                    
    # unique jobs and sort by id
    unique_jobs = {j["id"]: j for j in jobs}
    sorted_jobs = [unique_jobs[i] for i in sorted(unique_jobs.keys())]
    
    print(f"Batch Processing {len(sorted_jobs)} jobs (IDs {args.start} to {args.end})...\n")
    
    failed_count = 0
    success_count = 0
    
    for job in sorted_jobs:
        print(f"--- Processing Job #{job['id']}: {job['company']} ---")
        
        # 1. Hunt for emails
        print("Hunting HR emails...")
        found_emails = hunt_for_emails(job["company"])
        if not found_emails:
            failed_count += 1
            print(f"[Skipping] No valid emails found for {job['company']}.\n")
            continue
            
        receiver_str = ", ".join(found_emails)
        company_clean = job['company'].replace(' ', '_').replace('/', '_')
        
        # 2. Tailor Resume JSON
        print("Tailoring ATS Resume via AI...")
        jd_text = f"Role: {job['title']}\nCompany: {job['company']}\nNeeds: Growth Marketing, Automation, CRO, Data-driven Media Buying."
        tailored_json = os.path.join(resumes_pending, f"Resume_{company_clean}.json")
        tailor_resume(base_resume, jd_text, tailored_json)
        
        # 3. Generate PDF
        print("Compiling PDF...")
        tailored_pdf = os.path.join(resumes_pending, f"Resume_{company_clean}.pdf")
        if os.path.exists(tailored_json):
            build_pdf(tailored_json, tailored_pdf)
            
        # 4. Draft Email
        print("Drafting specific outbound email...")
        subject, body = draft_cold_email("", job["company"], job["title"])
        draft_file = os.path.join(emails_pending, f"Outreach_{company_clean}.txt")
        
        with open(draft_file, "w", encoding="utf-8") as f:
            f.write(f"To: {receiver_str}\n")
            f.write(f"Subject: {subject}\n")
            f.write(f"Attachment: {tailored_pdf}\n")
            f.write("="*50 + "\n")
            f.write(body)
            
        success_count += 1
        print(f"[Success] Enqueued into Pending Dispatch Queue!\n")
        
        # Throttle to prevent hitting Gemini's 15 RPM Free Tier limit
        print("Waiting 10 seconds to respect API rate limits...")
        time.sleep(10)
        
    print(f"Batch Complete.")
    print(f"Successfully enqueued: {success_count} jobs")
    print(f"Failed (no emails): {failed_count} jobs")
    print(f"Review them in: {emails_pending}")

if __name__ == "__main__":
    main()
