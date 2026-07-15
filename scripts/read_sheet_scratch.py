import os
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()
sheet_id = os.getenv("GOOGLE_SHEET_ID")
gcp_credentials_path = os.getenv("GOOGLE_SHEETS_CREDENTIALS")

scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(gcp_credentials_path, scopes=scope)
gclient = gspread.authorize(creds)

sheet = gclient.open_by_key(sheet_id)
worksheet = sheet.worksheet("Master Report")
rows = worksheet.get_all_values()

# Print rows 48 to 52 (index 47 to 51)
print("ROWS 48 to 52:")
for i in range(47, 52):
    if i < len(rows):
        print(f"Row {i+1}: {rows[i]}")
    else:
        print(f"Row {i+1}: EMPTY")
