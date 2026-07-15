import sys
import argparse
import urllib.parse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

def generate_osint_queries(company_name, domain_name):
    # Standardize inputs
    company = company_name.strip()
    domain = domain_name.strip().replace("https://", "").replace("http://", "").replace("www.", "")
    if "/" in domain:
        domain = domain.split("/")[0]
        
    queries = [
        {
            "category": "LinkedIn Decision Makers",
            "query": f'site:linkedin.com/in/ "{company}" AND ("HR" OR "Recruiter" OR "Head of Growth" OR "Talent Acquisition" OR "Growth Director")',
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
            "query": f'site:linkedin.com/in/ "{company}" AND ("Founder" OR "CEO" OR "VP Growth" OR "VP Marketing")',
            "description": "Finds founders and key executives at early/mid-stage startups for direct outreach."
        }
    ]
    
    # Generate Google Search URLs
    for q in queries:
        encoded_query = urllib.parse.quote(q['query'])
        q['url'] = f"https://www.google.com/search?q={encoded_query}"
        
    return company, domain, queries

def display_hunter_panel(company_name, domain_name):
    company, domain, queries = generate_osint_queries(company_name, domain_name)
    
    console.print(Panel.fit(
        f"[bold gold1]🎯 HR HUNT INTEL ENGINE[/bold gold1]\n"
        f"Target Company: [cyan]{company}[/cyan]\n"
        f"Target Domain:  [cyan]{domain}[/cyan]",
        border_style="bold steel_blue"
    ))
    
    console.print("[yellow]The absolute most reliable OSINT technique is to perform directed Google Dorking in your browser to avoid programmatic CAPTCHA blocks.[/yellow]\n")
    
    table = Table(title="OSINT Google Dorking Links", show_header=True, header_style="bold deep_sky_blue1")
    table.add_column("Category", style="bold cyan", width=25)
    table.add_column("Dork Query Description", style="italic", width=40)
    table.add_column("Google Search URL (Ctrl+Click to Open)", style="underline blue", width=65)
    
    for q in queries:
        table.add_row(q['category'], q['description'], q['url'])
        
    console.print(table)
    
    # Common email conventions to show as reference
    console.print("\n[bold green]💡 Common Email Formats Reference:[/bold green]")
    console.print(f"  1. [bold]first.last@{domain}[/bold] (e.g., shikhar.sinha@{domain})")
    console.print(f"  2. [bold]first@{domain}[/bold] (e.g., shikhar@{domain})")
    console.print(f"  3. [bold]firstinitial.last@{domain}[/bold] (e.g., ssinha@{domain})")
    console.print(f"  4. [bold]jobs@{domain}[/bold] / [bold]careers@{domain}[/bold] (General fallback)")
    console.print("\n[bold yellow]Step 7 Action:[/bold yellow] Click the links above to find the contact name/email, then input it into the pipeline CLI when prompted.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate targeted OSINT Google Dorks for finding hiring manager contact emails.")
    parser.add_argument("--company", required=True, help="Target company name")
    parser.add_argument("--domain", required=True, help="Target company domain")
    
    args = parser.parse_args()
    display_hunter_panel(args.company, args.domain)
