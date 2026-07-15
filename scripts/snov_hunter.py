import requests
import time
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import urllib.parse

console = Console()

def authenticate_snov():
    url = "https://api.snov.io/v1/oauth/access_token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": "4084ce14581a2c08d5940c5963fd2796",
        "client_secret": "b84924327695f466ed88b5f4b0c153d6"
    }
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("access_token")
    except Exception as e:
        console.print(f"[bold red]Failed to authenticate with Snov.io: {e}[/bold red]")
        return None

def retrieve_snov_contacts(company_name, domain_name):
    console.print(Panel.fit(
        f"[bold gold1]🎯 SNOV.IO CONTACT HUNTER[/bold gold1]\n"
        f"Target Company: [cyan]{company_name}[/cyan]\n"
        f"Target Domain:  [cyan]{domain_name}[/cyan]",
        border_style="bold steel_blue"
    ))
    
    with console.status("[bold cyan]Authenticating with Snov.io API...", spinner="dots"):
        token = authenticate_snov()
        
    if not token:
        console.print("[red]Authentication failed. Falling back to OSINT instructions.[/red]")
        return False
        
    headers = {"Authorization": f"Bearer {token}"}
    
    with console.status(f"[bold cyan]Initiating search for {domain_name}...", spinner="dots"):
        start_url = "https://api.snov.io/v2/domain-search/start"
        payload = {"domain": domain_name}
        try:
            res = requests.post(start_url, json=payload, headers=headers)
            res.raise_for_status()
            start_data = res.json()
            result_url = start_data.get("links", {}).get("result")
            if not result_url:
                console.print(f"[bold red]Snov.io API error: Could not find result URL in response.[/bold red]")
                return False
        except Exception as e:
            console.print(f"[bold red]Failed to initiate Snov.io search: {e}[/bold red]")
            return False

    with console.status(f"[bold cyan]Polling for results (this may take a moment)...", spinner="bouncingBar"):
        attempts = 0
        final_data = None
        while attempts < 10:
            try:
                poll_res = requests.get(result_url, headers=headers)
                poll_res.raise_for_status()
                poll_data = poll_res.json()
                
                # Check if search is complete. The exact structure depends on the API, 
                # but usually there's a status or we just check if 'emails' array exists.
                # Assuming standard domain search response structure for Snov.io
                if isinstance(poll_data, dict) and "emails" in poll_data:
                    final_data = poll_data.get("emails", [])
                    break
                elif isinstance(poll_data, list):
                     final_data = poll_data
                     break
                     
                time.sleep(3)
                attempts += 1
            except Exception as e:
                console.print(f"[bold red]Error during polling: {e}[/bold red]")
                return False
                
    if final_data is None:
        console.print("[bold red]Polling timed out. Could not retrieve contacts.[/bold red]")
        return False
        
    # Process and filter data
    filtered_contacts = []
    generic_aliases = ['info', 'contact', 'hello', 'sales', 'support', 'admin', 'team', 'help']
    
    for item in final_data:
        # Structure varies, adapting to likely fields
        first_name = item.get("first_name", "")
        last_name = item.get("last_name", "")
        position = item.get("position", "")
        email = item.get("email", "")
        status = item.get("status", "") # e.g., 'valid'
        
        if not email:
            continue
            
        local_part = email.split('@')[0].lower()
        if any(alias in local_part for alias in generic_aliases):
            continue
            
        # Optional: strictly enforce verified/valid if the API provides it
        if status and status != "valid" and status != "verified":
             continue
             
        score = 0
        pos_lower = position.lower()
        if any(kw in pos_lower for kw in ['growth', 'marketing', 'hr', 'talent', 'founder', 'ceo', 'director', 'vp', 'head']):
            score = 1
            
        filtered_contacts.append({
            "name": f"{first_name} {last_name}".strip() or "Unknown",
            "position": position or "Unknown",
            "email": email,
            "score": score
        })
        
    # Sort by relevance
    filtered_contacts.sort(key=lambda x: x['score'], reverse=True)
    
    if not filtered_contacts:
        console.print("[yellow]No relevant contacts found for this domain.[/yellow]")
        return False
        
    table = Table(title="Snov.io Verified Contacts", show_header=True, header_style="bold deep_sky_blue1")
    table.add_column("Name", style="bold cyan")
    table.add_column("Position", style="italic")
    table.add_column("Email", style="underline green")
    
    # Show top 10
    for c in filtered_contacts[:10]:
        table.add_row(c['name'], c['position'], c['email'])
        
    console.print(table)
    return True

def display_hunter_panel(company_name, domain_name):
    # Try Snov.io first
    success = retrieve_snov_contacts(company_name, domain_name)
    
    if not success:
        # Fallback to original hr_hunter behavior if Snov fails or finds nothing
        console.print("\n[yellow]Falling back to manual OSINT Dorking...[/yellow]\n")
        
        # We need to inline the OSINT generation here to avoid circular imports if replacing hr_hunter
        domain = domain_name.strip().replace("https://", "").replace("http://", "").replace("www.", "")
        if "/" in domain:
            domain = domain.split("/")[0]
            
        queries = [
            {
                "category": "LinkedIn Decision Makers",
                "query": f'site:linkedin.com/in/ "{company_name}" AND ("HR" OR "Recruiter" OR "Head of Growth" OR "Talent Acquisition" OR "Growth Director")',
                "description": "Finds hiring managers, recruiters, or growth heads on LinkedIn."
            },
            {
                "category": "Email Format / Harvester",
                "query": f'"{domain}" AND ("@email" OR "email format" OR "contact" OR "hiring")',
                "description": "Searches for the corporate email format (e.g. first.last@company.com)."
            },
            {
                "category": "Direct Email Harvest",
                "query": f'"@{domain}" AND ("HR" OR "recruitment" OR "careers" OR "jobs")',
                "description": "Targets direct mailbox mentions published openly on the web."
            },
            {
                "category": "Hiring Manager Outbound",
                "query": f'site:linkedin.com/in/ "{company_name}" AND ("Founder" OR "CEO" OR "VP Growth" OR "VP Marketing")',
                "description": "Finds founders and key executives at early/mid-stage startups for direct outreach."
            }
        ]
        
        for q in queries:
            encoded_query = urllib.parse.quote(q['query'])
            q['url'] = f"https://www.google.com/search?q={encoded_query}"
            
        table = Table(title="OSINT Google Dorking Links", show_header=True, header_style="bold deep_sky_blue1")
        table.add_column("Category", style="bold cyan", width=25)
        table.add_column("Dork Query Description", style="italic", width=40)
        table.add_column("Google Search URL (Ctrl+Click to Open)", style="underline blue", width=65)
        
        for q in queries:
            table.add_row(q['category'], q['description'], q['url'])
            
        console.print(table)
        
        console.print("\n[bold green]💡 Common Email Formats Reference:[/bold green]")
        console.print(f"  1. [bold]first.last@{domain}[/bold] (e.g., shikhar.sinha@{domain})")
        console.print(f"  2. [bold]first@{domain}[/bold] (e.g., shikhar@{domain})")
        console.print(f"  3. [bold]firstinitial.last@{domain}[/bold] (e.g., ssinha@{domain})")
        console.print(f"  4. [bold]jobs@{domain}[/bold] / [bold]careers@{domain}[/bold] (General fallback)")
        console.print("\n[bold yellow]Step 7 Action:[/bold yellow] Click the links above to find the contact name/email, then input it into the pipeline CLI when prompted.")
