import os
import re
import json
from urllib.parse import unquote

from flask import Flask, render_template, redirect, url_for
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from dotenv import load_dotenv
load_dotenv() 

# --- KONSTANTA KONFIGURASI APLIKASI ---

# Ambil dari Environment Variable (ENV) jika ada, jika tidak, gunakan nilai default
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', '1TkOeAMhwlmG1WftjAyJAlSBYzbR-JPum4sTIKliPtss')
SUMMARY_ROUTE = os.environ.get('SUMMARY_ROUTE', 'summary')
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# File Kredensial Lokal (Hanya untuk pengembangan lokal)
CLIENT_SECRET_FILE = 'client_secret.json'
TOKEN_FILE = 'token.json'

# Range Default
RANGE_KESALAHAN_DEFAULT = 'A1:C'
RANGE_STAFF_DEFAULT = 'H1:AH'

SHEETS_TO_HIDE = ['POIN-POIN KESALAHAN', 'LEADER', 'DIBANTU NOTE 1X', 'POIN-POIN KESALAHAN']
SHEET_KHUSUS = {
    'POIN-POIN KESALAHAN LC': 'A3:C',
}

# --- KONSTANTA BARU: Pemetaan Situs ke Leader ---
LEADER_MAPPING = {
    'DEPOBOS': 'HENDY R',
    'GENGTOTO': 'DANIEL',
    'TOGELUP': 'WELLY',
    'LINE TOGEL': 'SAMUEL KRISTANTO',
    'TOGELON': 'MICHAEL WINARTA',
    'PARTAITOGEL': 'GUNADI',
    'PATIHTOTO': 'GUNADI',
    'JONITOGEL': 'KELVIN',
    'NANASTOTO': 'WENDY',
    'WDBOS': 'CALVIN',
    'DANATOTO': 'PRAYOGI',
    'LUNATOGEL': 'RIVALDY',
    'MARIATOGEL': 'VICKY',
    'FIATOGEL': 'VICKY',
    'INDRATOGEL': 'ALI',
    'YOWESTOGEL': 'ALI',
    'HOMETOGEL': 'MEGA',
    'YOKTOGEL': 'ZAINAL',
    'PWVIP4D': 'ZAINAL',
    'DINGDONTOGEL': 'ALEXANDER',
    'BOSJOKO': 'DAVID',
    'NAKBON': 'DAVID',
    'UDOY88': 'DAVID',
    'HOKIJITU': 'DAVID',
    'PROTOGEL': 'MICHAEL PRO',
    'LATOTO': 'DEDDY',
    'UDINTOGEL': 'MELISA',
    'SITUSTOTO': 'WIRA',
    'INDRABET': 'WIRA',
    'GOLTOGEL': 'OWEN',
    'ZIATOGEL': 'SAMUEL B',
    'TVTOTO': 'BUFON',
    'PULITOTO': 'ROBBY VIERA',
    'MONGGOWIN': 'ROBBY VIERA',
    'TOPWD': 'ROBBY VIERA',
    'ANGKABET': 'JEFERI',
    'LAPAK99': 'JEFERI',
    'TOPANBOS': 'JEFERI',
    'JUDOTOTO': 'JEFERI',
    'MANCINGDUIT': 'JOEL SIAGIAN',
    'FATCAI': 'JOEL SIAGIAN',
    'RUANGWD': 'JOEL SIAGIAN',
    'BANDAR80': 'JOEL SIAGIAN',
    'OPPATOTO': 'GLEENS NIGLEES SALIM',
    'WATITOTO': 'GARY GERALDI',
    'JUTAWANBET': 'MUHAMMAD RIO PRATAMA',
    'LIGABANDOT': 'MUHAMMAD RIO PRATAMA',
    'INDOJP': 'MUHAMMAD RIO PRATAMA'
}

app = Flask(__name__, static_folder='../static')
SHEETS_SERVICE = None

# --- FILTER JINJA2 ---

def render_cell(cell_content):
    if not isinstance(cell_content, str):
        return str(cell_content)

    text = cell_content.strip()
    if not text:
        return ''

    url_pattern = re.compile(r'(?:^|\s+)(\d+\.\s*)?(https?://\S+|prnt\.sc/\S+)', re.IGNORECASE)
    matches = list(url_pattern.finditer(text))

    if not matches:
        return f'<span class="cell-content">{text}</span>'

    output_html = []
    last_end = 0

    for match in matches:
        full_match_start = match.start(0)
        full_match_end = match.end(0)
        number_prefix = match.group(1)
        link_part = match.group(2)

        non_link_text = text[last_end:full_match_start]
        if non_link_text.strip():
            output_html.append(non_link_text.strip())
            output_html.append('<br>')

        display_text = link_part.strip()
        full_url = display_text

        if display_text.startswith('prnt.sc'):
            full_url = 'https://' + display_text

        link_html = f'<a href="{full_url}" target="_blank">{display_text}</a>'

        if number_prefix:
            display_num = number_prefix.strip()
            output_html.append(f'{display_num} ')

        output_html.append(link_html)
        output_html.append('<br>')

        last_end = full_match_end

    trailing_text = text[last_end:].strip()
    if trailing_text:
        output_html.append(trailing_text)

    final_output = "".join(output_html).rstrip('<br>')

    if not final_output and text:
        return f'<span class="cell-content">{text}</span>'

    return final_output

def format_number(value):
    """Memformat bilangan bulat dengan pemisah ribuan (misalnya 4643 menjadi 4,643)."""
    if isinstance(value, (int, float)):
        # Menggunakan ',' sebagai pemisah ribuan.
        return f"{value:,.0f}" if isinstance(value, float) else f"{value:,}"
    return str(value)

app.jinja_env.filters['render_cell'] = render_cell
app.jinja_env.filters['format_number'] = format_number
app.jinja_env.globals['enumerate'] = enumerate

# --- FUNGSI GOOGLE SHEETS API (MODIFIKASI UNTUK VERCEL & LOKAL) ---

def init_sheets_service():
    creds = None
    
    # 1. Cek Environment Variables (Untuk Vercel)
    token_json_str = os.environ.get('TOKEN_JSON')
    client_secret_json_str = os.environ.get('CLIENT_SECRET_JSON')

    if token_json_str and client_secret_json_str:
        try:
            # Menggunakan Credentials dari ENV
            token_info = json.loads(token_json_str)
            creds = Credentials.from_authorized_user_info(token_info, SCOPES)
            
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            
        except Exception as e:
            print(f"Gagal memuat/refresh token dari ENV: {e}")
            creds = None

    # 2. Cek File Lokal (Untuk Pengembangan Lokal)
    local_token_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', TOKEN_FILE)
    local_client_secret_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', CLIENT_SECRET_FILE)
    
    if not creds and os.path.exists(local_token_path):
        creds = Credentials.from_authorized_user_file(local_token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh token yang diambil dari file lokal
            try:
                creds.refresh(Request())
                with open(local_token_path, 'w') as token:
                    token.write(creds.to_json())
            except Exception as e:
                print(f"Gagal me-refresh token lokal: {e}")
                creds = None
        else:
            # Otentikasi baru (Hanya berfungsi di lokal)
            if os.path.exists(local_client_secret_path):
                print("Melakukan otentikasi baru...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    local_client_secret_path, SCOPES)
                creds = flow.run_local_server(port=0)

                with open(local_token_path, 'w') as token:
                    token.write(creds.to_json())
            else:
                print(f"ERROR: Kredensial lokal '{CLIENT_SECRET_FILE}' tidak ditemukan di root.")
                return None # Mengembalikan None jika gagal
    
    if not creds or not creds.valid:
        return None # Mengembalikan None jika kredensial tidak valid setelah semua upaya

    return build('sheets', 'v4', credentials=creds)

def get_sheet_names(service):
    global SHEETS_TO_HIDE
    
    if service is None:
        print("ERROR: Sheet Service belum diinisialisasi atau gagal dimuat.")
        return []
    
    hide_set_stripped = {name.strip() for name in SHEETS_TO_HIDE}
    hide_set_no_space = {name.replace(' ', '').strip() for name in SHEETS_TO_HIDE}
    hide_set_stripped.update({name.strip() for name in SHEET_KHUSUS.keys()})
    
    try:
        spreadsheet_metadata = service.spreadsheets().get(
            spreadsheetId=SPREADSHEET_ID
        ).execute()

        all_names = [sheet.get('properties', {}).get('title')
                     for sheet in spreadsheet_metadata.get('sheets', [])]

        filtered_names = []
        for name in all_names:
            if not name:
                continue
            
            if name.strip() not in hide_set_stripped and name.replace(' ', '').strip() not in hide_set_no_space:
                filtered_names.append(name)
        
        for name in SHEET_KHUSUS.keys():
            if name not in filtered_names:
                filtered_names.append(name)

        return filtered_names

    except Exception as e:
        print(f"Terjadi kesalahan saat mengambil nama sheet: {e}")
        return []

def get_sheet_data(service, sheet_name, range_name, expected_columns=None):
    full_range_name = f"'{sheet_name}'!{range_name}"

    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
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

    except Exception as e:
        print(f"Terjadi kesalahan saat mengakses Google Sheets API untuk data di '{sheet_name}' ({range_name}): {e}")
        return []

def get_batch_sheet_data(service, ranges):
    """Mengambil data dari beberapa range sheet dalam satu panggilan API."""
    if not ranges:
        return []
    
    try:
        result = service.spreadsheets().values().batchGet(
            spreadsheetId=SPREADSHEET_ID,
            ranges=ranges
        ).execute()
        
        return result.get('valueRanges', [])
        
    except Exception as e:
        print(f"Terjadi kesalahan saat mengakses Google Sheets API dengan batchGet: {e}")
        return []


def calculate_sheet_total(staff_data):
    """
    Menghitung total kesalahan staff dari data yang diberikan
    dan memisahkan baris total jika ada.
    
    Mengembalikan: (total_kesalahan_staff, cleaned_rows)
    """
    if not staff_data or len(staff_data) < 2:
        return 0, []

    staff_rows = staff_data[1:]
    total_kesalahan_staff = 0
    cleaned_rows = []

    if staff_rows and len(staff_rows[0]) > 1:
        # 1. Cek apakah baris terakhir adalah baris TOTAL
        last_row = staff_rows[-1]
        is_total_row = False
        try:
            if last_row and last_row[0] and last_row[0].strip().lower() == 'total':
                total_str = last_row[1].strip().replace(',', '') # Hapus pemisah ribuan
                num_match = re.search(r'\d+', total_str)
                if num_match:
                    total_kesalahan_staff = int(num_match.group(0))
                    is_total_row = True
                cleaned_rows = staff_rows[:-1] # Hapus baris total
            
            # 2. Jika tidak ada baris TOTAL, hitung manual
            if not is_total_row:
                for row in staff_rows:
                    if len(row) > 1:
                        # Membersihkan string angka (misalnya "4,643" menjadi "4643")
                        num_str = re.sub(r'[^\d]', '', row[1].strip())  
                        if num_str.isdigit():
                            total_kesalahan_staff += int(num_str)
                        cleaned_rows.append(row) # Simpan semua baris staff

        except Exception as e:
            print(f"Gagal menghitung total kesalahan staff: {e}")
            total_kesalahan_staff = 0
            cleaned_rows = staff_rows

    return total_kesalahan_staff, cleaned_rows

# --- ROUTE APLIKASI ---

@app.route('/')
def home():
    return redirect(url_for('show_summary')) 

@app.route(f'/{SUMMARY_ROUTE}')
def show_summary():
    sheet_names_from_api = get_sheet_names(SHEETS_SERVICE) 
    
    leader_mapped_sites_uppercase = set(LEADER_MAPPING.keys())

    sheets_to_process = [name for name in sheet_names_from_api if name not in SHEET_KHUSUS]
    
    all_unique_site_names = set(sheets_to_process)
    
    for site_name_upper in leader_mapped_sites_uppercase:
        all_unique_site_names.add(site_name_upper) 
        all_unique_site_names.add(site_name_upper.title()) 

    final_sheets_to_read = [name for name in all_unique_site_names 
                            if name not in SHEET_KHUSUS and name.upper() in leader_mapped_sites_uppercase]
    
    final_sheets_to_read = sorted(list(set(final_sheets_to_read)))
    
    all_sites_map = {}
    for site_upper in leader_mapped_sites_uppercase:
        all_sites_map[site_upper] = { 
            'total': 0,
            'url': url_for('show_data', sheet_name=site_upper)
        }
        
    grand_total = 0 
    staff_summary_map = {} 
    staff_list_details = []
    leader_summary_map = {}
    
    # 1. Kumpulkan semua nama Leader (hanya untuk pengecualian)
    leader_names = {name.strip().upper() for name in LEADER_MAPPING.values()} 
    all_staff_names_from_leaders = set(leader_names) # Inisialisasi staff potensial dengan Leader

    ranges_to_get = []
    for sheet_name in sheets_to_process:
        ranges_to_get.append(f"'{sheet_name}'!{RANGE_STAFF_DEFAULT}")
    
    batch_results = get_batch_sheet_data(SHEETS_SERVICE, ranges_to_get)
    
    for i, sheet_name in enumerate(sheets_to_process):
        
        site_key_upper = sheet_name.strip().upper() 
        
        if i < len(batch_results) and site_key_upper in all_sites_map:
            result_range = batch_results[i]
            staff_data = result_range.get('values', [])
            
            filtered_staff_data = [
                row for row in staff_data if any(cell and cell.strip() for cell in row)
            ]
            
            total_situs, staff_rows = calculate_sheet_total(filtered_staff_data)
            
            all_sites_map[site_key_upper]['total'] = total_situs 
            grand_total += total_situs
            
            leader_name = LEADER_MAPPING.get(site_key_upper)
            if leader_name:
                leader_summary_map[leader_name] = leader_summary_map.get(leader_name, 0) + total_situs
                    
            for row in staff_rows:
                if len(row) > 1:
                    staff_name = row[0].strip().upper()
                    # Pastikan nama staff valid sebelum diproses
                    if not staff_name or staff_name.lower() == 'total':
                        continue
                        
                    num_str = re.sub(r'[^\d]', '', row[1].strip()) 
                    staff_total = int(num_str) if num_str.isdigit() else 0
                    
                    # Tambahkan staff ke kumpulan staff potensial (Leader + Staff Non-Leader)
                    all_staff_names_from_leaders.add(staff_name) 
                    
                    if staff_name: 
                        staff_list_details.append({
                            'name': staff_name,
                            'situs': sheet_name, 
                            'total': staff_total
                        })
                        
                        # Inisialisasi atau perbarui total staff
                        staff_summary_map[staff_name] = staff_summary_map.get(staff_name, 0) + staff_total

    # 2. Inisialisasi staff 0 yang belum terdaftar (termasuk staff non-Leader dengan total 0)
    # Ini memastikan staff non-Leader yang totalnya 0 juga masuk.
    for staff_name in all_staff_names_from_leaders:
        if staff_name not in staff_summary_map:
             staff_summary_map[staff_name] = 0
    
    # 3. Filter Leader dari daftar staff yang akan diringkas
    # Menentukan staff non-Leader
    staff_names_only = {name for name in staff_summary_map.keys() if name not in leader_names}
    
    # Membuat Map Baru Hanya untuk Staff Non-Leader
    staff_summary_map_filtered = {
        name: staff_summary_map[name] for name in staff_names_only
    }
    
    # Mengurutkan Staff Non-Leader
    unique_staff_names = sorted(
        staff_summary_map_filtered.keys(), 
        key=lambda name: (-staff_summary_map_filtered[name], name)
    )

    summary_data = []
    for site_upper, details in all_sites_map.items():
        summary_data.append({
            'name': site_upper.title(), 
            'total': details['total'],
            'url': url_for('show_data', sheet_name=site_upper)
        })
        
    summary_data.sort(key=lambda x: x['total'], reverse=True)
    
    
    final_summary_staff_data = []
    current_staff_index = 0
    staff_grand_total = 0 

    grouped_details = {} 
    
    # Kumpulkan detail hanya untuk staff non-Leader
    for item in staff_list_details:
        name = item['name']
        if name in staff_names_only: 
            if name not in grouped_details:
                grouped_details[name] = []
            grouped_details[name].append({'situs': item['situs'], 'total': item['total']})
    
    for name in unique_staff_names:
        current_staff_index += 1
        total_keseluruhan = staff_summary_map_filtered[name] # Menggunakan map yang sudah difilter
        
        details = sorted(grouped_details.get(name, []), key=lambda x: x['total'], reverse=True)
        
        list_situs_dan_total = []
        for detail in details:
            list_situs_dan_total.append(f"{detail['situs']} ({format_number(detail['total'])})") 
        
        situs_gabungan = " / ".join(list_situs_dan_total)
        
        # Jika totalnya 0 dan tidak ada detail situs yang digabungkan, tampilkan pesan kustom
        if total_keseluruhan == 0 and not situs_gabungan:
             situs_gabungan = "TIDAK ADA KESALAHAN (0)"


        final_summary_staff_data.append({
            'no': current_staff_index,
            'name': name,
            'situs_details': situs_gabungan, 
            'grand_total_staff': total_keseluruhan
        })
        
        staff_grand_total += total_keseluruhan
        
    # Leader Summary tetap dihitung berdasarkan Leader
    final_summary_leader_data = []
    leader_grand_total = 0
    leader_details_map = {}
    
    for original_situs_name_upper, details in all_sites_map.items(): 
        
        leader_name = LEADER_MAPPING.get(original_situs_name_upper)

        if leader_name:
            if leader_name not in leader_details_map:
                leader_details_map[leader_name] = {'total': 0, 'sites': []}
            
            leader_details_map[leader_name]['total'] += details['total']
            
            leader_details_map[leader_name]['sites'].append({
                'name': original_situs_name_upper.title(), 
                'total': details['total']
            })

    sorted_leaders = sorted(
        leader_details_map.keys(), 
        key=lambda name: (-leader_details_map[name]['total'], name)
    )
    
    current_leader_index = 0
    for leader_name in sorted_leaders:
        current_leader_index += 1
        total = leader_details_map[leader_name]['total']
        
        sites_details = sorted(leader_details_map[leader_name]['sites'], key=lambda x: x['total'], reverse=True)
        
        site_list_str = [f"{site['name']} ({format_number(site['total'])})" for site in sites_details]
        
        situs_gabungan = " / ".join(site_list_str)

        final_summary_leader_data.append({
            'no': current_leader_index,
            'name': leader_name,
            'situs_details': situs_gabungan,
            'total': total
        })
        
        leader_grand_total += total
        
    return render_template('index.html',
                            current_sheet='Summary',
                            sheet_names=sheet_names_from_api,
                            summary_data=summary_data, 
                            grand_total=grand_total, 
                            summary_staff_data=final_summary_staff_data, 
                            staff_grand_total=staff_grand_total, 
                            summary_leader_data=final_summary_leader_data,
                            leader_grand_total=leader_grand_total 
                            )

@app.route('/<sheet_name>')
def show_data(sheet_name):
    sheet_name = unquote(sheet_name)

    sheet_names = get_sheet_names(SHEETS_SERVICE)

    kesalahan_data = []
    kesalahan_headers = []
    staff_headers = []
    staff_rows = []
    total_kesalahan_staff = 0 

    # 1. Penanganan Sheet Khusus
    if sheet_name in SHEET_KHUSUS:
        range_kesalahan = SHEET_KHUSUS[sheet_name]

        kesalahan_data = get_sheet_data(
            SHEETS_SERVICE,
            sheet_name,
            range_kesalahan,
            expected_columns=3
        )

        kesalahan_headers = ["Kode", "Poin Kesalahan", "Ketentuan"] 

    # 2. Penanganan Sheet Normal
    else:
        TARGET_KESALAHAN_HEADERS = ["Nama Staff", "Link Kesalahan", "Poin Kesalahan"]

        # Mengambil data Kesalahan dan Staff dalam 1 panggilan batch
        ranges_for_sheet = [
            f"'{sheet_name}'!{RANGE_KESALAHAN_DEFAULT}",
            f"'{sheet_name}'!{RANGE_STAFF_DEFAULT}"
        ]
        
        batch_results = get_batch_sheet_data(SHEETS_SERVICE, ranges_for_sheet)
        
        kesalahan_data_with_header = batch_results[0].get('values', []) if len(batch_results) > 0 else []
        staff_data = batch_results[1].get('values', []) if len(batch_results) > 1 else []
        
        # Pembersihan data kesalahan
        filtered_kesalahan_data = [
            row for row in kesalahan_data_with_header if any(cell and cell.strip() for cell in row)
        ]

        if filtered_kesalahan_data:
            kesalahan_headers = TARGET_KESALAHAN_HEADERS
            kesalahan_data = [
                (row + [''] * (3 - len(row)))[:3] for row in filtered_kesalahan_data[1:]
            ]
        else:
            kesalahan_headers = TARGET_KESALAHAN_HEADERS
            kesalahan_data = []

        # Pembersihan data staff
        filtered_staff_data = [
            row for row in staff_data if any(cell and cell.strip() for cell in row)
        ]
        
        staff_headers = filtered_staff_data[0] if filtered_staff_data else []
        
        total_kesalahan_staff, staff_rows = calculate_sheet_total(filtered_staff_data)

    return render_template('index.html',
                           kesalahan_headers=kesalahan_headers,
                           kesalahan_data=kesalahan_data,
                           staff_headers=staff_headers,
                           staff_rows=staff_rows,
                           current_sheet=sheet_name,
                           sheet_names=sheet_names,
                           total_kesalahan_staff=total_kesalahan_staff,
                           SHEET_KHUSUS=SHEET_KHUSUS)

# --- INISIALISASI APLIKASI ---

try:
    SHEETS_SERVICE = init_sheets_service()
except Exception as e:
    print(f"\nFATAL ERROR saat inisialisasi di global scope: {e}")
    SHEETS_SERVICE = None

if __name__ == '__main__':
    if SHEETS_SERVICE is not None:
        try:
            print("Google Sheets Service berhasil diinisialisasi. Menjalankan Flask...")
            app.run(debug=True)
        except Exception as e:
            print(f"\nFATAL ERROR saat menjalankan Flask: {e}")
    else:
        print("\nGagal menginisialisasi Google Sheets Service. Cek file kredensial atau Environment Variables.")