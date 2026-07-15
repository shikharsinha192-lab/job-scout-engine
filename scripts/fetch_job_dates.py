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

# Simple regex to extract URLs from markdown link syntax
URL_REGEX = re.compile(r"\[.*?\]\((https?://[^)]+)\)")

def extract_urls_from_markdown(text: str) -> list[str]:
    return URL_REGEX.findall(text)

def fetch_date_for_url(url: str) -> datetime.date | None:
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return None
        # Try to get date from HTML meta/property or <time> tags
        soup = BeautifulSoup(resp.text, "html.parser")
        domain = pathlib.PurePath(requests.utils.urlparse(url).netloc).as_posix()
        selector = None
        # Find the most specific domain match (e.g., sub.domain.com)
        for d, sel in DATE_SELECTORS.items():
            if domain.endswith(d):
                selector = sel
                break
        # Attempt meta/property selector first
        if selector:
            element = soup.select_one(selector)
            if element:
                # meta tags have content attribute
                date_str = element.get("content") or element.text
                date = _parse_date_string(date_str)
                if date:
                    return date
        # Generic fallback: look for <time datetime="...">
        time_tag = soup.find("time")
        if time_tag and time_tag.has_attr("datetime"):
            date = _parse_date_string(time_tag["datetime"])
            if date:
                return date
        # Final fallback: HTTP Last-Modified header
        lm = resp.headers.get("Last-Modified")
        if lm:
            date = _parse_date_string(lm)
            if date:
                return date
    except Exception as e:
        # Silently ignore errors; could log if needed
        return None
    return None

def _parse_date_string(date_str: str) -> datetime.date | None:
    # Try multiple known formats
    for fmt in ("%B %d, %Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.datetime.strptime(date_str.strip(), fmt).date()
        except Exception:
            continue
    # Try parsing with dateutil if available (fallback)
    try:
        from dateutil import parser as dparser
        return dparser.parse(date_str).date()
    except Exception:
        return None

def fetch_dates_for_urls(urls: list[str]) -> dict[str, datetime.date | None]:
    results: dict[str, datetime.date | None] = {}
    # Rate‑limit: enforce 1 sec per domain
    last_request: dict[str, float] = defaultdict(float)
    def _fetch(u: str):
        domain = requests.utils.urlparse(u).netloc
        # Simple throttle per domain
        elapsed = time.time() - last_request[domain]
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        date = fetch_date_for_url(u)
        last_request[domain] = time.time()
        return u, date
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(_fetch, u): u for u in urls}
        for future in as_completed(future_to_url):
            u, date = future.result()
            results[u] = date
    return results

if __name__ == "__main__":
    # Example usage: read a markdown file and output URL→date JSON
    import sys
    if len(sys.argv) != 2:
        print("Usage: python fetch_job_dates.py <markdown_file>")
        sys.exit(1)
    md_path = pathlib.Path(sys.argv[1])
    urls = extract_urls_from_markdown(md_path.read_text(encoding="utf-8"))
    dates = fetch_dates_for_urls(urls)
    print(json.dumps({u: d.isoformat() if d else None for u, d in dates.items()}, indent=2))
