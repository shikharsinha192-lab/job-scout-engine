import requests
from bs4 import BeautifulSoup
import urllib.parse
import json
from datetime import datetime, timedelta

def ddg_search(query):
    url = "https://html.duckduckgo.com/html/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0"}
    try:
        res = requests.post(url, data={'q': query}, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        results = []
        for a in soup.find_all('a', class_='result__snippet'):
            title = a.parent.parent.find('h2', class_='result__title').get_text(strip=True)
            link = a.get('href')
            if link and 'uddg=' in link:
                link = urllib.parse.unquote(link.split('uddg=')[1].split('&')[0])
            results.append({"title": title, "url": link})
        return results
    except Exception as e:
        print(f"DDG Error: {e}")
        return []

def fetch_linkedin_india_7days():
    jobs_found = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0"}
    # f_TPR=r604800 is past week
    urls = [
        "https://www.linkedin.com/jobs/search/?f_WT=2&f_TPR=r604800&keywords=growth%20marketing&location=India",
        "https://www.linkedin.com/jobs/search/?f_WT=2&f_TPR=r604800&keywords=performance%20marketing&location=India"
    ]
    
    print("Fetching LinkedIn (Past 7 Days, India)...")
    for url in urls:
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
                    loc = loc_tag.text.strip() if loc_tag else 'India'
                    if 'india' in loc.lower():
                        jobs_found.append({
                            'title': title_tag.text.strip(),
                            'company': company_tag.text.strip(),
                            'location': loc,
                            'url': link_tag['href'].split('?')[0],
                            'source': 'LinkedIn Past Week'
                        })
        except Exception as e:
            print(f"LinkedIn error: {e}")
            
    return jobs_found

def fetch_apis_india():
    jobs_found = []
    headers = {"User-Agent": "JobScoutEngine/1.0"}
    
    print("Fetching APIs for India Remote...")
    # RemoteOK
    try:
        res = requests.get("https://remoteok.com/api?tags=marketing", headers=headers, timeout=10)
        data = res.json()
        for j in data[1:]:
            loc = str(j.get('location', '')).lower()
            if 'india' in loc or 'worldwide' in loc or 'anywhere' in loc:
                date_str = j.get('date', '')
                try:
                    job_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    if (datetime.now(job_date.tzinfo) - job_date).days <= 7:
                        jobs_found.append({
                            'title': j.get('position', ''),
                            'company': j.get('company', ''),
                            'location': j.get('location', ''),
                            'url': j.get('url', ''),
                            'source': 'RemoteOK'
                        })
                except:
                    pass
    except:
        pass
        
    return jobs_found

def run():
    print("Searching for remote marketing roles in India from the last 7 days...")
    jobs = []
    jobs.extend(fetch_linkedin_india_7days())
    jobs.extend(fetch_apis_india())
    
    # Deduplicate
    seen = set()
    unique_jobs = []
    for j in jobs:
        identifier = f"{j['title'].lower()}-{j['company'].lower()}"
        if identifier not in seen:
            seen.add(identifier)
            # Basic keyword filter
            t = j['title'].lower()
            if not any(k in t for k in ['engineer', 'developer', 'frontend', 'backend', 'fullstack']):
                unique_jobs.append(j)
                
    print(f"\nFound {len(unique_jobs)} fresh remote roles for Indian companies/locations.")
    
    with open("fresh_india_jobs.md", "w", encoding="utf-8") as f:
        f.write("# Fresh Remote Roles in India (Last 7 Days)\n\n")
        f.write("| Company | Role | Location | Source | Link |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- |\n")
        for j in unique_jobs:
            f.write(f"| {j['company']} | {j['title']} | {j['location']} | {j['source']} | [Apply]({j['url']}) |\n")
            
    print("Saved to fresh_india_jobs.md")

if __name__ == "__main__":
    run()
