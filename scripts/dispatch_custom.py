import os
import sys
import argparse
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.send_email import secure_smtp_send

def main():
    parser = argparse.ArgumentParser(description="Directly dispatch a custom email draft via secure SMTP.")
    parser.add_argument("--email", required=True, help="Recipient email address")
    parser.add_argument("--subject", required=True, help="Email subject line")
    parser.add_argument("--body_file", required=True, help="Path to text file containing the email body")
    parser.add_argument("--pdf", required=True, help="Path to resume PDF file to attach")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.body_file):
        print(f"Error: Body file not found at: {args.body_file}")
        sys.exit(1)
        
    if not os.path.exists(args.pdf):
        print(f"Error: Resume PDF not found at: {args.pdf}")
        sys.exit(1)
        
    with open(args.body_file, "r", encoding="utf-8") as f:
        body_text = f.read()
        
    env_email = os.environ.get("GMAIL_EMAIL")
    env_password = os.environ.get("GMAIL_APP_PASSWORD")
    
    if not env_email or not env_password:
        print("Error: GMAIL_EMAIL and GMAIL_APP_PASSWORD must be configured in your .env file.")
        sys.exit(1)
        
    print(f"\n📧 Custom Outreach Dispatch")
    print(f"To:         {args.email}")
    print(f"Subject:    {args.subject}")
    print(f"Attachment: {args.pdf}")
    print("-" * 40)
    
    success = secure_smtp_send(
        sender_email=env_email.strip(),
        sender_password=env_password.strip(),
        receiver_email=args.email.strip(),
        subject=args.subject.strip(),
        body_text=body_text.strip(),
        attachment_path=args.pdf.strip()
    )
    
    if success:
        print("\n🚀 CUSTOM DISPATCH SUCCESSFUL!")
    else:
        print("\n✖ Custom Dispatch Failed.")

if __name__ == "__main__":
    main()
