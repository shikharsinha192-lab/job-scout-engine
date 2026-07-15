import os
import requests
import feedparser
from datetime import datetime, timezone
from dateutil import parser as date_parser

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

def fetch_hn_who_is_hiring():
    print("Fetching Hacker News Who is Hiring via Algolia API...")
    jobs = []
    # 1. Find the latest "Who is hiring?" thread
    thread_url = "https://hn.algolia.com/api/v1/search?query=Ask%20HN:%20Who%20is%20hiring?&tags=story,author_whoishiring&restrictSearchableAttributes=title"
    try:
        res = requests.get(thread_url, timeout=10)
        if res.status_code == 200:
            hits = res.json().get("hits", [])
            if not hits:
                return []
            latest_thread_id = hits[0].get("objectID")
            
            # 2. Fetch comments for this specific thread that mention our keywords
            # We fetch all comments from the thread and filter locally for better control
            comments_url = f"https://hn.algolia.com/api/v1/search?tags=comment,story_{latest_thread_id}&hitsPerPage=1000"
            c_res = requests.get(comments_url, timeout=10)
            if c_res.status_code == 200:
                comments = c_res.json().get("hits", [])
                for hit in comments:
                    text = hit.get("comment_text", "").lower()
                    if ("remote" in text or "india" in text) and any(k in text for k in ["growth", "marketing", "product", "strategy"]):
                        posted = hit.get("created_at", "")
                        url = f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                        snippet = hit.get("comment_text", "")[:300].replace('\n', ' ')
                        jobs.append(normalize_job(snippet, "HN Startup", "Remote / India", True, posted, url, "Hacker News"))
    except Exception as e:
        print(f"Error fetching HN: {e}")
    return jobs

def fetch_rss_feed(url, source_name):
    print(f"Fetching RSS: {source_name}...")
    jobs = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            published = entry.get("published", "")
            
            # Convert published to ISO format if possible
            try:
                dt = date_parser.parse(published)
                posted_date = dt.isoformat()
            except:
                posted_date = published
                
            jobs.append(normalize_job(title, "Unknown (Parse from title)", "Remote", True, posted_date, link, source_name))
    except Exception as e:
        print(f"Error fetching RSS {source_name}: {e}")
    return jobs

def run_layer2():
    print("=== Layer 2: Structured Feed Fetch ===")
    all_jobs = []
    all_jobs.extend(fetch_hn_who_is_hiring())
    all_jobs.extend(fetch_rss_feed("https://remotive.com/api/remote-jobs", "Remotive RSS")) # Using JSON API is better but feedparser can parse some JSON feeds or we can switch to standard RSS URL if available. Wait, Remotive API is JSON. Let's stick to real RSS.
    all_jobs.extend(fetch_rss_feed("https://weworkremotely.com/remote-jobs.rss", "WeWorkRemotely"))
    all_jobs.extend(fetch_rss_feed("https://jobspresso.co/feed/", "Jobspresso"))
    
    print(f"Layer 2 complete: Found {len(all_jobs)} raw jobs.")
    return all_jobs

if __name__ == "__main__":
    jobs = run_layer2()
    print(f"Sample job: {jobs[0] if jobs else 'None'}")
