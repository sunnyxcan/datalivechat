# api/app.py

from datetime import datetime
from flask import Flask

from .config import (
    RANGE_LIVECHAT_DEFAULT, RANGE_STAFF_LIVECHAT, DATABASE_URL,
    SCOPES, SPREADSHEET_LIVECHAT,
    SPREADSHEET_KESALAHAN, RANGE_KESALAHAN_STAFF, RANGE_KESALAHAN_FATAL
)
from .database import db, get_global_config
from .sheets_api import init_sheets_service
from .filters import render_cell, format_number

app = Flask(__name__, static_folder='../static')
app.config['SECRET_KEY'] = 'ganti_dengan_kunci_rahasia_yang_kuat'

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app) 

LIVECHAT_SPREADSHEET_ID = SPREADSHEET_LIVECHAT
LIVECHAT_SCOPES = SCOPES
LIVECHAT_RANGE_KESALAHAN = RANGE_LIVECHAT_DEFAULT
LIVECHAT_RANGE_STAFF = RANGE_STAFF_LIVECHAT

KESALAHAN_SPREADSHEET_ID = SPREADSHEET_KESALAHAN
KESALAHAN_RANGE_STAFF = RANGE_KESALAHAN_STAFF
KESALAHAN_RANGE_FATAL = RANGE_KESALAHAN_FATAL

SHEETS_SERVICE = None
# Deklarasikan variabel global KESALAHAN_SHEETS_SERVICE
KESALAHAN_SHEETS_SERVICE = None


def load_global_config():
    global LIVECHAT_SPREADSHEET_ID, LIVECHAT_SCOPES, LIVECHAT_RANGE_KESALAHAN, LIVECHAT_RANGE_STAFF
    global KESALAHAN_SPREADSHEET_ID, KESALAHAN_RANGE_STAFF, KESALAHAN_RANGE_FATAL
    
    config = get_global_config()
    
    if config:
        # Konfigurasi Livechat (Lama)
        if 'SPREADSHEET_LIVECHAT' in config:
            LIVECHAT_SPREADSHEET_ID = config['SPREADSHEET_LIVECHAT']
            
        if 'SCOPES' in config and isinstance(config['SCOPES'], list):
            LIVECHAT_SCOPES = config['SCOPES']
        
        if 'RANGE_KESALAHAN_DEFAULT' in config:
            LIVECHAT_RANGE_KESALAHAN = config['RANGE_KESALAHAN_DEFAULT']

        if 'RANGE_STAFF_DEFAULT' in config:
            LIVECHAT_RANGE_STAFF = config['RANGE_STAFF_DEFAULT']
            
        # Konfigurasi Kesalahan (Baru)
        if 'SPREADSHEET_KESALAHAN' in config:
            KESALAHAN_SPREADSHEET_ID = config['SPREADSHEET_KESALAHAN']
            
        if 'RANGE_KESALAHAN_STAFF' in config:
            KESALAHAN_RANGE_STAFF = config['RANGE_KESALAHAN_STAFF']
            
        if 'RANGE_KESALAHAN_FATAL' in config:
            KESALAHAN_RANGE_FATAL = config['RANGE_KESALAHAN_FATAL']


def init_sheets_api_service():
    global SHEETS_SERVICE
    try:
        # Layanan untuk Livechat (SHEETS_SERVICE)
        SHEETS_SERVICE = init_sheets_service(LIVECHAT_SPREADSHEET_ID, LIVECHAT_SCOPES)
    except Exception:
        SHEETS_SERVICE = None
        
        
def init_kesalahan_sheets_service():
    global KESALAHAN_SHEETS_SERVICE
    try:
        # Layanan baru untuk Kesalahan (KESALAHAN_SHEETS_SERVICE)
        # Menggunakan ID Spreadsheet Kesalahan, namun tetap menggunakan LIVECHAT_SCOPES
        KESALAHAN_SHEETS_SERVICE = init_sheets_service(KESALAHAN_SPREADSHEET_ID, LIVECHAT_SCOPES)
    except Exception:
        KESALAHAN_SHEETS_SERVICE = None
        

def init_db_and_services():
    db.create_all()
    load_global_config()
    init_sheets_api_service()
    # Inisialisasi layanan Kesalahan yang baru di sini
    init_kesalahan_sheets_service()

with app.app_context():
    try:
        init_db_and_services()
    except Exception:
        pass

app.jinja_env.globals['current_year'] = datetime.now().year
app.jinja_env.filters['render_cell'] = render_cell
app.jinja_env.filters['format_number'] = format_number
app.jinja_env.globals['enumerate'] = enumerate