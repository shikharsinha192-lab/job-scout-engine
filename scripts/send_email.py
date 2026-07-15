import os
import sys
import smtplib
import getpass
import argparse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.gemini_client import generate_content_with_fallback, trim_prompt

# Resolves correctly regardless of whether called from scripts/ or api/ directories
_PLAYBOOK_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "email_playbook.md")

def _load_playbook():
    try:
        with open(_PLAYBOOK_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"[send_email] WARNING: Could not load email playbook from {_PLAYBOOK_PATH}: {e}")
        return ""

def draft_cold_email(recruiter_name, company_name, job_title, role_context="", skills_required="", why_relevant=""):
    """
    Gemini-powered email drafter. Reads the playbook and adapts the email
    specifically to the role, company, and context provided.
    Returns (subject, body) tuple.
    """
    playbook = _load_playbook()
    
    # Handle unknown or missing company names gracefully
    is_unknown_company = not company_name or company_name.strip() == "" or company_name.strip().lower() == "target company"
    display_company = "your company" if is_unknown_company else company_name
    
    if recruiter_name and recruiter_name.strip() and recruiter_name.lower() not in ("hiring team", "hiring manager", "recruiter", "unknown"):
        first_name = recruiter_name.split()[0]
        salutation_hint = f"Hi {first_name},"
    elif not is_unknown_company:
        salutation_hint = f"Hi {display_company} Hiring Team,"
    else:
        salutation_hint = "Hi Hiring Team,"
    
    SIGNATURE = os.getenv("SENDER_SIGNATURE", "Your Name\nGrowth Marketing Strategist\nyour.email@example.com\nhttps://www.linkedin.com/in/yourprofile/")
    STATS = os.getenv("SENDER_STATS", "I'm a growth marketer with 4+ years of experience, having managed 20+ brands.")

    role_type_hint = ""
    title_lower = job_title.lower()
    if any(k in title_lower for k in ("growth", "performance", "acquisition", "demand", "paid")):
        role_type_hint = "Lead with CAC reduction, ROAS, paid + AI funnel ownership."
    elif any(k in title_lower for k in ("content", "seo", "social")):
        role_type_hint = "Lead with multi-brand content strategy, AI-assisted production."
    elif any(k in title_lower for k in ("ai", "automation", "ops")):
        role_type_hint = "Lead with AI systems built, martech stack, 60-80% time savings."
    else:
        role_type_hint = "Lead with full-stack marketing + martech ownership, 25+ brands."

    prompt = f"""Draft a cold outreach email for Shikhar Sinha applying to {job_title} at {display_company}.

CANDIDATE STATS: {STATS}
ROLE FOCUS: {role_type_hint}
ROLE CONTEXT / PITCH HOOK: {role_context or 'Not specified'}
SKILLS REQUIRED: {skills_required or 'Not specified'}
WHY RELEVANT: {why_relevant or 'Not specified'}

STRICT RULES:
- Greeting: Start with exactly {salutation_hint} or Hey/Hi [First Name],
- First line: Must state exactly where you found the job post.
- Second line (Intro): MUST say exactly "I'm Shikhar, an AI native growth marketer with 4+ years of experience, having managed 24+ brands."
- CROSS-INDUSTRY RULE: If the job requires an industry Shikhar lacks (e.g., Healthcare), insert: "While most of my experience comes from D2C and B2B brands, the underlying growth principles remain identical: customer acquisition economics, conversion optimization, retention, experimentation, and attribution."
- FOUNDER RULE: If emailing a Founder, replace the storytelling section with 2-3 bullet points of funnel teardowns: "I noticed you're actively scaling paid acquisition. I spent some time reviewing your recent funnel and identified a few highly specific opportunities:\n• [Stellar, hyper-specific insight 1 citing real/recent data]\n• [Stellar, hyper-specific insight 2 citing real/recent data]\nHappy to elaborate if useful." (DO NOT BE GENERIC. DO NOT HALLUCINATE NUMBERS. Use latest real data.)
- Third line (Relevance): If NOT a Founder, MUST include a concise sentence expressing excitement because your background aligns perfectly with the JD.
- Systems & Automation: If NOT a Founder, DO NOT invent stories... weave in these core truths smoothly: "systems first Growth Operator", "rewiring funnels", "combine media buying with AI led backend automation", "handle both marketing and martech". Validate with "up to 13x ROAS" and "20-50% CAC drop". Use smooth transitions.
- Portfolio: Include and integrate the portfolio link (https://shikhar-portfolio-marketing.vercel.app) naturally woven into the body text.
- Tone: Vary sentence lengths. Keep it sharp. No fluff words like "moreover".
- End on an action note (e.g. "Let's schedule a call soon").
- STRICTLY PROHIBITED: Do NOT use ANY dashes for punctuation. No em dashes (—), en dashes (–), or hyphens (-) for pauses. Use commas or periods.
- STRICTLY PROHIBITED: No words like "moreover", "furthermore". No "see resume with deeper breakdowns". No "I hope this email finds you well"., NO "Please find attached", NO "see resume with deeper breakdowns"
- Bullet points: Max 3, and only if absolutely necessary.

OUTPUT FORMAT: Two sections split by the literal string ---SUBJECT--- on its own line.
Section 1: Full email body (salutation + body + CTA + signature)
---SUBJECT---
Section 2: Subject line only (e.g. Growth Marketer - {display_company})
"""

    try:
        result = generate_content_with_fallback(prompt)
        if not result.get("success"):
            print(f"[send_email] WARNING: Gemini call failed for {company_name}/{job_title}: {result.get('error', 'unknown error')}")
        raw = result.get("text", "").strip() if result.get("success") else ""
    except Exception as e:
        print(f"[send_email] ERROR: Exception during Gemini call for {company_name}/{job_title}: {e}")
        raw = ""

    # Strip markdown code fences Gemini may wrap the response in
    if raw.startswith("```"):
        lines = raw.splitlines()
        # Remove first line (``` or ```text etc.) and last line (```)
        inner_lines = lines[1:] if len(lines) > 1 else lines
        if inner_lines and inner_lines[-1].strip() == "```":
            inner_lines = inner_lines[:-1]
        raw = "\n".join(inner_lines).strip()

    # Parse output
    if "---SUBJECT---" in raw:
        parts = raw.split("---SUBJECT---")
        body = parts[0].strip()
        subject_company_suffix = f" at {display_company}" if not is_unknown_company else ""
        subject = parts[1].strip() if len(parts) > 1 else f"Growth & Performance Marketing - {job_title}{subject_company_suffix}"
    else:
        # Fallback: use raw as body, generate a safe subject
        subject_company_suffix = f" at {display_company}" if not is_unknown_company else ""
        body = raw if raw else f"""{salutation_hint}

I noticed your opening for a {job_title} at {display_company} and wanted to reach out.

I'm Shikhar, an AI native growth marketer with 4+ years of experience, having managed 24+ brands.

After reading the job description, I am reaching out because my skill set aligns perfectly with this role.

I am a systems first Growth Operator rewiring underperforming funnels to drive measurable P&L impact. I combine high intent media buying, retention, and full funnel growth with AI led backend automation, handling both marketing and martech. I build systems that acquire and retain customers profitably, using AI heavily to prototype ideas, generate creatives, and automate workflows so teams move 10x faster.

You can see my case studies and portfolio at https://shikhar-portfolio-marketing.vercel.app.

Let's schedule a call soon to discuss how I can help your team scale efficiently.

Looking forward to talking to you guys.

Thanks and regards,
Shikhar Sinha
Growth & Performance Marketing Strategist
shikharsinha192@gmail.com
https://www.linkedin.com/in/shikharsinha192/"""
        subject = f"Growth & Performance Marketing - {job_title}{subject_company_suffix}"

    # Hard enforce: strip all em dash variants and bare double-hyphen from both body and subject
    for field_ref in ["body", "subject"]:
        val = body if field_ref == "body" else subject
        val = val.replace("\u2014", " ")   # em dash
        val = val.replace("\u2013", " ")   # en dash
        val = val.replace("--", " ")       # bare double-hyphen
        if field_ref == "body":
            body = val
        else:
            subject = val

    return subject, body


def secure_smtp_send(sender_email, sender_password, receiver_email, subject, body_text, attachment_path):
    if not os.path.exists(attachment_path):
        print(f"[send_email] Error: Attachment resume file not found at: {attachment_path}")
        return False

    # Create message container
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject

    # Attach body
    msg.attach(MIMEText(body_text, 'plain', 'utf-8'))

    # Attach PDF resume
    try:
        with open(attachment_path, "rb") as f:
            pdf_data = f.read()
            filename = os.path.basename(attachment_path)
            attachment = MIMEApplication(pdf_data, _subtype="pdf")
            attachment.add_header('Content-Disposition', 'attachment', filename=filename)
            msg.attach(attachment)
    except Exception as e:
        print(f"[send_email] Error reading attachment file: {str(e)}")
        return False

    # Secure SMTP session (Gmail)
    try:
        print("[send_email] Establishing secure SMTP connection to smtp.gmail.com...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.ehlo()
        server.starttls()  # Upgrade connection to secure STARTTLS
        server.ehlo()

        print("[send_email] Authenticating credentials...")
        server.login(sender_email, sender_password)

        print("[send_email] Sending secure outreach email...")
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        return True
    except smtplib.SMTPAuthenticationError:
        print("[send_email] SMTP Authentication Failure: Invalid email or App Password.")
        print("[send_email] Ensure you are using a 16-character Gmail App Password (not your primary password).")
        return False
    except Exception as e:
        print(f"[send_email] SMTP Dispatch Error: {str(e)}")
        return False

def orchestrate_draft_and_send(recruiter_name, company_name, job_title, receiver_email, attachment_path, save_draft_path):
    """
    CLI-friendly orchestrator: drafts, previews, and sends a cold email.
    Reads GMAIL_EMAIL and GMAIL_APP_PASSWORD from environment (.env).
    Falls back to interactive prompts if env vars are missing.
    """
    # Draft email — returns (subject, body) tuple
    subject, email_body = draft_cold_email(recruiter_name, company_name, job_title)

    # Save draft locally for tracking/logs
    os.makedirs(os.path.dirname(os.path.abspath(save_draft_path)), exist_ok=True)
    with open(save_draft_path, "w", encoding="utf-8") as f:
        f.write(f"Subject: {subject}\n")
        f.write(f"To: {receiver_email}\n")
        f.write(f"Attachment: {attachment_path}\n")
        f.write("=" * 40 + "\n")
        f.write(email_body)

    # --- HUMAN-IN-THE-LOOP GATE 1: PREVIEW ---
    print("\n" + "=" * 60)
    print("📧 OUTBOUND EMAIL PREVIEW")
    print("=" * 60)
    print(f"To:         {receiver_email}")
    print(f"Subject:    {subject}")
    print(f"Attachment: {attachment_path}")
    print("-" * 60)
    print(email_body)
    print("=" * 60 + "\n")

    approved = input("Do you approve this draft and want to proceed to secure send? [Y/n]: ").strip().lower()
    if approved not in ("", "y", "yes"):
        print(f"Outreach canceled. Draft has been saved locally at: {save_draft_path}")
        return False

    # --- HUMAN-IN-THE-LOOP GATE 2: CREDENTIALS ---
    print("\n🔒 Secure Gmail Outbound Auth")
    print("To dispatch via Gmail, you must enter your credentials.")
    print("Google requires a 16-character 'App Password'. Do not use your primary password.\n")

    env_email = os.environ.get("GMAIL_EMAIL")
    env_password = os.environ.get("GMAIL_APP_PASSWORD")

    sender_email = env_email or input("Enter your Gmail address [shikharsinha192@gmail.com]: ").strip() or "shikharsinha192@gmail.com"

    if env_password:
        print("✓ Loaded GMAIL_APP_PASSWORD from .env config file.")
        sender_password = env_password
    else:
        sender_password = getpass.getpass("Enter your 16-character Gmail App Password (hidden input): ")

    if not sender_password or len(sender_password.strip()) == 0:
        print("Error: App Password cannot be empty.")
        return False

    # Execute secure send
    success = secure_smtp_send(
        sender_email=sender_email.strip(),
        sender_password=sender_password.strip(),
        receiver_email=receiver_email.strip(),
        subject=subject,
        body_text=email_body,
        attachment_path=attachment_path
    )

    if success:
        print(f"\n🚀 DISPATCH SUCCESSFUL!")
        print(f"Email successfully delivered to: {receiver_email}")
        print(f"Resume PDF attachment: {os.path.basename(attachment_path)}")
        return True
    else:
        print("✖ Outreach Dispatch Failed. Please verify credentials and try again.")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Draft and securely dispatch professional cold email outreach.")
    parser.add_argument("--recruiter", default="", help="Hiring contact name")
    parser.add_argument("--company", required=True, help="Company name")
    parser.add_argument("--role", required=True, help="Target job title")
    parser.add_argument("--email", required=True, help="Recipient email address")
    parser.add_argument("--pdf", required=True, help="Path to tailored resume PDF")
    parser.add_argument("--draft", required=True, help="Path to save text draft")
    
    args = parser.parse_args()
    
    orchestrate_draft_and_send(
        recruiter_name=args.recruiter,
        company_name=args.company,
        job_title=args.role,
        receiver_email=args.email,
        attachment_path=args.pdf,
        save_draft_path=args.draft
    )
