import os
import sys
import re
import tempfile
import shutil
from reportlab.lib.enums import TA_CENTER
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.text import Text

# Import local scripts
from scripts import generate_pdf, tailor_resume, snov_hunter as hr_hunter, send_email

console = Console()

def parse_listings_file(file_path, target_id):
    if not os.path.exists(file_path):
        return None
        
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line.startswith('|'):
                continue
            
            # Match rows like: | 1 | ... or | 130 | ...
            parts = [p.strip() for p in line.split('|')]
            if len(parts) < 6:
                continue
                
            try:
                row_id = int(parts[1])
                if row_id == target_id:
                    return {
                        "id": row_id,
                        "raw_title_company": parts[2],
                        "salary": parts[3],
                        "link": parts[4],
                        "rationale": parts[5]
                    }
            except ValueError:
                continue
    return None

def clean_title_company(raw_text):
    # e.g., "**Growth Marketer** — Sprinto (Remote, India)"
    # Strip markdown bold
    cleaned = raw_text.replace("**", "").strip()
    
    # Split on em-dash, en-dash, or standard hyphen
    split_chars = ["—", "–", "-"]
    title = cleaned
    company = "Target Company"
    
    for char in split_chars:
        if char in cleaned:
            parts = cleaned.split(char, 1)
            title = parts[0].strip()
            company = parts[1].strip()
            break
            
    # Clean company location e.g. "Sprinto (Remote, India)" -> "Sprinto"
    if "(" in company:
        company = company.split("(", 1)[0].strip()
        
    return title, company

def get_job_intel(job_id):
    # Choose file based on ID
    if 1 <= job_id <= 50:
        file_path = os.path.join("data", "job_listings_1_50.md")
    elif 51 <= job_id <= 150:
        file_path = os.path.join("data", "job_listings_51_150.md")
    else:
        console.print(f"[bold red]Error: Invalid Job ID {job_id}. ID must be between 1 and 150.[/bold red]")
        return None
        
    job_intel = parse_listings_file(file_path, job_id)
    if not job_intel:
        console.print(f"[bold red]Error: Could not locate Job ID {job_id} in {file_path}[/bold red]")
        return None
        
    # Extrapolate title and company
    title, company = clean_title_company(job_intel['raw_title_company'])
    job_intel['title'] = title
    job_intel['company'] = company
    
    return job_intel

def run_pipeline(job_id):
    console.print(Panel.fit(
        f"[bold gold1]🚀 Firing Recruiter Pipeline for Job ID #{job_id}[/bold gold1]",
        border_style="bold gold1"
    ))
    
    # --- STEP 1: PARSE JOB DATA ---
    job = get_job_intel(job_id)
    if not job:
        return
        
    console.print(f"[bold green]✓ Loaded Listing Details:[/bold green]")
    console.print(f"  [bold]Role:[/bold]       {job['title']}")
    console.print(f"  [bold]Company:[/bold]    {job['company']}")
    console.print(f"  [bold]Salary:[/bold]     {job['salary']}")
    console.print(f"  [bold]Rationale:[/bold]  {job['rationale']}")
    console.print(f"  [bold]Apply Link:[/bold] {job['link']}\n")
    
    # Confirm parsed details
    confirm_details = Confirm.ask("Do you want to use these details? (Enter 'N' to manually override company/role name)", default=True)
    if not confirm_details:
        job['company'] = Prompt.ask("Enter company name", default=job['company'])
        job['title'] = Prompt.ask("Enter target role/job title", default=job['title'])
        
    # --- STEP 2: TAILOR RESUME ---
    console.print("\n[bold yellow]Step 5: Resume Customization & ATS Optimization[/bold yellow]")
    console.print("To tailor the resume, please paste the Job Description (JD).")
    console.print("[dim]Note: Paste JD below. Press Enter twice (an empty line) when finished to submit.[/dim]\n")
    
    jd_lines = []
    while True:
        line = sys.stdin.readline()
        if not line or line.strip() == "":
            break
        jd_lines.append(line)
    jd_text = "".join(jd_lines).strip()
    
    # Fallback to general JD if empty
    if not jd_text:
        console.print("[yellow]Empty job description provided. Generating a baseline optimized resume using match rationale...[/yellow]")
        jd_text = f"Role: {job['title']}\nCompany: {job['company']}\nKey requirements: Growth Marketing, Performance Marketing, paid media budget scaling, GA4/GTM attribution, conversion rate optimization (CRO), automation."
        
    # Write JD to a temporary file
    temp_jd = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
    temp_jd.write(jd_text)
    temp_jd_path = temp_jd.name
    temp_jd.close()
    
    # Paths for resume output
    clean_company_fn = re.sub(r'[^a-zA-Z0-9]', '_', job['company'])
    tailored_json_path = os.path.join("output", "resumes", f"Shikhar_Sinha_Resume_{clean_company_fn}.json")
    tailored_pdf_path = os.path.join("output", "resumes", f"Shikhar_Sinha_Resume_{clean_company_fn}.pdf")
    
    console.print("[cyan]Generating customized resume JSON utilizing Gemini AI...[/cyan]")
    tailor_resume.tailor_resume(
        base_json_path=os.path.join("data", "resume_base.json"),
        jd_text=jd_text,
        output_json_path=tailored_json_path
    )
    
    # Clean up temporary JD file
    try:
        os.remove(temp_jd_path)
    except:
        pass
        
    # --- STEP 3: PDF COMPILATION ---
    console.print("\n[bold yellow]Step 6: PDF Compiling & Layout Structuring[/bold yellow]")
    console.print("[cyan]Running ReportLab engine to generate clean professional single-page resume...[/cyan]")
    generate_pdf.build_pdf(tailored_json_path, tailored_pdf_path)
    
    # --- STEP 4: HR INTELLIGENCE HUNTING ---
    console.print("\n[bold yellow]Step 7: Search Recruiter Contact Email[/bold yellow]")
    # Run the OSINT Dorks generator
    domain_name = job['company'].lower().replace(" ", "") + ".com"
    domain_override = Prompt.ask(f"Confirm corporate domain name for OSINT Google Dorks", default=domain_name)
    
    hr_hunter.display_hunter_panel(job['company'], domain_override)
    
    # Gather recipient details
    console.print("\n[bold yellow]Outbound Recruiter Profile Intake[/bold yellow]")
    recruiter_email = Prompt.ask("Enter recipient's harvested email address (e.g. careers@company.com or first.last@company.com)")
    while not recruiter_email or "@" not in recruiter_email:
        console.print("[red]Invalid email address. Please enter a valid email.[/red]")
        recruiter_email = Prompt.ask("Enter recipient's email address")
        
    recruiter_name = Prompt.ask("Enter recipient's name (leave blank if unknown)", default="")
    
    # --- STEP 5: EMAIL OUTBOUND & SECURE SMTP DISPATCH ---
    console.print("\n[bold yellow]Step 8 & 9: Personalized Cold Email Outreach & Gmail Dispatch[/bold yellow]")
    draft_txt_path = os.path.join("output", "emails", f"Shikhar_Sinha_Outreach_{clean_company_fn}.txt")
    
    send_email.orchestrate_draft_and_send(
        recruiter_name=recruiter_name,
        company_name=job['company'],
        job_title=job['title'],
        receiver_email=recruiter_email,
        attachment_path=tailored_pdf_path,
        save_draft_path=draft_txt_path
    )

def main():
    console.print(Panel(
        f"[bold gold1]💼 JOB SCOUT CAREER ENGINE & RECRUITER OUTBOUND[/bold gold1]\n"
        f"[dim]Version 1.0 (CTO & CEO Executable Primitive)[/dim]",
        border_style="bold gold1",
        alignment=TA_CENTER
    ))
    
    # Auto-initialize directories and base template files if not present (off git fallback setup)
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    
    base_resume = os.path.join(data_dir, "resume_base.json")
    base_resume_example = os.path.join(data_dir, "resume_base.json.example")
    
    if not os.path.exists(base_resume):
        if os.path.exists(base_resume_example):
            console.print("[yellow]ℹ️ Initializing resume_base.json from example template...[/yellow]")
            shutil.copy(base_resume_example, base_resume)
            console.print("[green]✓ Created data/resume_base.json. Please edit this file with your own profile data.[/green]")
        else:
            console.print("[bold red]Fatal Error: Base resume data template not found at data/resume_base.json.[/bold red]")
            sys.exit(1)
            
    job_listings_1_50 = os.path.join(data_dir, "job_listings_1_50.md")
    job_listings_1_50_example = os.path.join(data_dir, "job_listings_1_50.md.example")
    
    if not os.path.exists(job_listings_1_50):
        if os.path.exists(job_listings_1_50_example):
            console.print("[yellow]ℹ️ Initializing job_listings_1_50.md from example template...[/yellow]")
            shutil.copy(job_listings_1_50_example, job_listings_1_50)
            console.print("[green]✓ Created data/job_listings_1_50.md. Please edit this file with your target jobs.[/green]")
        
    # Core operational menu
    console.print("[cyan]Menu:[/cyan]")
    console.print("  1. Run Outbound Recruitment Pipeline for a Listing (1-150)")
    console.print("  2. Regenerate Master Base PDF Resume")
    console.print("  3. Run Google OSINT Dorking for a Company")
    console.print("  4. Exit")
    
    choice = IntPrompt.ask("\nSelect operation", choices=[1, 2, 3, 4], default=1)
    
    if choice == 1:
        job_id = IntPrompt.ask("\nEnter Job Listing ID to target (1-150)")
        while not (1 <= job_id <= 150):
            console.print("[red]ID must be between 1 and 150.[/red]")
            job_id = IntPrompt.ask("Enter Job Listing ID")
        run_pipeline(job_id)
        
    elif choice == 2:
        output_pdf = os.path.join("output", "resumes", "Master_Resume.pdf")
        console.print(f"[cyan]Compiling Master Base Resume PDF to: {output_pdf}[/cyan]")
        generate_pdf.build_pdf(base_resume, output_pdf)
        console.print("[green]✓ Master resume PDF completed successfully![/green]")
        
    elif choice == 3:
        company = Prompt.ask("Enter company name")
        domain = Prompt.ask("Enter company corporate domain (e.g. company.com)")
        hr_hunter.display_hunter_panel(company, domain)
        
    elif choice == 4:
        console.print("[cyan]Closing Career Engine. Exiting...[/cyan]")
        sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Keyboard interrupt received. Gracefully exiting...[/yellow]")
        sys.exit(0)
