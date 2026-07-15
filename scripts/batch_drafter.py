import os
import sys

# Import the drafting function directly to bypass interactive CLI prompt
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.send_email import draft_cold_email

campaigns = [
    {
        "dir": "data/campaigns/51_Sprinto",
        "company": "Sprinto",
        "role": "Growth Marketer",
        "recruiter": "Sprinto Hiring Team",
        "email": "careers@sprinto.com", # Snov OSINT timed out, defaulting to general careers inbox
        "pdf": "data/campaigns/51_Sprinto/Shikhar_Sinha_Resume.pdf"
    },
    {
        "dir": "data/campaigns/52_Razorpay",
        "company": "Razorpay",
        "role": "Sr. Associate, Growth Marketing",
        "recruiter": "Razorpay Hiring Team",
        "email": "careers@razorpay.com",
        "pdf": "data/campaigns/52_Razorpay/Shikhar_Sinha_Resume.pdf"
    },
    {
        "dir": "data/campaigns/50_UnitedHealth",
        "company": "UnitedHealth Group",
        "role": "Marketing Specialist",
        "recruiter": "UnitedHealth HR",
        "email": "hr@unitedhealthgroup.com",
        "pdf": "data/campaigns/50_UnitedHealth/Shikhar_Sinha_Resume.pdf"
    }
]

for camp in campaigns:
    print(f"Drafting for {camp['company']}...")
    
    # generate email draft
    subject, body = draft_cold_email(camp['recruiter'], camp['company'], camp['role'])
    
    draft_path = os.path.join(camp['dir'], "OUTBOUND_DRAFT.txt")
    with open(draft_path, "w", encoding="utf-8") as f:
        f.write(f"To: {camp['email']}\n")
        f.write(f"Subject: {subject}\n")
        f.write(f"Attachment: {camp['pdf']}\n")
        f.write("="*40 + "\n")
        f.write(body)
    
    print(f"  -> Saved draft at {draft_path}")

print("All drafts generated successfully!")
