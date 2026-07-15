import os
import re
import time
import html
import requests
import dns.resolver
import smtplib
import socket
from apify_client import ApifyClient
from dotenv import load_dotenv

try:
    from google import genai
    has_modern_genai = True
except ImportError:
    import google.generativeai as genai
    has_modern_genai = False

load_dotenv()

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.gemini_client import generate_content_with_fallback

def _ask_gemini(prompt):
    try:
        result = generate_content_with_fallback(prompt)
        return result.get("text", "").strip() if result.get("success") else ""
    except Exception as e:
        print(f"  [Gemini Error] {str(e)}")
        return ""

def get_domain_from_company(company):
    prompt = f"What is the primary website domain for the company '{company}'? Output ONLY the domain name (e.g. company.com) and nothing else. If you are unsure, output UNKNOWN."
    ans = _ask_gemini(prompt).lower().strip()
    if ans == "unknown" or "." not in ans or len(ans.split()) > 1:
        return f"{company.lower().replace(' ', '')}.com"
    return ans

# Layer 1: Deep Website Scrape
def layer1_website_scrape(company, domain):
    print(f"  [Layer 1] Scraping website: {domain}...")
    urls_to_try = [f"https://www.{domain}", f"https://www.{domain}/contact", f"https://www.{domain}/careers"]
    found_emails = set()
    
    # Simple regex for email
    email_regex = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
    
    for url in urls_to_try:
        try:
            resp = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code == 200:
                emails = email_regex.findall(resp.text)
                for e in emails:
                    e = e.lower()
                    if e.endswith(f"@{domain}"):
                        found_emails.add(e)
        except Exception:
            pass
            
    # Filter out useless emails, prioritize HR
    hr_emails = [e for e in found_emails if any(kw in e for kw in ['hr@', 'careers@', 'talent@', 'jobs@', 'recruitment@'])]
    if hr_emails:
        return hr_emails
        
    # Return any personal emails (not standard generic ones)
    generic_prefixes = ['info', 'contact', 'hello', 'sales', 'support', 'marketing', 'admin']
    personal_emails = [e for e in found_emails if not any(e.startswith(f"{gp}@") for gp in generic_prefixes)]
    
    return personal_emails

# Layer 2: Snov.io B2B Database
def layer2_snov_api(domain):
    print(f"  [Layer 2] Querying Snov.io API for {domain}...")
    client_id = os.environ.get("SNOV_CLIENT_ID")
    client_secret = os.environ.get("SNOV_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("  [Layer 2] Snov API credentials not found. Skipping.")
        return []
        
    try:
        # Get Token
        token_res = requests.post("https://api.snov.io/v1/oauth/access_token", data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret
        }, timeout=10)
        
        if token_res.status_code != 200:
            print(f"  [Layer 2] Snov Auth failed: {token_res.text}")
            return []
            
        access_token = token_res.json().get("access_token")
        
        # Domain Search
        search_res = requests.get(
            f"https://api.snov.io/v2/domain-emails-with-info?domain={domain}&type=all&limit=100",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )
        
        if search_res.status_code != 200:
            return []
            
        data = search_res.json()
        emails_list = data.get("emails", [])
        
        hr_keywords = ["hr", "human resources", "recruiter", "talent", "acquisition", "people"]
        
        target_emails = []
        for item in emails_list:
            pos = str(item.get("position", "")).lower()
            if any(kw in pos for kw in hr_keywords):
                target_emails.append(item.get("email"))
                
        # If we didn't find HR specific, take the first valid one as a fallback or return empty to proceed to Layer 3
        if target_emails:
            return target_emails
            
        return []
        
    except Exception as e:
        print(f"  [Layer 2] Snov API Error: {str(e)}")
        return []

# Layer 3: OSINT Name Extraction + SMTP Verification
def check_smtp_email(email, mx_record):
    try:
        server = smtplib.SMTP(mx_record, 25, timeout=5)
        server.helo(socket.gethostname())
        server.mail('admin@example.com')
        code, message = server.rcpt(email)
        server.quit()
        return code == 250
    except Exception:
        return False

# Layer 3: GitHub Intelligence (Commits + Profiles)
def layer3_github_intelligence(company, domain):
    print(f"  [Layer 3] Searching GitHub Intelligence for {company}...")
    pat = os.environ.get("GITHUB_PAT")
    headers = {}
    if pat:
        headers["Authorization"] = f"token {pat}"
    
    found_emails = set()
    
    # Step A: Resolve GitHub organization
    org_candidates = [
        company.lower().replace(" ", ""),
        company.lower().replace(" ", "-"),
    ]
    
    resolved_org = None
    for org in org_candidates:
        try:
            r = requests.get(f"https://api.github.com/orgs/{org}", headers=headers, timeout=5)
            if r.status_code == 200:
                resolved_org = org
                break
        except Exception:
            pass
            
    if not resolved_org:
        return []
            
    if resolved_org:
        print(f"    Resolved GitHub Org: {resolved_org}")
        # Get top 5 repos
        try:
            repos_url = f"https://api.github.com/orgs/{resolved_org}/repos?sort=updated&per_page=5"
            r = requests.get(repos_url, headers=headers, timeout=5)
            if r.status_code == 200:
                repos = r.json()
                for repo in repos:
                    repo_name = repo.get("name")
                    commits_url = f"https://api.github.com/repos/{resolved_org}/{repo_name}/commits?per_page=20"
                    cr = requests.get(commits_url, headers=headers, timeout=5)
                    if cr.status_code == 200:
                        commits = cr.json()
                        if isinstance(commits, list):
                            for c in commits:
                                try:
                                    author_email = c['commit']['author']['email']
                                    if author_email and '@' in author_email and 'noreply' not in author_email:
                                        found_emails.add(author_email.lower())
                                except (KeyError, TypeError):
                                    pass
                                try:
                                    committer_email = c['commit']['committer']['email']
                                    if committer_email and '@' in committer_email and 'noreply' not in committer_email:
                                        found_emails.add(committer_email.lower())
                                except (KeyError, TypeError):
                                    pass
        except Exception as e:
            print(f"    Error mining commits: {str(e)}")
            
    # Step B: Search for employees and resolve public profiles
    try:
        search_users_url = f"https://api.github.com/search/users?q=company:\"{company}\""
        r = requests.get(search_users_url, headers=headers, timeout=5)
        if r.status_code == 200:
             users = r.json().get("items", [])
             for u in users[:10]: # limit to top 10 employees to avoid rate limit issues
                 login = u.get("login")
                 user_url = f"https://api.github.com/users/{login}"
                 ur = requests.get(user_url, headers=headers, timeout=5)
                 if ur.status_code == 200:
                     profile = ur.json()
                     email = profile.get("email")
                     if email and '@' in email and 'noreply' not in email:
                            found_emails.add(email.lower())
    except Exception as e:
        print(f"    Error searching employees: {str(e)}")
        
    # Strictly filter to domain-specific emails.
    # Never fall back to personal emails (like gmail.com) or local machine names (.local)
    domain_emails = [e for e in found_emails if e.endswith(f"@{domain}")]
    if domain_emails:
        print(f"    [Success] Found {len(domain_emails)} matching domain emails on GitHub.")
        return list(set(domain_emails))
        
    return []

# Layer 4: HackerNews Hiring Thread Scan
def layer4_hackernews_scan(company, domain):
    print(f"  [Layer 4] Searching HackerNews Hiring Threads for {company}...")
    found_emails = set()
    
    # Search for comments mentioning company
    url = f"https://hn.algolia.com/api/v1/search_by_date"
    params = {
        "query": company,
        "tags": "comment",
        "hitsPerPage": 30
    }
    try:
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            hits = r.json().get("hits", [])
            email_regex = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
            for hit in hits:
                comment_text = hit.get("comment_text", "")
                if comment_text:
                    # Unescape HTML entities
                    clean_text = html.unescape(comment_text)
                    # Strip HTML tags
                    clean_text = re.sub('<[^<]+?>', ' ', clean_text)
                    emails = email_regex.findall(clean_text)
                    for e in emails:
                        e_clean = e.lower().strip().rstrip('.')
                        found_emails.add(e_clean)
    except Exception as e:
        print(f"    HN Search Error: {str(e)}")
        
    domain_emails = [e for e in found_emails if e.endswith(f"@{domain}")]
    if domain_emails:
        print(f"    [Success] Found {len(domain_emails)} matching domain emails on HN.")
        return list(set(domain_emails))
        
    return []

def _validate_via_breach_db(email):
    try:
        url = f"https://api.xposedornot.com/v1/check-email/{email}"
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            return True
    except Exception:
        pass
    return False

def layer5_smtp_verification(company, domain):
    print(f"  [Layer 5] OSINT Name Search & Local SMTP/Breach Verification for {domain}...")
    apify_token = os.environ.get("APIFY_API_TOKEN")
    if not apify_token: return []
    
    try:
        client = ApifyClient(apify_token)
        search_query = f'site:linkedin.com/in/ "{company}" AND ("HR" OR "Recruiter" OR "Talent" OR "Founder" OR "CEO")'
        
        run_input = {
            "queries": search_query,
            "maxPagesPerQuery": 1,
            "resultsPerPage": 5,
        }
        
        run = client.actor("apify/google-search-scraper").call(run_input=run_input)
        dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else run.default_dataset_id
        
        snippets = []
        for item in client.dataset(dataset_id).iterate_items():
            if 'organicResults' in item:
                for result in item['organicResults']:
                    snippets.append(result.get('title', ''))
                    
        raw_text = "\n".join(snippets)
        if not raw_text.strip(): return []
        
        prompt = f"Extract the first and last name of the HR Manager, Recruiter, Founder, or CEO from this text. Output ONLY their full name (e.g., 'John Doe'). If none found, output NONE:\n{raw_text}"
        name = _ask_gemini(prompt).strip()
        
        if "NONE" in name.upper() or len(name.split()) < 2:
            return []
            
        parts = name.split()
        first = parts[0].lower()
        last = parts[-1].lower()
        f = first[0]
        
        permutations = [
            f"{first}.{last}@{domain}",
            f"{first}{last}@{domain}",
            f"{f}{last}@{domain}",
            f"{first}@{domain}"
        ]
        
        # Check Breach DB first (fast, silent)
        for email in permutations:
            if _validate_via_breach_db(email):
                print(f"  [Layer 5] Breach Database Verified: {email}")
                return [email]
            time.sleep(0.5)
            
        # Get MX Record
        try:
            answers = dns.resolver.resolve(domain, 'MX')
            mx_record = str(answers[0].exchange)
        except Exception:
            return []
            
        for email in permutations:
            if check_smtp_email(email, mx_record):
                print(f"  [Layer 5] SMTP Verified: {email}")
                return [email]
                
        return []
        
    except Exception as e:
        print(f"  [Layer 5] Error: {str(e)}")
        return []

# Layer 6: OSINT Snippet Scrape Fallback
def layer6_osint_fallback(company, domain):
    print(f"  [Layer 6] Google OSINT Snippet Fallback...")
    apify_token = os.environ.get("APIFY_API_TOKEN")
    if not apify_token: return []
    
    try:
        client = ApifyClient(apify_token)
        search_query = f'"{company}" AND ("@{domain}") AND ("HR" OR "Careers" OR "Talent" OR "Recruitment" OR "Email")'
        
        run_input = {
            "queries": search_query,
            "maxPagesPerQuery": 1,
            "resultsPerPage": 15,
        }
        
        run = client.actor("apify/google-search-scraper").call(run_input=run_input)
        dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else run.default_dataset_id
        
        snippets = []
        for item in client.dataset(dataset_id).iterate_items():
            if 'organicResults' in item:
                for result in item['organicResults']:
                    snippets.append(result.get('description', ''))
                    
        raw_text = "\n".join(snippets)
        if not raw_text.strip(): return []
        
        prompt = f"Extract ANY valid email addresses that belong to '{domain}' from this text. Only return the emails comma-separated. If none, return NONE_FOUND:\n{raw_text}"
        ans = _ask_gemini(prompt).strip()
        
        if "NONE_FOUND" in ans.upper():
            return []
            
        emails = [e.strip() for e in ans.split(',') if '@' in e]
        return emails
        
    except Exception as e:
        print(f"  [Layer 6] Error: {str(e)}")
        return []


def hunt_for_emails(company, domain=None):
    """Orchestrates the 6-layer waterfall email harvesting strategy."""
    print(f"Initiating Waterfall Harvester for: {company}")
    
    if not domain:
        domain = get_domain_from_company(company)
    print(f"  Resolved Domain: {domain}")
        
    banned_prefixes = [
        "info", "contact", "support", "sales", "hello", "hi", "team", "admin", 
        "press", "marketing", "media", "help", "general", "inquiries", "webmaster", "postmaster",
        "partners", "legal", "hr", "careers", "jobs", "talent", "recruitment", "people", "office",
        "example", "test", "demo", "dummy", "placeholder", "user", "username", "yourname", "domain", "company"
    ]
    
    strict_emails = set()
    fallback_emails = set()
    
    def _is_valid_email(email_str: str) -> bool:
        email_str = email_str.lower().strip()
        if '@' not in email_str or len(email_str.split()) > 1:
            return False
        parts = email_str.split('@')
        if len(parts) != 2:
            return False
        dom = parts[1]
        if '.' not in dom:
            return False
        invalid_tlds = ('.local', '.localdomain', '.lan', 'localhost')
        if any(dom.endswith(tld) or dom == tld.strip('.') for tld in invalid_tlds):
            return False
        if not re.match(r"^[a-z0-9_.+-]+@[a-z0-9-]+\.[a-z0-9-.]+$", email_str):
            return False
        return True

    def process_found(found_list, layer_num):
        for e in found_list:
            e = e.lower().strip()
            if not _is_valid_email(e):
                print(f"  [Filtered] Rejected invalid email format: {e}")
                continue
            local_part = e.split("@")[0]
            if local_part in ["hr", "careers", "jobs", "talent", "recruitment", "people"]:
                fallback_emails.add(e)
            elif local_part in banned_prefixes or any(local_part.startswith(f"{bp}-") for bp in banned_prefixes):
                print(f"  [Filtered] Rejected generic email: {e}")
            else:
                strict_emails.add(e)
                
    # Layer 1: Website Scrape
    found = layer1_website_scrape(company, domain)
    if found:
        process_found(found, 1)
        if strict_emails:
            print(f"  [Success] Found personal emails via Layer 1")
            return list(strict_emails)
        
    # Layer 2: Snov.io
    found = layer2_snov_api(domain)
    if found:
        process_found(found, 2)
        if strict_emails:
            print(f"  [Success] Found personal emails via Layer 2")
            return list(strict_emails)
            
    # Layer 3: GitHub Intelligence
    found = layer3_github_intelligence(company, domain)
    if found:
        process_found(found, 3)
        if strict_emails:
            print(f"  [Success] Found personal emails via Layer 3")
            return list(strict_emails)
            
    # Layer 4: HN Scan
    found = layer4_hackernews_scan(company, domain)
    if found:
        process_found(found, 4)
        if strict_emails:
            print(f"  [Success] Found personal emails via Layer 4")
            return list(strict_emails)
            
    # Layer 5: SMTP / Breach Validate
    found = layer5_smtp_verification(company, domain)
    if found:
        process_found(found, 5)
        if strict_emails:
            print(f"  [Success] Found personal emails via Layer 5")
            return list(strict_emails)
            
    # Layer 6: OSINT Fallback
    found = layer6_osint_fallback(company, domain)
    if found:
        process_found(found, 6)
        if strict_emails:
            print(f"  [Success] Found personal emails via Layer 6")
            return list(strict_emails)
            
    if fallback_emails:
        print(f"  [Fallback] No personal emails found, falling back to: {list(fallback_emails)}")
        return list(fallback_emails)
        
    return []

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", required=True)
    args = parser.parse_args()
    
    found = hunt_for_emails(args.company)
    if found:
        print(f"Final Discovered Emails: {', '.join(found)}")
    else:
        print("No emails found after all 6 layers.")
