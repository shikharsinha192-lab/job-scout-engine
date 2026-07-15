import streamlit as st
import os
import sys
import base64
import glob
import shutil

# Add parent to path to import backend logic
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.send_email import secure_smtp_send
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(layout="wide", page_title="Job Scout Dispatch Queue")

# Directory setup
base_dir = os.path.dirname(os.path.dirname(__file__))
email_pending_dir = os.path.join(base_dir, "output", "emails", "pending")
pdf_pending_dir = os.path.join(base_dir, "output", "resumes", "pending")

email_sent_dir = os.path.join(base_dir, "output", "emails", "archived", "sent")
email_rejected_dir = os.path.join(base_dir, "output", "emails", "archived", "rejected")
pdf_archived_dir = os.path.join(base_dir, "output", "resumes", "archived")

for d in [email_sent_dir, email_rejected_dir, pdf_archived_dir]:
    os.makedirs(d, exist_ok=True)

st.title("🚀 Outbound Dispatch Queue")

# Load queue
draft_files = sorted(glob.glob(os.path.join(email_pending_dir, "*.txt")))

if not draft_files:
    st.success("🎉 Queue is empty! Run the batch processor to load more jobs.")
    st.stop()

st.info(f"📬 **{len(draft_files)}** drafts remaining in queue.")

# Always show the first draft in the queue
current_draft_path = draft_files[0]
base_name = os.path.basename(current_draft_path)
company_part = base_name.replace("Outreach_", "").replace(".txt", "")

# We expect the attachment path to be defined inside the text file now, but we can also infer it
expected_pdf = os.path.join(pdf_pending_dir, f"Resume_{company_part}.pdf")

# Parse draft
with open(current_draft_path, "r", encoding="utf-8") as f:
    draft_content = f.read()

lines = draft_content.split('\n')
to_line = next((l for l in lines if l.startswith("To:")), "To: ")
subject_line = next((l for l in lines if l.startswith("Subject:")), "Subject: ")

body_start = draft_content.find("==")
body_start = draft_content.find("\n", body_start) + 1 if body_start != -1 else 0
body_text = draft_content[body_start:].strip()

def archive_files(dest_email_dir):
    # Move email
    shutil.move(current_draft_path, os.path.join(dest_email_dir, base_name))
    # Move PDF if exists
    if os.path.exists(expected_pdf):
        shutil.move(expected_pdf, os.path.join(pdf_archived_dir, os.path.basename(expected_pdf)))
    # JSON as well just to keep it clean
    expected_json = expected_pdf.replace(".pdf", ".json")
    if os.path.exists(expected_json):
        shutil.move(expected_json, os.path.join(pdf_archived_dir, os.path.basename(expected_json)))

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader(f"Reviewing: {company_part.replace('_', ' ')}")
    email_to = st.text_input("To:", value=to_line.replace("To:", "").strip())
    email_subject = st.text_input("Subject:", value=subject_line.replace("Subject:", "").strip())
    email_body = st.text_area("Body:", value=body_text, height=550)
    
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("🚀 Approve & Send", type="primary", use_container_width=True):
            sender_email = os.environ.get("GMAIL_EMAIL")
            sender_password = os.environ.get("GMAIL_APP_PASSWORD")
            
            if not sender_email or not sender_password:
                st.error("Credentials missing in .env file.")
            else:
                with st.spinner("Dispatching securely..."):
                    clean_email = sender_email.strip().strip('"').strip("'")
                    clean_pass = sender_password.strip().strip('"').strip("'")
                    
                    success = secure_smtp_send(
                        sender_email=clean_email,
                        sender_password=clean_pass,
                        receiver_email=email_to,
                        subject=email_subject,
                        body_text=email_body,
                        attachment_path=expected_pdf
                    )
                    if success:
                        archive_files(email_sent_dir)
                        st.rerun()
                    else:
                        st.error("Failed to send email. Check credentials and terminal logs.")
    with c2:
        if st.button("⏭️ Skip / Reject", use_container_width=True):
            archive_files(email_rejected_dir)
            st.rerun()

with col2:
    st.subheader("Attached ATS Resume")
    if os.path.exists(expected_pdf):
        with open(expected_pdf, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
    else:
        st.warning(f"Could not find matching PDF at {expected_pdf}")
