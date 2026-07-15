import requests
import time
import json
from pathlib import Path

CLIENT_ID = "4084ce14581a2c08d5940c5963fd2796"
CLIENT_SECRET = "b84924327695f466ed88b5f4b0c153d6"
DOMAINS = ["sprinto.com", "cactusglobal.com", "packt.com", "intempt.com", "virtualvocations.com"]
OUTPUT_FILE = Path("c:/Users/91639/Documents/antigravity/job-scout-engine/data/snov_contacts.json")

def get_token():
    resp = requests.post("https://api.snov.io/v1/oauth/access_token", data={
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    })
    return resp.json()["access_token"]

def fetch_domain_contacts(domain, token):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    start_resp = requests.post("https://api.snov.io/v2/domain-search/start", headers=headers, json={"domain": domain})
    if start_resp.status_code != 200:
        return {"domain": domain, "error": f"Failed to start: {start_resp.text}"}
    
    result_url = start_resp.json().get("links", {}).get("result")
    if not result_url:
        return {"domain": domain, "error": "No result URL"}
    
    attempts = 0
    while attempts < 15:
        res = requests.get(result_url, headers=headers)
        if res.status_code == 200:
            data = res.json()
            if "emails" in data or "data" in data or "company" in data:
                return data
        time.sleep(3)
        attempts += 1
    return {"domain": domain, "error": "Timeout"}

def main():
    try:
        token = get_token()
    except Exception as e:
        print("Failed to auth", e)
        return
    
    results = {}
    for d in DOMAINS:
        print(f"Fetching {d}...")
        results[d] = fetch_domain_contacts(d, token)
        
    OUTPUT_FILE.write_text(json.dumps(results, indent=2))
    print("Done")

if __name__ == "__main__":
    main()
