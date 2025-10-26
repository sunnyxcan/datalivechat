# api/app.py

from datetime import datetime
from flask import Flask

from .config import (
    RANGE_KESALAHAN_DEFAULT, RANGE_STAFF_DEFAULT, DATABASE_URL,
    SCOPES, SPREADSHEET_ID
)
from .database import db, get_global_config
from .sheets_api import init_sheets_service
from .filters import render_cell, format_number

# --- INISIALISASI APLIKASI FLASK ---
app = Flask(__name__, static_folder='../static')
app.config['SECRET_KEY'] = 'ganti_dengan_kunci_rahasia_yang_kuat'

# --- KONFIGURASI DATABASE ---
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app) 

# --- VARIABEL GLOBAL ---
GLOBAL_SPREADSHEET_ID = SPREADSHEET_ID
GLOBAL_SCOPES = SCOPES
GLOBAL_RANGE_KESALAHAN = RANGE_KESALAHAN_DEFAULT
GLOBAL_RANGE_STAFF = RANGE_STAFF_DEFAULT
SHEETS_SERVICE = None

def load_global_config():
    """Memuat dan menimpa variabel global dengan nilai dari database."""
    global GLOBAL_SPREADSHEET_ID, GLOBAL_SCOPES, GLOBAL_RANGE_KESALAHAN, GLOBAL_RANGE_STAFF
    
    config = get_global_config()
    
    if config:
        if 'SPREADSHEET_ID' in config:
            GLOBAL_SPREADSHEET_ID = config['SPREADSHEET_ID']
            
        if 'SCOPES' in config and isinstance(config['SCOPES'], list):
            GLOBAL_SCOPES = config['SCOPES']
        
        if 'RANGE_KESALAHAN_DEFAULT' in config:
            GLOBAL_RANGE_KESALAHAN = config['RANGE_KESALAHAN_DEFAULT']

        if 'RANGE_STAFF_DEFAULT' in config:
            GLOBAL_RANGE_STAFF = config['RANGE_STAFF_DEFAULT']

def init_sheets_api_service():
    """Inisialisasi ulang Sheets Service."""
    global SHEETS_SERVICE
    try:
        SHEETS_SERVICE = init_sheets_service(GLOBAL_SPREADSHEET_ID, GLOBAL_SCOPES)
    except Exception:
        SHEETS_SERVICE = None

def init_db_and_services():
    """Inisialisasi database: membuat tabel jika belum ada dan memuat konfigurasi global."""
    db.create_all()
    load_global_config()
    init_sheets_api_service()

with app.app_context():
    try:
        init_db_and_services()
    except Exception:
        pass

# --- FILTER DAN GLOBAL JINJA2 ---
app.jinja_env.globals['current_year'] = datetime.now().year
app.jinja_env.filters['render_cell'] = render_cell
app.jinja_env.filters['format_number'] = format_number
app.jinja_env.globals['enumerate'] = enumerate