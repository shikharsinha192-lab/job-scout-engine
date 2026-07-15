import os
import sys
import time
import logging
from apify_client import ApifyClient
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

# 1. Load the local environment variables from the .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseScraper:
    def __init__(self):
        """Initializes the Apify client and Google Sheets client."""
        # 2. Extract the securely loaded variables
        self.apify_token = os.getenv("APIFY_API_TOKEN")
        self.sheet_id = os.getenv("GOOGLE_SHEET_ID")
        self.gcp_credentials_path = os.getenv("GOOGLE_SHEETS_CREDENTIALS")

        if not self.apify_token:
            print("CRITICAL ERROR: APIFY_API_TOKEN is missing from the .env file.")
            sys.exit(1)
            
        self.client = ApifyClient(self.apify_token)
        
        # Initialize Google Sheets
        self.gclient = None
        if self.sheet_id and self.gcp_credentials_path and os.path.exists(self.gcp_credentials_path):
            try:
                scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
                creds = Credentials.from_service_account_file(self.gcp_credentials_path, scopes=scope)
                self.gclient = gspread.authorize(creds)
            except Exception as e:
                logger.error(f"Failed to authenticate with Google Sheets: {e}")
        else:
            logger.warning("Google Sheets credentials or Sheet ID missing. Data will not be saved to Sheets.")

    def execute_run(self, actor_id, run_input, max_retries=3):
        """Executes an Apify actor run with exponential backoff for network/API errors."""
        retries = 0
        backoff_factor = 2

        while retries <= max_retries:
            try:
                logger.info(f"Starting run for actor {actor_id} (Attempt {retries + 1})")
                run = self.client.actor(actor_id).call(run_input=run_input)
                
                # Fetch results
                dataset_id = run.default_dataset_id
                logger.info(f"Run finished. Fetching dataset {dataset_id}")
                dataset_items = self.client.dataset(dataset_id).iterate_items()
                return list(dataset_items)
            
            except Exception as e:
                logger.warning(f"Error calling actor {actor_id}: {e}")
                retries += 1
                if retries > max_retries:
                    logger.error(f"Max retries reached for actor {actor_id}. Failing.")
                    raise
                
                sleep_time = backoff_factor ** retries
                logger.info(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
            except Exception as e:
                 logger.error(f"Unexpected error executing run: {e}")
                 raise

    def save_to_sheets(self, data, platform_name):
        """Pushes structured data to Google Sheets."""
        if not self.gclient or not self.sheet_id:
            logger.warning(f"Skipping save_to_sheets for {platform_name} - GS connection not initialized.")
            return

        if not data:
            logger.info(f"No data to save for {platform_name}.")
            return

        try:
            sheet = self.gclient.open_by_key(self.sheet_id)
            
            # Master Report worksheet
            try:
                worksheet = sheet.worksheet("Master Report")
            except gspread.exceptions.WorksheetNotFound:
                worksheet = sheet.add_worksheet(title="Master Report", rows="1000", cols="20")
            
            # Convert list of dicts to list of lists for appending
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                headers = list(data[0].keys())
                
                import datetime
                date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                rows_to_append = []
                # Add section header with date
                rows_to_append.append([])
                rows_to_append.append([f"==== PLATFORM: {platform_name.upper()} ====", f"==== DATE: {date_str} ===="])
                rows_to_append.append(headers)
                
                for item in data:
                    row = [str(item.get(header, "")) for header in headers]
                    rows_to_append.append(row)
                
                if rows_to_append:
                    worksheet.append_rows(rows_to_append)
                    logger.info(f"Appended {len(rows_to_append)} rows to Master Report")
            else:
                logger.warning(f"Data format not supported for Sheets append: {type(data)}")
                
        except Exception as e:
            logger.error(f"Failed to save data to Google Sheets: {e}")

    def filter_by_last_2_weeks(self, data, date_keys=['postedAt', 'createdAt', 'date', 'publishDate', 'listDate']):
        import datetime
        import re
        filtered = []
        now = datetime.datetime.now()
        for item in data:
            date_val = None
            for k in date_keys:
                if item.get(k):
                    date_val = item.get(k)
                    break
            
            if not date_val:
                filtered.append(item)
                continue
                
            val_str = str(date_val).lower()
            keep = True
            
            if 'day' in val_str:
                num = re.search(r'\d+', val_str)
                if num and int(num.group()) > 14: keep = False
            elif 'week' in val_str:
                num = re.search(r'\d+', val_str)
                if num and int(num.group()) > 2: keep = False
            elif 'month' in val_str or 'year' in val_str:
                keep = False
            else:
                try:
                    iso_date = val_str.split('t')[0]
                    dt = datetime.datetime.strptime(iso_date, '%Y-%m-%d')
                    if (now - dt).days > 14: keep = False
                except:
                    pass
                try:
                    iso_date = val_str.split('t')[0]
                    dt = datetime.datetime.strptime(iso_date, '%Y/%m/%d')
                    if (now - dt).days > 14: keep = False
                except:
                    pass
            
            if keep:
                filtered.append(item)
                
        return filtered
