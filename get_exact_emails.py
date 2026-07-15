import requests
import json
import time

targets = [
    {"company": "Staffnixcom", "domain": "staffnixcom.com", "name": "Mayank Choudhary"},
    {"company": "MyOperator", "domain": "myoperator.com", "name": "Vijay Muthu"},
    {"company": "Timble Technologies", "domain": "timbletechnologies.com", "name": "Shefali Gupta"},
    {"company": "Hashone Career", "domain": "hashonecareer.com", "name": "Madhavan I"},
    {"company": "Moshi Moshi", "domain": "moshimoshi.com", "name": "HR"},
    {"company": "Eco-Soap Bank", "domain": "ecosoapbank.org", "name": "Samir Lakhani"},
    {"company": "Zava AI", "domain": "zavaai.com", "name": "Rahul bhagchandani"},
    {"company": "TestMu AI", "domain": "lambdatest.com", "name": "Aliya Akhtar"},
    {"company": "Peak Hire Solutions", "domain": "peakhiresolutions.com", "name": "Dharati Thakkar"},
    {"company": "G2com", "domain": "g2.com", "name": "Ashish Sahu"},
    {"company": "Wordsburg Translations", "domain": "wordsburg.com", "name": "Priyanka choudhary"},
    {"company": "AdPushup", "domain": "adpushup.com", "name": "Sakshi Singh"},
    {"company": "EASYECOM", "domain": "easyecom.io", "name": "Shraddha Mahajan"},
    {"company": "Kinematic Digital", "domain": "kinematicdigital.com", "name": "Megha Bhatt"}
]

SNOV_CLIENT_ID = "4084ce14581a2c08d5940c5963fd2796"
SNOV_CLIENT_SECRET = "b84924327695f466ed88b5f4b0c153d6"
token = None

def get_snov_token():
    url = "https://api.snov.io/v1/oauth/access_token"
    payload = {"grant_type": "client_credentials", "client_id": SNOV_CLIENT_ID, "client_secret": SNOV_CLIENT_SECRET}
    try:
        return requests.post(url, data=payload).json().get("access_token")
    except:
        return None

def get_email_for_name(domain, first_name, last_name):
    # Snovio email finder endpoint
    url = "https://api.snov.io/v1/get-emails-from-names"
    payload = {
        "domain": domain,
        "firstName": first_name,
        "lastName": last_name
    }
    try:
        res = requests.post(url, data=payload, headers={"Authorization": f"Bearer {token}"})
        data = res.json()
        if data.get("emails"):
            return [e.get("email") for e in data["emails"]]
    except:
        pass
    return []

def run():
    global token
    token = get_snov_token()
    
    results = []
    
    for t in targets:
        first_name = t['name'].split()[0]
        last_name = " ".join(t['name'].split()[1:]) if len(t['name'].split()) > 1 else ""
        
        emails = get_email_for_name(t['domain'], first_name, last_name)
        
        if not emails:
            # Generate OSINT fallbacks
            f_lower = first_name.lower()
            l_lower = last_name.lower()
            domain = t['domain']
            emails = []
            if l_lower:
                emails.append(f"{f_lower}.{l_lower}@{domain} (Guessed OSINT)")
                emails.append(f"{f_lower}{l_lower[0]}@{domain} (Guessed OSINT)")
            emails.append(f"{f_lower}@{domain} (Guessed OSINT)")
            emails.append(f"hr@{domain} (Fallback)")
            emails.append(f"careers@{domain} (Fallback)")
            
        results.append({
            "Company": t['company'],
            "Contact Person": t['name'],
            "Target Emails": emails
        })
        
    with open("exact_emails.json", "w") as f:
        json.dump(results, f, indent=4)
        
    print("Done generating exact emails.")

if __name__ == "__main__":
    run()
