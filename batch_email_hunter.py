import requests
from bs4 import BeautifulSoup
import re
import urllib.parse
import json
import time

companies = [
    "Staffnixcom",
    "VoiceTree Technologies",
    "Timble Technologies",
    "Hashone Career",
    "Moshi Moshi",
    "Eco-Soap Bank",
    "Zava AI",
    "TestMu AI",
    "Peak Hire Solutions",
    "G2com",
    "Wordsburg Translations",
    "AdPushup",
    "EASYECOM",
    "Kinematic Digital"
]

SNOV_CLIENT_ID = "4084ce14581a2c08d5940c5963fd2796"
SNOV_CLIENT_SECRET = "b84924327695f466ed88b5f4b0c153d6"
token = None

def get_snov_token():
    url = "https://api.snov.io/v1/oauth/access_token"
    payload = {"grant_type": "client_credentials", "client_id": SNOV_CLIENT_ID, "client_secret": SNOV_CLIENT_SECRET}
    try:
        res = requests.post(url, data=payload)
        return res.json().get("access_token")
    except:
        return None

def ddg_search(query):
    url = "https://html.duckduckgo.com/html/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    try:
        res = requests.post(url, data={'q': query}, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        results = []
        for a in soup.find_all('a', class_='result__snippet'):
            title = a.parent.parent.find('h2', class_='result__title').get_text(strip=True)
            link = a.get('href')
            if link and link.startswith('//duckduckgo.com/l/?uddg='):
                link = urllib.parse.unquote(link.split('uddg=')[1].split('&')[0])
            snippet = a.get_text(strip=True)
            results.append({"title": title, "url": link, "snippet": snippet})
        return results
    except Exception as e:
        print(f"DDG Error: {e}")
        return []

def get_domain(company_name):
    res = ddg_search(f"{company_name} official website")
    for r in res:
        url = r['url']
        if not url: continue
        if any(x in url for x in ['linkedin.com', 'facebook.com', 'glassdoor', 'indeed', 'ambitionbox', 'cutshort']):
            continue
        try:
            domain = urllib.parse.urlparse(url).netloc.replace("www.", "")
            if domain: return domain
        except:
            pass
    return f"{company_name.lower().replace(' ', '')}.com" # fallback guess

def get_snov_contacts(domain):
    if not token: return []
    try:
        start_url = "https://api.snov.io/v2/domain-search/start"
        res = requests.post(start_url, json={"domain": domain}, headers={"Authorization": f"Bearer {token}"})
        res_url = res.json().get("links", {}).get("result")
        if not res_url: return []
        
        for _ in range(5):
            time.sleep(2)
            poll = requests.get(res_url, headers={"Authorization": f"Bearer {token}"}).json()
            if "emails" in poll:
                return poll["emails"]
            if isinstance(poll, list):
                return poll
    except:
        pass
    return []

def extract_names_from_linkedin(company):
    results = ddg_search(f'site:linkedin.com/in/ "{company}" AND ("HR" OR "Recruiter" OR "Talent" OR "Founder" OR "CEO")')
    names = []
    for r in results:
        title = r['title']
        # Extract names from "John Doe - HR Manager - Company | LinkedIn"
        parts = title.split('-')
        if parts:
            name = parts[0].strip()
            if "LinkedIn" not in name and len(name.split()) <= 3:
                names.append({"name": name, "snippet": r['snippet']})
    return names

def run():
    global token
    token = get_snov_token()
    
    final_output = []
    
    for comp in companies:
        print(f"\n--- Processing {comp} ---")
        domain = get_domain(comp)
        print(f"Domain guessed: {domain}")
        
        # 1. Get HR/Founder names from LinkedIn
        linkedin_profiles = extract_names_from_linkedin(comp)
        
        # 2. Get Snov contacts
        snov_contacts = get_snov_contacts(domain)
        
        # Find matches
        found_emails = []
        for p in linkedin_profiles:
            name_parts = p['name'].lower().split()
            for sc in snov_contacts:
                if sc.get('email'):
                    email = sc['email'].lower()
                    # Try to match name to email (e.g., first name in email)
                    if len(name_parts) > 0 and name_parts[0] in email:
                        found_emails.append(f"{sc['email']} (Matched {p['name']})")
        
        # If no match, get any founder/hr from snov
        if not found_emails:
            for sc in snov_contacts:
                pos = (sc.get('position') or '').lower()
                if any(x in pos for x in ['founder', 'ceo', 'hr', 'talent', 'recruiter', 'marketing']):
                    name = f"{sc.get('first_name','')} {sc.get('last_name','')}".strip()
                    found_emails.append(f"{sc['email']} (Snov Role: {pos})")
        
        # Fallback
        if not found_emails:
            found_emails.append(f"hr@{domain} (Fallback)")
            found_emails.append(f"careers@{domain} (Fallback)")
            
        final_output.append({
            "Company": comp,
            "Domain": domain,
            "LinkedIn Leads": [p['name'] for p in linkedin_profiles[:3]],
            "Target Emails": list(set(found_emails))
        })
        
    with open("scouted_emails.json", "w") as f:
        json.dump(final_output, f, indent=4)
    print("Done! Results saved to scouted_emails.json")

if __name__ == "__main__":
    run()
