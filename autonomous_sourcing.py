import requests
from bs4 import BeautifulSoup
import sqlite3
import json
import re
import datetime
from urllib.parse import urlparse

# --- CORE SYSTEM: DB & SCORING ---

DB_FILE = 'jobs_ledger.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS jobs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  title TEXT,
                  company TEXT,
                  location TEXT,
                  url TEXT,
                  source TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE(title, company))''')
    conn.commit()
    conn.close()

def is_duplicate(title, company):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Normalize for comparison
    norm_title = title.lower().strip()
    norm_company = company.lower().strip()
    c.execute("SELECT 1 FROM jobs WHERE LOWER(title)=? AND LOWER(company)=?", (norm_title, norm_company))
    result = c.fetchone()
    conn.close()
    return bool(result)

def add_job(title, company, location, url, source):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO jobs (title, company, location, url, source) VALUES (?, ?, ?, ?, ?)",
                  (title, company, location, url, source))
        conn.commit()
        added = True
    except sqlite3.IntegrityError:
        added = False
    conn.close()
    return added

def score_job(title, company, location, description=""):
    title_lower = title.lower()
    loc_lower = location.lower() if location else ""
    desc_lower = description.lower() if description else ""
    
    # Fast rejects (Engineering roles)
    eng_keywords = ['engineer', 'developer', 'frontend', 'backend', 'fullstack', 'qa', 'data scientist', 'devops']
    if any(k in title_lower for k in eng_keywords):
        return -1
        
    # Geo rejects
    # Many remote jobs are US only. We want India-friendly or Anywhere.
    geo_rejects = ['us only', 'usa only', 'uk only', 'europe only', 'latam only', 'north america only']
    if any(k in loc_lower for k in geo_rejects):
        return -1
        
    # Relevancy Scoring (Marketing / Growth)
    score = 0
    prime_keywords = ['marketing', 'growth', 'performance', 'seo', 'content', 'abm', 'demand', 'lead gen', 'b2b', 'd2c', 'social']
    if any(k in title_lower for k in prime_keywords):
        score += 10
        
    # Bonus for India/Global/Anywhere
    good_geos = ['india', 'anywhere', 'worldwide', 'global', 'remote']
    if any(k in loc_lower for k in good_geos):
        score += 5
        
    return score

# --- LAYER 1: JSON APIs ---

def fetch_layer1_apis():
    jobs_found = []
    headers = {"User-Agent": "JobScoutEngine/1.0"}
    
    # 1. Remotive
    print("Fetching Remotive...")
    try:
        res = requests.get("https://remotive.com/api/remote-jobs?category=marketing", headers=headers, timeout=10)
        data = res.json()
        for j in data.get('jobs', []):
            jobs_found.append({
                'title': j.get('title', ''),
                'company': j.get('company_name', ''),
                'location': j.get('candidate_required_location', ''),
                'url': j.get('url', ''),
                'source': 'Remotive API'
            })
    except Exception as e:
        print(f"Remotive error: {e}")

    # 2. RemoteOK
    print("Fetching RemoteOK...")
    try:
        res = requests.get("https://remoteok.com/api?tags=marketing", headers=headers, timeout=10)
        data = res.json()
        for j in data[1:]: # First element is legal info
            jobs_found.append({
                'title': j.get('position', ''),
                'company': j.get('company', ''),
                'location': j.get('location', ''),
                'url': j.get('url', ''),
                'source': 'RemoteOK API'
            })
    except Exception as e:
        print(f"RemoteOK error: {e}")

    # 3. Himalayas
    print("Fetching Himalayas...")
    try:
        res = requests.get("https://himalayas.app/jobs/api?limit=100", headers=headers, timeout=10)
        data = res.json()
        for j in data.get('jobs', []):
            jobs_found.append({
                'title': j.get('title', ''),
                'company': j.get('companyName', ''),
                'location': ', '.join(j.get('countries', [])),
                'url': j.get('applicationLink', ''),
                'source': 'Himalayas API'
            })
    except Exception as e:
        print(f"Himalayas error: {e}")
        
    return jobs_found

# --- LAYER 2: Hacker News Who is Hiring ---

def fetch_layer2_hn():
    jobs_found = []
    print("Fetching Hacker News Who Is Hiring...")
    try:
        # Find latest thread
        search_url = 'https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&query="Ask HN: Who is hiring"'
        res = requests.get(search_url, timeout=10).json()
        if not res['hits']: return []
        
        latest_story_id = res['hits'][0]['objectID']
        
        # Search comments in that thread for marketing/growth
        comment_search_url = f'https://hn.algolia.com/api/v1/search?query=marketing+OR+growth&tags=comment,story_{latest_story_id}'
        comments = requests.get(comment_search_url, timeout=10).json()
        
        for hit in comments['hits']:
            text = hit.get('comment_text', '')
            # Try to parse standard HN format: Company | Role | Location | Extras
            # Often first line has this
            lines = BeautifulSoup(text, "html.parser").get_text().split('\n')
            if not lines: continue
            first_line = lines[0]
            parts = first_line.split('|')
            if len(parts) >= 2:
                company = parts[0].strip()
                title = parts[1].strip()
                loc = parts[2].strip() if len(parts) > 2 else "Remote/HN"
                jobs_found.append({
                    'title': title,
                    'company': company,
                    'location': loc,
                    'url': f"https://news.ycombinator.com/item?id={hit['objectID']}",
                    'source': 'Hacker News'
                })
    except Exception as e:
        print(f"HN error: {e}")
        
    return jobs_found

# --- LAYER 3: RSS Feeds ---

def fetch_layer3_rss():
    jobs_found = []
    headers = {"User-Agent": "JobScoutEngine/1.0"}
    feeds = [
        ("WeWorkRemotely", "https://weworkremotely.com/categories/remote-marketing-jobs.rss"),
        ("RemotiveRSS", "https://remotive.com/feed?category=marketing")
    ]
    
    for source_name, url in feeds:
        print(f"Fetching RSS: {source_name}...")
        try:
            res = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(res.content, features="xml")
            items = soup.find_all('item')
            for item in items:
                title_full = item.find('title').text if item.find('title') else ""
                link = item.find('link').text if item.find('link') else ""
                
                # Title often contains company: "Company: Job Title"
                company = ""
                title = title_full
                if ":" in title_full:
                    company, title = title_full.split(":", 1)
                
                jobs_found.append({
                    'title': title.strip(),
                    'company': company.strip() or "Unknown",
                    'location': "Remote", # Implied by feeds
                    'url': link,
                    'source': f'RSS {source_name}'
                })
        except Exception as e:
            print(f"RSS error {source_name}: {e}")
            
    return jobs_found

# --- LAYER 5: GOOGLE DORKS (DDG HTML) ---

def fetch_layer5_dorks():
    jobs_found = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    queries = [
        'site:jobs.lever.co "growth marketing" remote india OR worldwide',
        'site:boards.greenhouse.io "performance marketing" remote'
    ]
    
    print("Fetching Google Dorks (via DDG)...")
    for q in queries:
        try:
            res = requests.post("https://html.duckduckgo.com/html/", data={'q': q}, headers=headers, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            for a in soup.find_all('a', class_='result__snippet'):
                title = a.parent.parent.find('h2', class_='result__title').get_text(strip=True)
                link = a.get('href')
                if link and 'uddg=' in link:
                    link = link.split('uddg=')[1].split('&')[0]
                    import urllib.parse
                    link = urllib.parse.unquote(link)
                    
                jobs_found.append({
                    'title': title,
                    'company': 'ATS Dork (Check Link)',
                    'location': 'Remote',
                    'url': link,
                    'source': 'Google Dork'
                })
        except Exception as e:
            print(f"Dork error: {e}")
            
    return jobs_found

# --- LAYER 6: LINKEDIN URL HACK ---

def fetch_layer6_linkedin():
    jobs_found = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0"}
    url = "https://www.linkedin.com/jobs/search/?f_WT=2&f_TPR=r86400&keywords=growth%20marketing&location=India"
    
    print("Fetching LinkedIn (No Auth)...")
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        cards = soup.find_all('div', class_='base-card')
        for card in cards:
            title_tag = card.find('h3', class_='base-search-card__title')
            company_tag = card.find('h4', class_='base-search-card__subtitle')
            loc_tag = card.find('span', class_='job-search-card__location')
            link_tag = card.find('a', class_='base-card__full-link')
            
            if title_tag and company_tag and link_tag:
                jobs_found.append({
                    'title': title_tag.text.strip(),
                    'company': company_tag.text.strip(),
                    'location': loc_tag.text.strip() if loc_tag else 'India',
                    'url': link_tag['href'].split('?')[0],
                    'source': 'LinkedIn Hack'
                })
    except Exception as e:
        print(f"LinkedIn error: {e}")
        
    return jobs_found

# --- MASTER ORCHESTRATOR ---

def run_sourcing_engine():
    init_db()
    all_raw_jobs = []
    
    print("--- STARTING AUTONOMOUS JOB SOURCING ENGINE ---")
    
    all_raw_jobs.extend(fetch_layer1_apis())
    all_raw_jobs.extend(fetch_layer2_hn())
    all_raw_jobs.extend(fetch_layer3_rss())
    all_raw_jobs.extend(fetch_layer5_dorks())
    all_raw_jobs.extend(fetch_layer6_linkedin())
    
    print(f"\nExtracted {len(all_raw_jobs)} total raw leads. Running Deduplication & Scoring Engine...")
    
    processed_jobs = []
    
    for job in all_raw_jobs:
        t = job['title']
        c = job['company']
        
        score = score_job(t, c, job['location'])
        if score > 0:
            if not is_duplicate(t, c):
                add_job(t, c, job['location'], job['url'], job['source'])
                processed_jobs.append(job)
                
    print(f"\n--- SOURCING COMPLETE ---")
    print(f"Found {len(processed_jobs)} new, highly relevant, non-duplicate jobs!")
    
    # Dump to Markdown
    with open("fresh_sourced_jobs.md", "w", encoding="utf-8") as f:
        f.write("# Autonomous Engine: Fresh Remote Jobs\n\n")
        f.write("| Company | Role | Location | Source | Link |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- |\n")
        for j in processed_jobs:
            f.write(f"| {j['company']} | {j['title']} | {j['location']} | {j['source']} | [Apply]({j['url']}) |\n")
            
    print("Results saved to fresh_sourced_jobs.md")

if __name__ == "__main__":
    run_sourcing_engine()
