import os
import sys

# Import local modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts import tailor_resume, generate_pdf, send_email

def main():
    print("STEP 1: PARSE JOB DATA")
    job = {
        "title": "Growth Marketer",
        "company": "Sprinto",
        "salary": "INR 18-30 LPA",
        "rationale": "Your AI-first growth loops and full-funnel automation experience directly map to Sprinto's PLG model."
    }
    print(f"Loaded Listing: {job['title']} at {job['company']}\n")

    print("STEP 2: TAILOR RESUME (ATS Optimization)")
    jd_text = f"Role: {job['title']}\nCompany: {job['company']}\nKey requirements: Growth Marketing, Performance Marketing, paid media budget scaling, GA4/GTM attribution, conversion rate optimization (CRO), automation."
    
    base_json_path = os.path.join("data", "resume_base.json")
    
    # ensure output dirs exist
    os.makedirs(os.path.join("output", "resumes"), exist_ok=True)
    os.makedirs(os.path.join("output", "emails"), exist_ok=True)
    
    tailored_json_path = os.path.join("output", "resumes", f"Shikhar_Sinha_Resume_{job['company']}_test.json")
    
    # Suppress verbose prints from tailor_resume for a clean log
    tailor_resume.tailor_resume(base_json_path, jd_text, tailored_json_path)
    print(f"Resume tailored and saved to JSON format\n")

    print("STEP 3: PDF COMPILATION")
    tailored_pdf_path = os.path.join("output", "resumes", f"Shikhar_Sinha_Resume_{job['company']}_test.pdf")
    generate_pdf.build_pdf(tailored_json_path, tailored_pdf_path)
    print(f"PDF generated using ReportLab and saved to: {tailored_pdf_path}\n")

    print("STEP 4: HR INTELLIGENCE & OUTBOUND EMAIL")
    draft_path = os.path.join("output", "emails", f"Outreach_{job['company']}_test.txt")
    subject, body = send_email.draft_cold_email("", job['company'], job['title'])
    
    with open(draft_path, "w", encoding="utf-8") as f:
         f.write(f"Subject: {subject}\n\n")
         f.write(body)
    print(f"Final Outreach Email drafted based on strict guidelines.")
    print(f"Draft saved to: {draft_path}\n")
    print("TEST PIPELINE COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
