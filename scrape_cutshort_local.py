from bs4 import BeautifulSoup
import json
import re
import sys

file_path = r"C:\Users\91639\Downloads\Cutshort_ Making Top Professionals More Successful..html"

try:
    with open(file_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    # Let's try to extract JSON-LD or state data first, as Cutshort often embeds next.js state
    next_data = soup.find("script", id="__NEXT_DATA__")
    if next_data:
        try:
            data = json.loads(next_data.string)
            # navigate to jobs
            # usually in props.pageProps...
            # let's just dump it if possible or search for job objects
            dump_path = r"C:\Users\91639\Documents\antigravity\job-scout-engine\temp_cutshort_data.json"
            with open(dump_path, "w", encoding="utf-8") as out:
                json.dump(data, out)
            print("Successfully extracted Next.js state data.")
        except Exception as e:
            print(f"Failed to parse NEXT_DATA: {e}")

    # Alternatively, just look for job card elements visually if JSON fails
    print("Parsing via DOM elements...")
    job_cards = soup.find_all("div", class_=re.compile("JobCard_container", re.I)) 
    if not job_cards:
        # fallback class names, Cutshort uses different class structures
        job_cards = soup.find_all("div", attrs={"data-testid": "job-card"})
        if not job_cards:
            # Let's just find anything that looks like a job title
            job_cards = soup.find_all("div", class_=re.compile("card", re.I))

    print(f"Found {len(job_cards)} potential job cards.")

except Exception as e:
    print(f"Error reading or parsing HTML: {e}")
