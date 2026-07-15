import os
import requests
from apify_client import ApifyClient
from datetime import datetime, timezone
import feedparser
from dotenv import load_dotenv
from dateutil import parser as date_parser

load_dotenv()

def normalize_job(title, company, location, is_remote, posted_date, url, source):
    return {
        "job_title": title,
        "company": company,
        "location": location,
        "is_remote": is_remote,
        "posted_date": posted_date,
        "job_url": url,
        "source": source
    }

def fetch_uae_rss():
    print("Fetching Bayt.com RSS...")
    jobs = []
    try:
        # Bayt often has RSS for search queries
        url = "https://www.bayt.com/en/uae/jobs/marketing-jobs/rss/"
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            published = entry.get("published", "")
            
            try:
                dt = date_parser.parse(published)
                posted_date = dt.isoformat()
            except:
                posted_date = published
                
            company = "UAE Company"
            if "-" in title:
                company = title.split("-")[0].strip()
                title = "-".join(title.split("-")[1:]).strip()
                
            jobs.append(normalize_job(title, company, "UAE (Check Remote)", False, posted_date, link, "Bayt.com"))
    except Exception as e:
        print(f"Error fetching Bayt RSS: {e}")
    return jobs

def fetch_uae_dorks(keywords):
    print(f"Fetching Naukrigulf & Bayt via Apify Google Search...")
    jobs = []
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        return jobs
        
    client = ApifyClient(token)
    
    queries = []
    for k in keywords[:3]:
        queries.append(f'site:naukrigulf.com "{k}" "remote"')
        queries.append(f'site:bayt.com "{k}" "remote"')
        
    run_input = {
        "queries": "\n".join(queries),
        "maxPagesPerQuery": 1,
        "resultsPerPage": 10,
    }
    
    try:
        run = client.actor("apify/google-search-scraper").call(run_input=run_input)
        dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else run.default_dataset_id
        
        for item in client.dataset(dataset_id).iterate_items():
            for result in item.get("organicResults", []):
                title = result.get("title", "")
                url = result.get("url", "")
                
                company = "UAE Company"
                posted = datetime.now(timezone.utc).isoformat()
                
                source = "Naukrigulf" if "naukrigulf.com" in url else "Bayt.com"
                jobs.append(normalize_job(title, company, "UAE Remote", True, posted, url, source))
    except Exception as e:
        print(f"Error fetching UAE boards via Google: {e}")
        
    return jobs

def fetch_uae_jobs(keywords):
    jobs = []
    jobs.extend(fetch_uae_rss())
    jobs.extend(fetch_uae_dorks(keywords))
    return jobs

if __name__ == "__main__":
    j = fetch_uae_jobs(["growth marketer"])
    print(f"Found {len(j)} UAE jobs. Sample: {j[0] if j else 'None'}")
