# api/utils.py

from .app import (
    SHEETS_SERVICE, KESALAHAN_SHEETS_SERVICE,
    LIVECHAT_SPREADSHEET_ID, KESALAHAN_SPREADSHEET_ID
)
from .database import get_special_sheets
from .sheets_api import get_sheet_names


def get_all_sheet_names():
    """Mengambil daftar sheet dari Livechat dan Kesalahan untuk navigasi."""
    sheet_khusus = get_special_sheets()
    sheet_names_livechat = []
    kesalahan_sheet_names = []
    
    # 1. Sheet Livechat
    if SHEETS_SERVICE and LIVECHAT_SPREADSHEET_ID:
        try:
            # Mengambil sheet Livechat, melewati sheet yang ada di sheet_khusus
            sheet_names_livechat = get_sheet_names(SHEETS_SERVICE, sheet_khusus, LIVECHAT_SPREADSHEET_ID)
        except Exception as e:
            print(f"Peringatan: Gagal mengambil sheet Livechat: {e}")

    # 2. Sheet Kesalahan
    if KESALAHAN_SHEETS_SERVICE and KESALAHAN_SPREADSHEET_ID:
        try:
            # Sheet kesalahan tidak menggunakan filter sheet_khusus
            kesalahan_sheet_names = get_sheet_names(KESALAHAN_SHEETS_SERVICE, {}, KESALAHAN_SPREADSHEET_ID)
        except Exception as e:
            print(f"Peringatan: Gagal mengambil sheet Kesalahan: {e}")

    # Mengembalikan daftar nama sheet Livechat, Kesalahan, dan mapping sheet khusus
    return sheet_names_livechat, kesalahan_sheet_names, sheet_khusus