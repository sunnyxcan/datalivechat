# api/routes.py

import re
from urllib.parse import unquote
from flask import render_template, redirect, url_for, request, flash
import math

from .app import (
    app, SHEETS_SERVICE, KESALAHAN_SHEETS_SERVICE,
    LIVECHAT_SPREADSHEET_ID, LIVECHAT_RANGE_KESALAHAN, LIVECHAT_RANGE_STAFF,
    KESALAHAN_SPREADSHEET_ID,
    load_global_config, init_sheets_api_service, init_kesalahan_sheets_service
)
from .config import SUMMARY_LIVECHAT_ROUTE, TARGET_KESALAHAN_HEADERS, KHUSUS_KESALAHAN_HEADERS 
from .database import (
    get_special_sheets, SiteConfig, SpecialSheet,
    get_global_config, update_global_config,
    update_or_add_site_config, delete_site_config,
    update_or_add_special_sheet, delete_special_sheet
)
from .sheets_api import (
    get_sheet_names, get_sheet_data,
    get_batch_sheet_data, calculate_sheet_total
)
from .filters import format_number


# =========================================================================
# IMPOR MODUL RUTE LAIN
# =========================================================================

from . import routes_main      # Berisi: home, show_db_config, show_summary_livechat
from . import routes_livechat  # Berisi: show_data
from . import routes_kesalahan # Berisi: get_kesalahan_sheet_names, show_kesalahan_data

# File ini hanya bertindak sebagai pengumpul rute.