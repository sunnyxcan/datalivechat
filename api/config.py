# api/config.py

import os
from dotenv import load_dotenv

load_dotenv()

SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', '1TkOeAMhwlmG1WftjAyJAlSBYzbR-JPum4sTIKliPtss')
SUMMARY_ROUTE = os.environ.get('SUMMARY_ROUTE', 'summary')
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

CLIENT_SECRET_FILE = 'client_secret.json'
TOKEN_FILE = 'token.json'

RANGE_KESALAHAN_DEFAULT = 'A1:C'
RANGE_STAFF_DEFAULT = 'H1:AH'

TARGET_KESALAHAN_HEADERS = ["Nama Staff", "Link Kesalahan", "Poin Kesalahan"]
KHUSUS_KESALAHAN_HEADERS = ["Kode", "Poin Kesalahan", "Ketentuan"] 

SHEETS_TO_HIDE = ['POIN-POIN KESALAHAN', 'LEADER', 'DIBANTU NOTE 1X', 'POIN-POIN KESALAHAN']

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://neondb_owner:npg_fBzYT73PxHdt@ep-bold-unit-a1d4rkmx-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require')

REDIS_URL = os.environ.get('REDIS_URL', 'redis://default:4u6RMXd2y5YdzWyshsa9QoFHWo3adhoy@redis-17316.c252.ap-southeast-1-1.ec2.redns.redis-cloud.com:17316')