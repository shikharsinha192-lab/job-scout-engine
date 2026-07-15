import json
import re
import requests
from bs4 import BeautifulSoup
import time

companies = [
    "ARQ multi-currency digital wallet",
    "Ease Health behavioral health EHR",
    "Enginy AI B2B sales",
    "Physical Intelligence robotics",
    "Rundoo building-materials",
    "k-ID age assurance",
    "april embedded AI tax software",
    "Reflow AI workforce productivity",
    "HIFI multi-chain payment",
    "Callosum heterogeneous AI",
    "Fundamental enterprise forecasting",
    "Natural payment rails",
    "Valid AI digital ad creation",
    "Synquery AI matching",
    "Upscale AI workload networking",
    "Nous Research open-source models",
    "MatX chips for LLMs",
    "Memories.ai video analysis",
    "Rippletide decision graph",
    "WisdomAI natural-language analytics",
    "Joyful Health AI revenue recovery",
    "evroc European hyperscale cloud",
    "QuiverAI generative AI vector graphics",
    "FutureSearch LLM agents",
    "Guild.ai control plane",
    "Larridin measuring AI adoption",
    "Runlayer security governance",
    "SolveAI enterprise conversational",
    "Deeptune training gyms",
    "Fulcrum AI automation insurance"
]

import urllib.parse

def search(query, num_results=3):
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    results = []
    for a in soup.find_all('a', class_='result__url', limit=num_results):
        href = a.get('href')
        if href:
            if href.startswith('//'): href = 'https:' + href
            results.append(href)
    return results

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

results = {}

for comp in companies:
    query = f"{comp} careers OR jobs"
    print(f"Searching for: {comp}")
    found_urls = []
    try:
        for url in search(query, num_results=3):
            if any(ats in url.lower() for ats in ['lever.co', 'greenhouse.io', 'ashbyhq.com', 'workable.com', 'breezy.hr', 'careers', 'jobs']):
                found_urls.append(url)
    except Exception as e:
        print(f"Error searching {comp}: {e}")
    
    results[comp] = found_urls
    time.sleep(1) # Be nice to google

with open("startup_urls.json", "w") as f:
    json.dump(results, f, indent=4)

print("Saved URLs to startup_urls.json")
