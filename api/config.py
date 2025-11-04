# api/config.py

import os
from dotenv import load_dotenv

load_dotenv()

# --- LIVECHAT CONFIGURATION ---
SPREADSHEET_LIVECHAT = os.environ.get('SPREADSHEET_LIVECHAT', '1TkOeAMhwlmG1WftjAyJAlSBYzbR-JPum4sTIKliPtss')
RANGE_LIVECHAT_DEFAULT = os.environ.get('RANGE_LIVECHAT_DEFAULT', 'A1:C')
RANGE_STAFF_LIVECHAT = os.environ.get('RANGE_STAFF_LIVECHAT', 'H1:H')

SUMMARY_LIVECHAT_ROUTE = os.environ.get('SUMMARY_LIVECHAT_ROUTE', 'summary-livechat')
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

CLIENT_SECRET_FILE = 'client_secret.json'
TOKEN_FILE = 'token.json'

TARGET_KESALAHAN_HEADERS = ["Nama Staff", "Link Kesalahan", "Poin Kesalahan"]
KHUSUS_KESALAHAN_HEADERS = ["Kode", "Poin Kesalahan", "Ketentuan"] 

SHEETS_TO_HIDE = ['POIN-POIN KESALAHAN', 'LEADER', 'DIBANTU NOTE 1X', 'POIN-POIN KESALAHAN', 'TOTAL LC']

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://neondb_owner:npg_fBzYT73PxHdt@ep-bold-unit-a1d4rkmx-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require')

REDIS_URL = os.environ.get('REDIS_URL', 'redis://default:4u6RMXd2y5YdzWyshsa9QoFHWo3adhoy@redis-17316.c252.ap-southeast-1-1.ec2.redns.redis-cloud.com:17316')

# --- KESALAHAN CONFIGURATION BARU ---
SPREADSHEET_KESALAHAN = os.environ.get('SPREADSHEET_KESALAHAN', '1_WY_5vO5FJK0cfI2PjNwJ3GP5_ChELTT1GyJCiFYdE4')
RANGE_KESALAHAN_STAFF = os.environ.get('RANGE_KESALAHAN_STAFF', 'A2:BN')
RANGE_KESALAHAN_FATAL = os.environ.get('RANGE_KESALAHAN_FATAL', 'A1:M')