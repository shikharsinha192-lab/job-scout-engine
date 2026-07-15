import requests
from bs4 import BeautifulSoup
import json
from deliverability_engine import process_company

def scrape_linkedin_jd(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0",
        "Accept-Language": "en-US,en;q=0.9"
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        jd_div = soup.find('div', class_='show-more-less-html__markup')
        if jd_div:
            return jd_div.get_text(separator='\n', strip=True)
    except:
        pass
    return "JD Not Found"

def run_batch():
    targets = [
        {"company": "Canary Digital.ai", "role": "Growth & Digital Marketing Lead", "url": "https://in.linkedin.com/jobs/view/growth-digital-marketing-lead-at-canary-digital-ai-4430333404"},
        {"company": "Animaker Inc.", "role": "Founding Growth Marketer", "url": "https://in.linkedin.com/jobs/view/founding-growth-marketer-at-animaker-inc-4428478123"},
        {"company": "Consuma", "role": "Growth Generalist", "url": "https://in.linkedin.com/jobs/view/growth-generalist-at-consuma-4428915430"},
        {"company": "Bambinos.live", "role": "Head of Growth", "url": "https://in.linkedin.com/jobs/view/head-of-growth-at-bambinos-live-future-school-4430369942"},
        {"company": "DrinkPrime", "role": "Growth Manager", "url": "https://in.linkedin.com/jobs/view/growth-manager-at-drinkprime-4430532954"}
    ]
    
    final_payload = []
    
    for t in targets:
        print(f"\n--- Scraping JD for {t['company']} ---")
        jd = scrape_linkedin_jd(t['url'])
        
        print(f"--- Running Deliverability Engine for {t['company']} ---")
        verifications = process_company(t['company'])
        
        final_payload.append({
            "company": t['company'],
            "role": t['role'],
            "jd": jd,
            "verifications": verifications
        })
        
    with open("batch_8_prep.json", "w", encoding="utf-8") as f:
        json.dump(final_payload, f, indent=4)
        
    print("\nBatch preparation complete. Payload saved to batch_8_prep.json.")

if __name__ == "__main__":
    run_batch()
