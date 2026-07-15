import os
import sys
from dotenv import load_dotenv
from apify_client import ApifyClient
import gspread
from google.oauth2.service_account import Credentials

# 1. Load the local environment variables securely
load_dotenv()

TOKEN = os.getenv("APIFY_API_TOKEN")
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
CREDS_PATH = os.getenv("GOOGLE_SHEETS_CREDENTIALS")

if not all([TOKEN, SHEET_ID, CREDS_PATH]):
    print("[!] CRITICAL ERROR: Missing variables in .env file.")
    sys.exit(1)

# 2. Configure the Target Apify Actor (Free Tier Friendly)
ACTOR_ID = "cheap_scraper/linkedin-job-scraper"
search_query = sys.argv[1] if len(sys.argv) > 1 else "Performance Marketer"

import urllib.parse
encoded_query = urllib.parse.quote(search_query)
start_url = f"https://www.linkedin.com/jobs/search/?keywords={encoded_query}&location=India"

run_input = {
    "startUrls": [{"url": start_url}],
    "maxItems": 150,  # Minimum 150 required by the actor
}

def main():
    print(f"[*] Initiating Engine... Target: '{search_query}'")
    
    # 3. Authenticate with Google Sheets
    print("[*] Authenticating with Google Sheets API...")
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    try:
        creds = Credentials.from_service_account_file(CREDS_PATH, scopes=scopes)
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(SHEET_ID).sheet1
    except Exception as e:
        print(f"[!] Google Sheets Authentication Failed: {e}")
        sys.exit(1)

    # 4. Execute Apify Network Request
    print(f"[*] Firing Apify Actor: {ACTOR_ID}")
    client = ApifyClient(TOKEN)
    
    try:
        run = client.actor(ACTOR_ID).call(run_input=run_input)
        dataset_id = run.default_dataset_id
        print(f"[*] Data retrieved successfully. Parsing dataset: {dataset_id}")
    except Exception as e:
        print(f"[!] Apify Execution Failed: {e}")
        sys.exit(1)

    # 5. Parse, Clean, and Upload Data
    print("\n--- INGESTION REPORT ---")
    results = []
    
    for item in client.dataset(dataset_id).iterate_items():
        title = item.get("jobTitle", "Unknown Title")
        company = item.get("companyName", "Unknown Company")
        location = item.get("location", "Remote/India")
        url = item.get("jobUrl", "No URL")
        
        # Format for Google Sheets (Row Array)
        row_data = [title, company, location, url]
        results.append(row_data)
        
        # Print minimalist markdown to terminal
        print(f"- **{title}** at {company} ({location})")
        print(f"  Link: {url}\n")

    if results:
        print(f"[*] Pushing {len(results)} rows to Google Sheets...")
        sheet.append_rows(results)
        print("[*] Operation Complete. Database updated.")
    else:
        print("[!] No jobs found for this query.")

if __name__ == "__main__":
    main()
