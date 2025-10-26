# api/sheets_api.py

import os
import json
import re

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .config import (
    SPREADSHEET_ID, CLIENT_SECRET_FILE, TOKEN_FILE, 
    SHEETS_TO_HIDE, SCOPES as DEFAULT_SCOPES 
)
from .database import get_global_config, get_special_sheets

# --- FUNGSI UTILITY UNTUK MEMUAT KONFIGURASI DINAMIS ---

def _load_dynamic_config():
    global_config = get_global_config()
    special_sheets = get_special_sheets()
    
    scopes = global_config.get('SCOPES', DEFAULT_SCOPES)
    spreadsheet_id = global_config.get('SPREADSHEET_ID', SPREADSHEET_ID)

    return scopes, special_sheets, spreadsheet_id

# --- FUNGSI GOOGLE SHEETS API ---

def init_sheets_service(spreadsheet_id=None, scopes=None):
    
    dynamic_scopes, _, dynamic_spreadsheet_id = _load_dynamic_config()
    
    current_scopes = scopes if scopes else dynamic_scopes
    
    creds = None
    
    # 1. Cek Environment Variables
    token_json_str = os.environ.get('TOKEN_JSON')
    client_secret_json_str = os.environ.get('CLIENT_SECRET_JSON')

    if token_json_str and client_secret_json_str:
        try:
            token_info = json.loads(token_json_str)
            creds = Credentials.from_authorized_user_info(token_info, current_scopes)
            
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                
        except Exception:
            creds = None

    # 2. Cek File Lokal
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.join(current_dir, '..') if os.path.basename(current_dir) == 'api' else current_dir
    
    local_token_path = os.path.join(project_root, TOKEN_FILE)
    local_client_secret_path = os.path.join(project_root, CLIENT_SECRET_FILE)
    
    if not creds and os.path.exists(local_token_path):
        creds = Credentials.from_authorized_user_file(local_token_path, current_scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(local_token_path, 'w') as token:
                    token.write(creds.to_json())
            except Exception:
                creds = None
        else:
            if os.path.exists(local_client_secret_path):
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        local_client_secret_path, current_scopes)
                    creds = flow.run_local_server(port=0)

                    with open(local_token_path, 'w') as token:
                        token.write(creds.to_json())
                except Exception:
                    return None
            else:
                return None 
    
    if not creds or not creds.valid:
        return None 

    return build('sheets', 'v4', credentials=creds)

def get_sheet_names(service, sheet_khusus=None, spreadsheet_id=None):
    if service is None:
        return []
        
    _, dynamic_sheet_khusus, dynamic_spreadsheet_id = _load_dynamic_config()
    
    current_sheet_khusus = sheet_khusus if sheet_khusus is not None else dynamic_sheet_khusus
    current_spreadsheet_id = spreadsheet_id if spreadsheet_id else dynamic_spreadsheet_id
    
    
    hide_set_stripped = {name.strip() for name in SHEETS_TO_HIDE}
    hide_set_no_space = {name.replace(' ', '').strip() for name in SHEETS_TO_HIDE}
    
    hide_set_stripped.update({name.strip() for name in current_sheet_khusus.keys()})
    
    try:
        spreadsheet_metadata = service.spreadsheets().get(
            spreadsheetId=current_spreadsheet_id
        ).execute()

        all_names = [sheet.get('properties', {}).get('title')
                     for sheet in spreadsheet_metadata.get('sheets', [])]

        filtered_names = []
        for name in all_names:
            if not name:
                continue
            
            if name.strip() not in hide_set_stripped and name.replace(' ', '').strip() not in hide_set_no_space:
                filtered_names.append(name)
        
        for name in current_sheet_khusus.keys():
            if name not in filtered_names:
                filtered_names.append(name)

        return filtered_names

    except Exception:
        return []

def get_sheet_data(service, sheet_name, range_name, expected_columns=None, spreadsheet_id=None):
    
    _, _, dynamic_spreadsheet_id = _load_dynamic_config()
    current_spreadsheet_id = spreadsheet_id if spreadsheet_id else dynamic_spreadsheet_id
    
    full_range_name = f"'{sheet_name}'!{range_name}"

    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=current_spreadsheet_id,
            range=full_range_name
        ).execute()
        
        values = result.get('values', [])
        filtered_values = [
            row for row in values if any(cell and cell.strip() for cell in row)
        ]

        if expected_columns and expected_columns > 0:
            cleaned_data = []
            for row in filtered_values:
                if len(row) < expected_columns:
                    padded_row = row + [''] * (expected_columns - len(row))
                else:
                    padded_row = row[:expected_columns]
                cleaned_data.append(padded_row)
            return cleaned_data

        return filtered_values

    except Exception:
        return []

def get_batch_sheet_data(service, ranges, spreadsheet_id=None):
    if not ranges:
        return []
        
    _, _, dynamic_spreadsheet_id = _load_dynamic_config()
    current_spreadsheet_id = spreadsheet_id if spreadsheet_id else dynamic_spreadsheet_id

    try:
        result = service.spreadsheets().values().batchGet(
            spreadsheetId=current_spreadsheet_id,
            ranges=ranges
        ).execute()
        
        return result.get('valueRanges', [])
        
    except Exception:
        return []

def calculate_sheet_total(staff_data):
    if not staff_data or len(staff_data) < 2:
        return 0, []

    staff_rows = staff_data[1:]
    total_kesalahan_staff = 0
    cleaned_rows = []
    is_total_row = False

    if staff_rows and len(staff_rows[0]) > 1:
        last_row = staff_rows[-1]
        try:
            if last_row and last_row[0] and last_row[0].strip().lower() == 'total':
                total_str = last_row[1].strip().replace(',', '')
                num_match = re.search(r'\d+', total_str)
                if num_match:
                    total_kesalahan_staff = int(num_match.group(0))
                    is_total_row = True
                cleaned_rows = staff_rows[:-1]
        except Exception:
            pass
        
        if not is_total_row:
            for row in staff_rows:
                if len(row) > 1:
                    num_str = re.sub(r'[^\d]', '', row[1].strip()) 
                    if num_str.isdigit():
                        total_kesalahan_staff += int(num_str)
                    cleaned_rows.append(row)

    return total_kesalahan_staff, cleaned_rows