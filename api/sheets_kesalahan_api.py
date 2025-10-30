# api/sheets_kesalahan_api.py

import re
import sys 

from .app import SHEETS_SERVICE, KESALAHAN_SPREADSHEET_ID 
from .config import SHEETS_TO_HIDE
from .sheets_api import get_batch_sheet_data, get_sheet_data # Pastikan get_sheet_data tersedia


def _get_kesalahan_spreadsheet_id():
    """Mengambil ID Spreadsheet Kesalahan."""
    # Menambahkan validasi sederhana
    if not KESALAHAN_SPREADSHEET_ID:
        print("ERROR: KESALAHAN_SPREADSHEET_ID belum didefinisikan di config/app.", file=sys.stderr)
        return None
    return KESALAHAN_SPREADSHEET_ID

# ----------------------------------------------------
# 1. FUNGSI PENGAMBILAN SEMUA NAMA SHEET
# ----------------------------------------------------
def get_all_sheet_names():
    """
    Mengambil semua nama sheet dari Spreadsheet Kesalahan secara dinamis.

    Returns:
        list: Daftar nama sheet (str) yang sudah difilter.
    """
    if SHEETS_SERVICE is None:
        print("Sheets Service Gagal Diinisialisasi.", file=sys.stderr)
        return []
    
    spreadsheet_id = _get_kesalahan_spreadsheet_id()
    if not spreadsheet_id: return []

    try:
        # Menggunakan fields='sheets.properties.title' agar lebih cepat
        metadata = SHEETS_SERVICE.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields='sheets.properties.title'
        ).execute()
        
        # Ekstrak nama sheet
        sheet_names = [sheet.get('properties', {}).get('title') 
                       for sheet in metadata.get('sheets', [])]
        
        # Hapus sheet yang tidak relevan (berdasarkan SHEETS_TO_HIDE dari config)
        filtered_names = [name for name in sheet_names if name not in SHEETS_TO_HIDE]
        
        return filtered_names
        
    except Exception as e:
        print(f"ERROR: Gagal mengambil metadata spreadsheet: {e}", file=sys.stderr)
        return []
