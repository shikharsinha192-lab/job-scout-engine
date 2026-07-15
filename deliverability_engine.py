import os
import requests
from bs4 import BeautifulSoup
import urllib.parse
import dns.resolver
import json
import time
import re
from dotenv import load_dotenv
from google import genai
from google.genai import types
from zero_bounce_engine import verify_email

# Load environment
env_path = r"C:\Users\91639\Documents\antigravity\job-scout-engine\.env"
load_dotenv(dotenv_path=env_path)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY_PAID") or os.getenv("GEMINI_API_KEY_FREE")

def get_company_info_gemini(company_name):
    """
    Uses Gemini API with Google Search Grounding to reliably discover
    the domain and LinkedIn contacts (Founder/CEO and HR/recruiter) of a company.
    This bypasses traditional scraper blocking and captchas.
    """
    if not GEMINI_API_KEY:
        print("[Deliverability Engine] Warning: Gemini API key missing. Bypassing AI Search.")
        return None
        
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    Please search Google and find:
    1. The official website domain of the company: "{company_name}".
    2. The full name and exact role of the Founder, CEO, or Co-Founder of "{company_name}".
    3. The full name and exact role of the HR Manager, Recruiter, Talent Acquisition, or Marketing Head of "{company_name}".
    
    Return the response strictly as a JSON block with this format:
    ```json
    {{
        "domain": "companydomain.com",
        "founder": {{
            "name": "First Last",
            "role": "Founder & CEO"
        }},
        "hr": {{
            "name": "First Last",
            "role": "HR Manager"
        }}
    }}
    ```
    If a role cannot be found, set its value to null.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}]
            )
        )
        
        # Parse JSON from markdown fences
        json_match = re.search(r"```json\s*(.*?)\s*```", response.text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response.text.strip()
            
        return json.loads(json_str)
    except Exception as e:
        print(f"[Deliverability Engine] Gemini Search Grounding Error: {e}")
        return None

def ddg_search(query):
    """
    Fallback DuckDuckGo HTML search.
    """
    url = "https://html.duckduckgo.com/html/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0"}
    try:
        res = requests.post(url, data={'q': query}, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        results = []
        for a in soup.find_all('a', class_='result__snippet'):
            title_tag = a.parent.parent.find('h2', class_='result__title')
            title = title_tag.get_text(strip=True) if title_tag else "No Title"
            link = a.get('href')
            if link and 'uddg=' in link:
                link = urllib.parse.unquote(link.split('uddg=')[1].split('&')[0])
            snippet = a.get_text(strip=True)
            results.append({"title": title, "url": link, "snippet": snippet})
        return results
    except Exception as e:
        print(f"DDG Error: {e}")
        return []

def get_linkedin_contacts_fallback(company_name):
    """
    Fallback LinkedIn contacts harvester using DDG search.
    """
    query = f'site:linkedin.com/in/ "{company_name}" AND ("Founder" OR "CEO" OR "HR" OR "Talent" OR "Recruiter" OR "Head of Marketing" OR "VP Marketing")'
    results = ddg_search(query)
    
    founder = None
    hr = None
    
    for r in results:
        title = r['title'].lower()
        name_part = r['title'].split('-')[0].strip()
        if "linkedin" in name_part.lower():
            continue
        
        if not founder and any(x in title for x in ['founder', 'ceo', 'co-founder']):
            founder = {"name": name_part, "role": "Founder"}
        elif not hr and any(x in title for x in ['hr', 'talent', 'recruiter', 'people', 'marketing']):
            hr = {"name": name_part, "role": "HR/Marketing"}
            
        if founder and hr:
            break
            
    return {"founder": founder, "hr": hr}

def get_real_domain_fallback(company_name):
    """
    Fallback domain resolver using DDG search.
    """
    results = ddg_search(f'"{company_name}" official website')
    bad_domains = ['linkedin', 'facebook', 'glassdoor', 'indeed', 'justdial', 'crunchbase', 'ambitionbox', 'instagram', 'twitter']
    
    for r in results:
        url = r['url']
        if not url:
            continue
        domain = urllib.parse.urlparse(url).netloc.replace("www.", "")
        if not any(bad in domain for bad in bad_domains) and '.' in domain:
            return domain
    return f"{company_name.lower().replace(' ', '')}.com"

def verify_domain_http(domain):
    """
    Checks if a domain is active.
    """
    try:
        res = requests.head(f"http://{domain}", timeout=5, allow_redirects=True)
        return res.status_code < 400
    except:
        try:
            res = requests.get(f"http://{domain}", timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            return res.status_code < 400
        except:
            return False

def generate_email_candidates(name, domain):
    """
    Generates standard corporate email candidates.
    """
    parts = name.strip().split()
    first = parts[0].lower()
    last = parts[-1].lower() if len(parts) > 1 else ""
    
    candidates = []
    if last:
        candidates.append(f"{first}.{last}@{domain}")
        candidates.append(f"{first}{last}@{domain}")
        candidates.append(f"{first[0]}{last}@{domain}")
    candidates.append(f"{first}@{domain}")
    return candidates

def has_mx_record(domain):
    """
    Checks if MX records exist.
    """
    try:
        records = dns.resolver.resolve(domain, 'MX')
        return len(records) > 0
    except:
        return False

def verify_email_snov(email):
    """
    Backward-compatible wrapper function for snov verification.
    """
    res = verify_email(email)
    status = res.get("status")
    
    if status == "DELIVERABLE":
        return "valid"
    elif status == "CATCH_ALL":
        return "accept_all"
    elif status == "RISKY":
        return "unverifiable"
    else:
        return "invalid"

def process_company(company_name):
    """
    Orchestrates the entire discovery and validation pipeline.
    Uses Gemini Search Grounding as primary search, falling back to DDG scraping.
    Verifies all candidates using zero_bounce_engine.
    """
    print(f"\n=============================")
    print(f"PROCESSING: {company_name}")
    print(f"=============================")
    
    # 1. Try AI-powered discovery first
    print("[Discovery] Running AI Search Grounding...")
    info = get_company_info_gemini(company_name)
    
    domain = None
    contacts = {"founder": None, "hr": None}
    
    if info:
        domain = info.get("domain")
        founder_info = info.get("founder")
        hr_info = info.get("hr")
        
        if founder_info and founder_info.get("name"):
            contacts["founder"] = {"name": founder_info["name"], "role": founder_info.get("role", "Founder")}
        if hr_info and hr_info.get("name"):
            contacts["hr"] = {"name": hr_info["name"], "role": hr_info.get("role", "HR Manager")}
            
        print(f"  -> Domain found: {domain}")
        print(f"  -> Founder found: {contacts['founder']}")
        print(f"  -> HR/Other found: {contacts['hr']}")
    
    # 2. Fallback to scraping if AI fails or returns empty contacts
    if not domain:
        print("[Discovery] Fallback: Finding Domain via Web Scraping...")
        domain = get_real_domain_fallback(company_name)
        print(f"  -> Fallback Domain: {domain}")
        
    if not contacts["founder"] and not contacts["hr"]:
        print("[Discovery] Fallback: Sourcing Contacts via Web Scraping...")
        contacts = get_linkedin_contacts_fallback(company_name)
        print(f"  -> Fallback Founder: {contacts['founder']}")
        print(f"  -> Fallback HR: {contacts['hr']}")
        
    if not contacts["founder"] and not contacts["hr"]:
        print("❌ FAIL: Could not discover any human contacts.")
        return None
        
    # 3. Domain HTTP verification
    print("[Domain Gate] Verifying domain activity...")
    if not verify_domain_http(domain):
        print(f"❌ FAIL: Domain {domain} is not resolving or active.")
        return None
    print("  -> Domain verified active.")
        
    # 4. MX Record Check
    print("[MX Gate] Checking MX Records...")
    if not has_mx_record(domain):
        print(f"❌ FAIL: Domain {domain} has no valid MX records. Hard bounce guaranteed.")
        return None
    print("  -> MX Records found.")

    # 5. Email Candidates Verification
    print("[Verification Gate] Verifying Email Candidates...")
    verified_targets = []
    
    for key, contact in contacts.items():
        if not contact:
            continue
        print(f"  -> Checking {contact['name']} ({contact['role']})...")
        candidates = generate_email_candidates(contact['name'], domain)
        
        found_valid = False
        for email in candidates:
            res = verify_email(email)
            status = res.get("status")
            host_provider = res.get("host", "Unknown")
            reason = res.get("reason", "")
            
            print(f"     - {email} : {status} (Host: {host_provider}, Reason: {reason})")
            
            if status == "DELIVERABLE":
                verified_targets.append({
                    "name": contact['name'], 
                    "role": contact['role'], 
                    "email": email, 
                    "confidence": "High (Valid)",
                    "host": host_provider
                })
                found_valid = True
                break
            elif status == "CATCH_ALL":
                # Segregate catch-all as risky
                verified_targets.append({
                    "name": contact['name'], 
                    "role": contact['role'], 
                    "email": email, 
                    "confidence": "Risky (Catch-All)",
                    "host": host_provider
                })
                print(f"     ⚠️ WARNING: {email} is a Catch-All server (Risk of bounce).")
                
        if not found_valid:
            print(f"     ❌ No 100% safe (DELIVERABLE) patterns found for {contact['name']}.")
            
    if verified_targets:
        print(f"✅ SUCCESS: Found {len(verified_targets)} verified targets.")
        return {"company": company_name, "domain": domain, "targets": verified_targets}
    else:
        print("❌ FAIL: No emails passed verification.")
        return None

if __name__ == "__main__":
    # Test execution
    test_companies = ["MyOperator", "savesage.club"]
    for c in test_companies:
        process_company(c)
        time.sleep(2)
