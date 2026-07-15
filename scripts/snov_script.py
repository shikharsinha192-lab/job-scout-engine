import requests
import time
import sys

def get_snov_token():
    url = "https://api.snov.io/v1/oauth/access_token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": "4084ce14581a2c08d5940c5963fd2796",
        "client_secret": "b84924327695f466ed88b5f4b0c153d6"
    }
    resp = requests.post(url, data=payload)
    return resp.json().get("access_token")

def search_domain(domain, token):
    url = "https://api.snov.io/v2/domain-search/start"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"domain": domain}
    
    resp = requests.post(url, headers=headers, json=payload)
    data = resp.json()
    
    result_url = data.get("links", {}).get("result")
    if not result_url:
        print(f"[{domain}] Failed to start search:", data)
        return []
        
    for _ in range(10):
        time.sleep(3)
        res = requests.get(result_url, headers=headers)
        res_data = res.json()
        if "data" in res_data and isinstance(res_data["data"], list):
            return res_data["data"]
            
    print(f"[{domain}] Polling timed out.")
    return []

def main():
    domains = ["sprinto.com", "razorpay.com", "unitedhealthgroup.com"]
    token = get_snov_token()
    if not token:
        print("Failed to get token")
        sys.exit(1)
        
    for domain in domains:
        print(f"Searching {domain}...")
        contacts = search_domain(domain, token)
        found = False
        for c in contacts:
            pos = str(c.get('position', '')).lower()
            if 'hr' in pos or 'recruiter' in pos or 'growth' in pos or 'marketing' in pos or 'founder' in pos or 'talent' in pos:
                print(f"  -> {c.get('first_name')} {c.get('last_name')} | {c.get('position')} | {c.get('email')}")
                found = True
        if not found:
            print("  -> No matching HR/Growth/Founder contacts found.")

if __name__ == "__main__":
    main()
