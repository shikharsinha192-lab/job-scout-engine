import pathlib
import re
import json
import time
from duckduckgo_search import DDGS

SOURCE_FILE = pathlib.Path(r"c:/Users/91639/Documents/antigravity/job-scout-engine/data/job_listings_1_50.md")
DEST_FILE = pathlib.Path(r"c:/Users/91639/Documents/antigravity/job-scout-engine/data/verified_dates_1_36.json")

def extract_jobs():
    lines = SOURCE_FILE.read_text(encoding="utf-8").splitlines()
    jobs = []
    # Pattern to match rows like: | 1 | **Growth Marketer** — Sprinto (Remote, India) | ...
    pattern = re.compile(r"\|\s*(\d+)\s*\|\s*\*\*(.*?)\*\*\s*—\s*(.*?)\s*\|")
    for line in lines:
        m = pattern.search(line)
        if m:
            idx = int(m.group(1))
            if 1 <= idx <= 36:
                title = m.group(2).strip()
                company_loc = m.group(3).strip()
                # company_loc might look like: "Sprinto (Remote, India)"
                company = company_loc.split("(")[0].strip()
                jobs.append({
                    "id": idx,
                    "title": title,
                    "company": company,
                    "raw": line
                })
    return jobs

def verify_dates(jobs):
    results = []
    ddgs = DDGS()
    for job in jobs:
        query = f'"{job["title"]}" "{job["company"]}" remote India job'
        try:
            # Search DDG
            search_results = ddgs.text(query, max_results=3)
            snippets = " ".join([r.get("body", "") + " " + r.get("title", "") for r in search_results])
            
            # Simple heuristic to extract relative time indicators
            time_matches = re.findall(r'(\d+\s+(?:day|week|month|year|hour)s?\s+ago)', snippets, re.IGNORECASE)
            # Also check for full dates in snippet
            date_matches = re.findall(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}, \d{4}', snippets)
            
            job["snippets"] = snippets
            job["found_times"] = list(set(time_matches + date_matches))
            results.append(job)
        except Exception as e:
            job["error"] = str(e)
            results.append(job)
        time.sleep(2) # Respect rate limits
    return results

def main():
    if not SOURCE_FILE.is_file():
        print(f"Source file not found: {SOURCE_FILE}")
        return
    jobs = extract_jobs()
    print(f"Extracted {len(jobs)} jobs. Verifying dates...")
    verified = verify_dates(jobs)
    DEST_FILE.write_text(json.dumps(verified, indent=2), encoding="utf-8")
    print(f"Verification complete. Results saved to {DEST_FILE}")

if __name__ == "__main__":
    main()
