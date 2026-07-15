from bs4 import BeautifulSoup

file_path = r"C:\Users\91639\Downloads\Cutshort_ Making Top Professionals More Successful..html"

with open(file_path, "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")
jobs = []

# Try to find all standalone job blocks. Cutshort often wraps them in an 'a' tag or a generic div with a specific flex layout.
# We will just traverse all tags that have children containing 'yrs' and 'L' or '₹'
for el in soup.find_all(lambda tag: tag.name in ['div', 'a'] and len(tag.find_all(recursive=False)) > 1):
    text = el.get_text(separator="|")
    if "yrs" in text and "₹" in text and ("Save for later" in text or "View details" in text or "yr" in text):
        parts = [p.strip() for p in text.split("|") if p.strip()]
        # To avoid duplicates and deeply nested identical tags, we only keep it if it looks like a complete card (~10-50 parts)
        if 5 < len(parts) < 100:
            jobs.append(parts)

# Deduplicate
unique_jobs = []
seen = set()
for j in jobs:
    # First few items usually contain company and title
    key = tuple(j[:4])
    if key not in seen:
        seen.add(key)
        unique_jobs.append(j)

for idx, j in enumerate(unique_jobs):
    print(f"--- JOB {idx+1} ---")
    print("\n".join(j[:15]))  # Print first 15 segments
    print("...")
