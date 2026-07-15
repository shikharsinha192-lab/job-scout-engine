import pathlib
import re
import json
import datetime
import time
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

# Load domain → CSS selector mapping for posting date
SELECTOR_FILE = pathlib.Path(r"c:/Users/91639/Documents/antigravity/job-scout-engine/data/date_selectors.json")
if SELECTOR_FILE.is_file():
    DATE_SELECTORS = json.loads(SELECTOR_FILE.read_text(encoding="utf-8"))
else:
    DATE_SELECTORS = {}

# Regex to extract URLs from markdown link syntax
URL_REGEX = re.compile(r"\[.*?\]\((https?://[^)]+)\)")

def extract_urls(text: str) -> list[str]:
    return URL_REGEX.findall(text)

def fetch_date(url: str) -> datetime.date | None:
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        domain = requests.utils.urlparse(url).netloc.lower()
        selector = None
        for d, sel in DATE_SELECTORS.items():
            if domain.endswith(d):
                selector = sel
                break
        # Try domain‑specific selector first
        if selector:
            el = soup.select_one(selector)
            if el:
                date_str = el.get("content") or el.text
                parsed = parse_date(date_str)
                if parsed:
                    return parsed
        # Generic fallback: <time datetime="...">
        time_tag = soup.find("time")
        if time_tag and time_tag.has_attr("datetime"):
            parsed = parse_date(time_tag["datetime"])
            if parsed:
                return parsed
        # Fallback to HTTP Last‑Modified header
        lm = resp.headers.get("Last-Modified")
        if lm:
            parsed = parse_date(lm)
            if parsed:
                return parsed
    except Exception:
        return None
    return None

def parse_date(s: str) -> datetime.date | None:
    for fmt in ("%B %d, %Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.datetime.strptime(s.strip(), fmt).date()
        except Exception:
            continue
    # Try dateutil as last resort
    try:
        from dateutil import parser as dparser
        return dparser.parse(s).date()
    except Exception:
        return None

def fetch_dates(urls: list[str]) -> dict[str, datetime.date | None]:
    results: dict[str, datetime.date | None] = {}
    last_req: dict[str, float] = defaultdict(float)
    def _fetch(u: str):
        domain = requests.utils.urlparse(u).netloc.lower()
        elapsed = time.time() - last_req[domain]
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        d = fetch_date(u)
        last_req[domain] = time.time()
        return u, d
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_fetch, u): u for u in urls}
        for f in as_completed(futures):
            u, d = f.result()
            results[u] = d
    return results

def main():
    source_files = [
        pathlib.Path(r"c:/Users/91639/Documents/antigravity/job-scout-engine/data/job_listings_1_50.md"),
        pathlib.Path(r"c:/Users/91639/Documents/antigravity/job-scout-engine/data/job_listings_51_150.md"),
    ]
    cutoff = datetime.date.today() - datetime.timedelta(weeks=3)  # 3 weeks ago
    dest = pathlib.Path(r"c:/Users/91639/Documents/antigravity/job-scout-engine/data/filtered_recent_job_listings_1_150.md")
    keep_blocks = []
    for src in source_files:
        if not src.is_file():
            continue
        content = src.read_text(encoding="utf-8")
        # Split listings by '---' separator (common in markdown reports)
        blocks = [b.strip() for b in content.split('---') if b.strip()]
        for block in blocks:
            urls = extract_urls(block)
            if not urls:
                # No URL – keep by default (unlikely)
                keep_blocks.append(block)
                continue
            dates = fetch_dates(urls)
            # Determine if any URL has a recent posting date
            recent = any(d and d >= cutoff for d in dates.values())
            if recent:
                keep_blocks.append(block)
    # Write filtered markdown
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open('w', encoding='utf-8') as f:
        f.write('\n\n---\n\n'.join(keep_blocks))
    print(f"Filtered listings written to {dest}")

if __name__ == "__main__":
    main()
