import os
import sys
import smtplib
import getpass
import argparse
import json
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from dotenv import load_dotenv

try:
    from google import genai
    from google.genai import types
    has_modern_genai = True
except ImportError:
    import google.generativeai as genai
    has_modern_genai = False

load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.gemini_client import generate_content_with_fallback, trim_prompt, FREE_KEY, PAID_KEY

# Resolves correctly regardless of whether called from scripts/ or api/ directories
_PLAYBOOK_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "email_playbook.md")
_STRATEGIES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "email_strategies.json")
_RESUME_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "resume_base.json")

def _load_playbook():
    try:
        with open(_PLAYBOOK_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"[send_email] WARNING: Could not load email playbook from {_PLAYBOOK_PATH}: {e}")
        return ""

def _load_strategies():
    try:
        with open(_STRATEGIES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[send_email] WARNING: Could not load email strategies from {_STRATEGIES_PATH}: {e}")
        return {"archetypes": []}

def _load_base_resume():
    try:
        if os.path.exists(_RESUME_PATH):
            with open(_RESUME_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"[send_email] WARNING: Could not load base resume from {_RESUME_PATH}: {e}")
    return {}

def classify_and_extract_signals(raw_post_text):
    prompt = f"""You are a professional recruiting coordinator. Analyze the following job post / JD / screenshot transcription and extract key signals for personalizing our outreach.

JOB POST TEXT:
\"\"\"
{raw_post_text}
\"\"\"

Extract the following signals and format them as a valid JSON object:
- post_type: Choose from [linkedin_founder, linkedin_hr, formal_jd, freelance_post, open_call]
- poster_archetype: Choose from [founder, cxo, hr_recruiter, hiring_manager, agency]
- company_stage: Choose from [idea, pre_seed, seed, series_a_b, growth, enterprise, unknown]
- tone_of_post: Choose from [casual_and_conversational, formal_and_structured, visionary, urgent, ambiguous]
- industry: Choose from [d2c, saas, fintech, edtech, health, ecommerce, cross_industry]
- key_skills_wanted: List of main skills wanted (strings)
- primary_challenge: A 1-sentence description of the main problem they want the candidate to solve
- explicit_ask: What they literally asked candidates to do (e.g., "send email with resume", "DM me portfolio")
- red_flags: List of any potential mismatches or strict requirements (e.g., years of experience required)
- best_angle_of_attack: Choose the best strategy archetype from: [builder, operator, bridge, challenger, urgent, contrarian]

Return ONLY a valid JSON object. Do not include markdown code block formatting.
"""
    try:
        result = generate_content_with_fallback(prompt, response_mime_type="application/json")
        if result.get("success"):
            return json.loads(result["text"])
    except Exception as e:
        print(f"[send_email] WARNING: Signal extraction failed: {e}")
    
    # Fallback default signals
    return {
        "post_type": "formal_jd",
        "poster_archetype": "hiring_manager",
        "company_stage": "unknown",
        "tone_of_post": "formal_and_structured",
        "industry": "cross_industry",
        "key_skills_wanted": [],
        "primary_challenge": "Execute performance marketing and growth strategies.",
        "explicit_ask": "send email with resume",
        "red_flags": [],
        "best_angle_of_attack": "operator"
    }

def get_company_insights_via_search(company_name, api_key, model_name="gemini-2.5-flash"):
    prompt = f"""Search the web for current marketing and product signals for {company_name}.
Focus on:
1. What paid ad platforms are they active on (Meta, Google, LinkedIn)?
2. What are the key visual style or hooks of their current ads?
3. Are there any obvious bugs, friction points, or optimization opportunities on their website/landing pages?

Summarize these into 2-3 bullet points of highly specific, actionable observations. Cite real data if found. Do not be generic.
"""
    try:
        if has_modern_genai:
            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}]
                )
            )
            return resp.text.strip()
        else:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            resp = model.generate_content(
                prompt,
                tools='google_search'
            )
            return resp.text.strip()
    except Exception as e:
        print(f"[send_email] WARNING: Search grounding failed for {company_name}: {e}")
        return ""

def draft_cold_email(recruiter_name, company_name, job_title, role_context="", skills_required="", why_relevant=""):
    """
    Gemini-powered strategist and email writer. Analyzes the job post context,
    matches it to a strategic archetype, retrieves live company signals if needed,
    and drafts a bespoke outreach email adhering strictly to universal rules.
    Returns (subject, body) tuple.
    """
    # 1. Load context and config files
    playbook = _load_playbook()
    strategies = _load_strategies()
    base_resume = _load_base_resume()
    
    candidate_name = base_resume.get("personal_info", {}).get("name", "Shikhar Sinha")
    candidate_email = base_resume.get("personal_info", {}).get("email", "shikharsinha192@gmail.com")
    candidate_linkedin = base_resume.get("personal_info", {}).get("linkedin", "https://www.linkedin.com/in/shikharsinha192/")
    
    # 2. Reconstruct raw post text for signal extractor
    raw_post_text = f"Company: {company_name}\nJob Title: {job_title}\nRole Context/Pitch Hook: {role_context}\nSkills Required: {skills_required}\nWhy Relevant: {why_relevant}"
    
    # 3. Stage 1: Extract Signals
    signals = classify_and_extract_signals(raw_post_text)
    strategy_id = signals.get("best_angle_of_attack", "operator")
    
    # Match strategic archetype
    archetype_config = {}
    for arch in strategies.get("archetypes", []):
        if arch["id"] == strategy_id:
            archetype_config = arch
            break
    if not archetype_config:
        archetype_config = strategies.get("archetypes", [{}])[0]
        
    dynamic_title = archetype_config.get("dynamic_title", "AI Native Growth Operator")
    
    # 4. Stage 2: Sourced Insights if Challenger strategy triggered
    search_insights = ""
    if strategy_id == "challenger" and company_name and company_name.lower() != "target company":
        print(f"[send_email] Challenger strategy selected. Sourcing web insights for {company_name}...")
        api_key = FREE_KEY or PAID_KEY
        if api_key:
            search_insights = get_company_insights_via_search(company_name, api_key)
            
    # 5. Build mega-prompt for Strategist + Writer
    prompt = f"""You are a master career coach and elite copywriter. You write highly conversion-focused cold outreach emails to hiring managers and founders.

We are writing a cold email for the following candidate:
- Name: {candidate_name}
- Email: {candidate_email}
- LinkedIn: {candidate_linkedin}
- Target Introduction (Use this as the baseline second sentence): "I'm {candidate_name}, an AI native growth operator with 4+ years of experience, having managed 24+ brands."

We are targeting this job opportunity:
- Company: {company_name}
- Job Title: {job_title}
- Context/Details:
\"\"\"
{raw_post_text}
\"\"\"

Here is the strategic analysis we performed on this post:
- Post Type: {signals.get("post_type")}
- Poster Archetype: {signals.get("poster_archetype")}
- Company Stage: {signals.get("company_stage")}
- Tone of Post: {signals.get("tone_of_post")}
- Primary Challenge: {signals.get("primary_challenge")}
- Best Angle of Attack: {archetype_config.get("name")}
- Archetype Guidelines:
{chr(10).join("  • " + g for g in archetype_config.get("guidelines", []))}
"""

    if search_insights:
        prompt += f"""\nHere are live web observations about the company's current marketing/funnels:
\"\"\"
{search_insights}
\"\"\"
Use these observations to construct the hyper-specific insights for the email.
"""

    prompt += f"""
Here is the email playbook of universal rules you MUST follow:
\"\"\"
{playbook}
\"\"\"

Here is a gold standard example of outreach for this archetype:
- Context: {archetype_config.get("examples", [{}])[0].get("context")}
- Subject: {archetype_config.get("examples", [{}])[0].get("subject")}
- Body:
{archetype_config.get("examples", [{}])[0].get("body")}

Draft the email body and subject line.
Ensure the signature title is exactly: "{dynamic_title}"
Ensure the signature name is exactly: "{candidate_name}"
Ensure the signature email is exactly: "{candidate_email}"
Ensure the signature linkedin link is exactly: "{candidate_linkedin}"

STRICT COMPLIANCE CHECK:
- NO DASHES OF ANY KIND for punctuation (em dashes, en dashes, hyphens for pauses). Use commas or periods.
- NO filler words (moreover, furthermore, thus, therefore).
- NO resume references (e.g. do not say "attached resume").
- NO greeting fluff (no "hope this email finds you well").
- The signature block MUST match the format in the example exactly.

OUTPUT FORMAT: Two sections split by the literal string ---SUBJECT--- on its own line.
Section 1: Full email body (salutation + body + signature)
---SUBJECT---
Section 2: Subject line only
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
        inner_lines = lines[1:] if len(lines) > 1 else lines
        if inner_lines and inner_lines[-1].strip() == "```":
            inner_lines = inner_lines[:-1]
        raw = "\n".join(inner_lines).strip()

    # Parse output
    if "---SUBJECT---" in raw:
        parts = raw.split("---SUBJECT---")
        body = parts[0].strip()
        subject = parts[1].strip() if len(parts) > 1 else f"Outreach — {job_title}"
    else:
        # Fallback: generate a safe subject and body
        subject = f"Outreach — {job_title}"
        body = raw if raw else f"""Hi,\n\nI saw your post for the {job_title} role at {company_name}.\n\nI'm {candidate_name}, an AI native growth operator with 4+ years of experience, having managed 24+ brands.\n\nAfter reading the job description, I am reaching out because my skill set aligns perfectly with this role. My case studies and dashboard builds are documented in my portfolio at https://shikhar-portfolio-marketing.vercel.app.\n\nLet's schedule a call soon to discuss how I can help your team scale.\n\nLooking forward to talking to you guys.\n\nThanks and regards,\n{candidate_name}\n{dynamic_title}\n{candidate_email}\n{candidate_linkedin}"""

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
