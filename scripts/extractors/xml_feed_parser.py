import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from dateutil import parser

def parse_xml_feed(feed_url, keywords=["Marketing", "Growth", "Performance"]):
    print(f"Initiating XML/RSS bulk ingestion from: {feed_url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    
    jobs_normalized = []
    
    try:
        res = requests.get(feed_url, headers=headers, timeout=15)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            
            # Common RSS/XML structures:
            # RSS 2.0: /channel/item
            items = root.findall('.//item')
            
            for item in items:
                title = item.findtext('title', '')
                link = item.findtext('link', '')
                pubDate = item.findtext('pubDate', '')
                description = item.findtext('description', '')
                
                # Check for keyword matches in title
                if not any(kw.lower() in title.lower() for kw in keywords):
                    continue
                    
                # In standard RSS, company and location are often embedded in the title or custom tags.
                # E.g., "Growth Manager at Startup (Remote)"
                company = "Unknown"
                loc = "Remote"
                is_remote = True # Assuming remote feeds for now
                
                if " at " in title:
                    parts = title.split(" at ")
                    title = parts[0]
                    company = parts[1].split("(")[0].strip() if "(" in parts[1] else parts[1].strip()
                
                # Normalize date
                parsed_date = ""
                if pubDate:
                    try:
                        dt = parser.parse(pubDate)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        parsed_date = dt.isoformat()
                    except:
                        pass
                
                jobs_normalized.append({
                    "job_title": title.strip(),
                    "company": company,
                    "location": loc,
                    "is_remote": is_remote,
                    "posted_date": parsed_date,
                    "job_url": link,
                    "source": "XML Affiliate Feed"
                })
        else:
            print(f"XML feed returned status {res.status_code}")
    except Exception as e:
        print(f"Error parsing XML feed {feed_url}: {e}")
        
    print(f"XML ingestion complete. Extracted {len(jobs_normalized)} jobs.")
    return jobs_normalized

if __name__ == "__main__":
    # Example using WeWorkRemotely remote jobs RSS
    jobs = parse_xml_feed("https://weworkremotely.com/remote-jobs.rss", ["marketing", "growth", "crm", "seo"])
    print(f"Found {len(jobs)} marketing jobs in XML feed.")
    if jobs:
        print(f"Sample: {jobs[0]}")
