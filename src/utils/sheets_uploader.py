from __future__ import annotations
import os
import pickle
from pathlib import Path
from typing import Optional

import pandas as pd

# Google Sheets imports (optional)
try:
    import gspread
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    SHEETS_AVAILABLE = True
except ImportError:
    SHEETS_AVAILABLE = False

# Google Sheets configuration
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file"]

def upload_to_sheets(csv_path: Path, sheet_id: Optional[str] = None, creds_path: Optional[str] = None) -> bool:
    """Upload CSV results to Google Sheets. Returns True if successful."""
    
    # Get configuration from environment if not provided
    if not sheet_id:
        sheet_id = os.getenv("GOOGLE_SHEET_ID", "") or os.getenv("SPREADSHEET_ID", "")
    
    if not creds_path:
        creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json") or os.getenv("CREDENTIALS_PATH", "credentials.json")
    
    # Validation checks
    if not SHEETS_AVAILABLE:
        print("⚠️  Google Sheets libraries not available. Install with: pip install gspread google-auth-oauthlib")
        return False
    
    if not sheet_id:
        print("⚠️  Google Sheets ID not configured. Set GOOGLE_SHEET_ID or SPREADSHEET_ID in .env")
        return False
    
    if not csv_path.exists():
        print(f"❌ CSV file not found: {csv_path}")
        return False
    
    try:
        print("📊 Uploading results to Google Sheets...")
        
        # Load CSV data
        df = pd.read_csv(csv_path)
        if df.empty:
            print("⚠️  CSV file is empty, nothing to upload")
            return False
        
        # Authenticate with Google
        creds = None
        token_path = "token.pickle"
        
        if os.path.exists(token_path):
            with open(token_path, "rb") as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and getattr(creds, "refresh_token", None):
                creds.refresh(Request())
            else:
                if not os.path.exists(creds_path):
                    print(f"❌ Credentials file not found: {creds_path}")
                    return False
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(token_path, "wb") as token:
                pickle.dump(creds, token)
        
        # Upload to sheets
        gc = gspread.authorize(creds)
        ws = gc.open_by_key(sheet_id).sheet1
        ws.clear()
        ws.update("A1", [df.columns.tolist()] + df.astype(str).values.tolist())
        ws.freeze(rows=1)
        
        print(f"✅ Successfully uploaded {len(df)} rows to Google Sheets!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to upload to Google Sheets: {e}")
        return False

def get_sheets_config() -> tuple[str, str]:
    """Get Google Sheets configuration from environment variables."""
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "") or os.getenv("SPREADSHEET_ID", "")
    creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json") or os.getenv("CREDENTIALS_PATH", "credentials.json")
    return sheet_id, creds_path

def is_sheets_configured() -> bool:
    """Check if Google Sheets is properly configured."""
    sheet_id, creds_path = get_sheets_config()
    return bool(sheet_id and os.path.exists(creds_path) and SHEETS_AVAILABLE)

def main():
    """Command-line interface for manual uploads."""
    import sys
    from pathlib import Path
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Get CSV path from environment or command line
    csv_path = os.getenv("RESULTS_CSV", "results/face_results.csv")
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    
    csv_file = Path(csv_path)
    
    print(f"🚀 Manual Google Sheets Upload")
    print(f"📁 CSV file: {csv_file}")
    
    success = upload_to_sheets(csv_file)
    
    if success:
        print("🎉 Upload completed successfully!")
        sys.exit(0)
    else:
        print("❌ Upload failed. Check configuration and try again.")
        sys.exit(1)

if __name__ == "__main__":
    main()
