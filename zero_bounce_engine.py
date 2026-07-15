import re
import os
import requests
import dns.resolver
from dotenv import load_dotenv
from email_validator import validate_email, EmailNotValidError

# Load environment variables
env_path = r"C:\Users\91639\Documents\antigravity\job-scout-engine\.env"
load_dotenv(dotenv_path=env_path)

ABSTRACT_API_KEY = os.getenv("ABSTRACT_API_KEY", "")

# Standard patterns for fallback check
FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "zoho.com",
    "protonmail.com", "icloud.com", "gmx.com", "yandex.com", "mail.com"
}

def verify_syntax(email: str) -> bool:
    """
    Validates email syntax using the robust email-validator library (RFC compliant).
    """
    try:
        validate_email(email, check_deliverability=False)
        return True
    except EmailNotValidError:
        return False

def get_mx_records(domain: str) -> list:
    """
    Retrieves the MX records for a domain using dnspython.
    Returns a sorted list of mail exchange server hostnames.
    """
    try:
        answers = dns.resolver.resolve(domain, 'MX')
        # Sort MX records by preference (lower is higher priority)
        sorted_answers = sorted(answers, key=lambda r: r.preference)
        return [str(r.exchange).rstrip('.').lower() for r in sorted_answers]
    except Exception as e:
        # No MX records found or resolution failure
        return []

def fingerprint_mail_host(mx_records: list) -> str:
    """
    Identifies the email hosting provider based on MX record fingerprints.
    Useful for identifying Google Workspace or Microsoft 365 domains.
    """
    if not mx_records:
        return "Unknown (No MX)"
        
    for mx in mx_records:
        if "google.com" in mx or "googlemail.com" in mx or "aspmx" in mx:
            return "Google Workspace"
        elif "outlook.com" in mx or "outlook.com" in mx or "messaging.microsoft.com" in mx:
            return "Microsoft Office 365"
        elif "secureserver.net" in mx:
            return "GoDaddy Smart Host"
        elif "zoho.com" in mx:
            return "Zoho Mail"
        elif "protection.outlook.com" in mx:
            return "Microsoft Exchange Online"
            
    return "Private/Custom Mail Server"

def check_abstract_api(email: str) -> dict:
    """
    Queries the Abstract API for real-time verification and catch-all detection.
    """
    if not ABSTRACT_API_KEY:
        return {"error": "Abstract API Key is missing"}
        
    try:
        url = f"https://emailreputation.abstractapi.com/v1/?api_key={ABSTRACT_API_KEY}&email={email}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API HTTP Error {response.status_code}"}
    except Exception as e:
        return {"error": f"API Connection Failed: {str(e)}"}

def verify_email(email: str) -> dict:
    """
    Master verification pipeline combining syntax, MX records, hosting provider fingerprinting,
    and third-party API intelligence to categorize email deliverability.
    """
    email = email.strip().lower()
    
    # 1. Syntax Check
    if not verify_syntax(email):
        return {
            "email": email,
            "status": "UNDELIVERABLE",
            "reason": "Invalid syntax format",
            "host": "Unknown",
            "is_catchall": False,
            "score": 0.0
        }
        
    domain = email.split('@')[1]
    
    # 2. DNS MX Records Check
    mx_records = get_mx_records(domain)
    if not mx_records:
        return {
            "email": email,
            "status": "UNDELIVERABLE",
            "reason": f"No valid MX records found for domain: {domain}",
            "host": "Unknown",
            "is_catchall": False,
            "score": 0.0
        }
        
    host_provider = fingerprint_mail_host(mx_records)
    
    # 3. Third-party API Verification (Abstract API)
    api_res = check_abstract_api(email)
    
    if "error" in api_res:
        # Fallback to local MX verification if API fails/runs out of credits
        is_free = domain in FREE_EMAIL_DOMAINS
        return {
            "email": email,
            "status": "CATCH_ALL" if not is_free else "DELIVERABLE",
            "reason": f"Local MX verified. API Check bypassed ({api_res['error']})",
            "host": host_provider,
            "is_catchall": not is_free,
            "score": 0.5 if not is_free else 0.8
        }
        
    # Parse API response
    deliverability = api_res.get("email_deliverability", {}).get("status")
    is_catchall = api_res.get("email_quality", {}).get("is_catchall", False)
    score = api_res.get("email_quality", {}).get("score", 0.0)
    is_disposable = api_res.get("email_quality", {}).get("is_disposable", False)
    is_role = api_res.get("email_quality", {}).get("is_role", False)
    
    if is_disposable:
        return {
            "email": email,
            "status": "UNDELIVERABLE",
            "reason": "Disposable email address",
            "host": host_provider,
            "is_catchall": is_catchall,
            "score": score
        }
        
    if deliverability == "deliverable":
        if is_catchall:
            return {
                "email": email,
                "status": "CATCH_ALL",
                "reason": "Accepts all emails at domain level (Potential risk of soft/hard bounce)",
                "host": host_provider,
                "is_catchall": True,
                "score": score
            }
        return {
            "email": email,
            "status": "DELIVERABLE",
            "reason": "API Confirmed Deliverable",
            "host": host_provider,
            "is_catchall": False,
            "score": score
        }
    elif deliverability == "undeliverable":
        return {
            "email": email,
            "status": "UNDELIVERABLE",
            "reason": "API Confirmed Undeliverable (Hard Bounce guaranteed)",
            "host": host_provider,
            "is_catchall": is_catchall,
            "score": score
        }
    elif deliverability == "risky":
        return {
            "email": email,
            "status": "RISKY",
            "reason": "API marked deliverability as risky or suspicious",
            "host": host_provider,
            "is_catchall": is_catchall,
            "score": score
        }
    else:
        # Fallback for "unknown" status
        if is_catchall:
            return {
                "email": email,
                "status": "CATCH_ALL",
                "reason": "Accept-all domain with unknown recipient validation",
                "host": host_provider,
                "is_catchall": True,
                "score": score
            }
        return {
            "email": email,
            "status": "RISKY",
            "reason": f"API returned unknown/unverifiable status: {deliverability}",
            "host": host_provider,
            "is_catchall": is_catchall,
            "score": score
        }

if __name__ == "__main__":
    # Diagnostic test cases
    test_emails = [
        "test@gmail.com",
        "hr@example.com",
        "invalid.test.email.12345@google.com",
        "nonexistent@example.club"
    ]
    print("--- Running Zero Bounce Verification Tests ---")
    for email in test_emails:
        print(f"\nVerifying: {email}")
        res = verify_email(email)
        print(f"Status: {res['status']}")
        print(f"Host: {res['host']}")
        print(f"Reason: {res['reason']}")
        print(f"Score: {res['score']}")
