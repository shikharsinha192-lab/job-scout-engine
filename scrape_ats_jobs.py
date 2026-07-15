import json
import requests
from bs4 import BeautifulSoup

# Standard ATS endpoints:
# Lever: https://api.lever.co/v0/postings/{company}?mode=json
# Greenhouse: https://boards-api.greenhouse.io/v1/boards/{company}/jobs
# Ashby: https://api.ashbyhq.com/posting-api/job-board/{company}

with open("startup_urls_found.json", "r") as f:
    urls_data = json.load(f)

results = []

def fetch_lever(company_id, company_name):
    url = f"https://api.lever.co/v0/postings/{company_id}?mode=json"
    res = requests.get(url)
    if res.status_code == 200:
        data = res.json()
        for job in data:
            loc = job.get('categories', {}).get('location', '').lower()
            workplace = job.get('workplaceType', '').lower()
            title = job.get('text', '')
            link = job.get('hostedUrl', '')
            
            if 'india' in loc or 'remote' in loc or 'remote' in workplace:
                results.append({
                    "Company": company_name,
                    "Role": title,
                    "Location": loc,
                    "Link": link
                })

def fetch_greenhouse(company_id, company_name):
    url = f"https://boards-api.greenhouse.io/v1/boards/{company_id}/jobs"
    res = requests.get(url)
    if res.status_code == 200:
        data = res.json()
        for job in data.get('jobs', []):
            loc = job.get('location', {}).get('name', '').lower()
            title = job.get('title', '')
            link = job.get('absolute_url', '')
            
            if 'india' in loc or 'remote' in loc:
                results.append({
                    "Company": company_name,
                    "Role": title,
                    "Location": loc,
                    "Link": link
                })

def fetch_ashby(company_id, company_name):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{company_id}"
    res = requests.get(url)
    if res.status_code == 200:
        data = res.json()
        for job in data.get('jobs', []):
            loc = job.get('location', '').lower()
            title = job.get('title', '')
            link = job.get('jobUrl', '')
            
            if 'india' in loc or 'remote' in loc:
                results.append({
                    "Company": company_name,
                    "Role": title,
                    "Location": loc,
                    "Link": link
                })

for company, urls in urls_data.items():
    found_ats = False
    for url in urls:
        if 'lever.co/' in url:
            # extract company id
            parts = url.split('lever.co/')
            if len(parts) > 1:
                cid = parts[1].split('/')[0]
                fetch_lever(cid, company)
                found_ats = True
                break
        elif 'greenhouse.io/' in url:
            parts = url.split('greenhouse.io/')
            if len(parts) > 1:
                cid = parts[1].split('/')[0]
                if cid == 'embed': # Sometimes it's /embed/job_board?for=company
                    pass 
                else:
                    fetch_greenhouse(cid, company)
                    found_ats = True
                    break
        elif 'ashbyhq.com/' in url:
            parts = url.split('ashbyhq.com/')
            if len(parts) > 1:
                cid = parts[1].split('/')[0]
                fetch_ashby(cid, company)
                found_ats = True
                break
    
    if not found_ats:
        print(f"Could not auto-parse ATS for {company}")

with open("ats_jobs_results.json", "w") as f:
    json.dump(results, f, indent=4)

print(f"Successfully scraped {len(results)} remote/India roles via ATS APIs.")
