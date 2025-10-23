import os
import re
from urllib.parse import unquote

from flask import Flask, render_template, redirect, url_for
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# --- KONSTANTA ---
CLIENT_SECRET_FILE = 'client_secret.json'
TOKEN_FILE = 'token.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SPREADSHEET_ID = '1TkOeAMhwlmG1WftjAyJAlSBYzbR-JPum4sTIKliPtss'
RANGE_KESALAHAN_DEFAULT = 'A1:C'
RANGE_STAFF_DEFAULT = 'H1:AH'
SUMMARY_ROUTE = 'summary'

SHEETS_TO_HIDE = ['POIN-POIN KESALAHAN LC', 'LEADER', 'DIBANTU NOTE 1X', 'POIN-POIN KESALAHAN']
SHEET_KHUSUS = {
    'POIN-POIN KESALAHAN': 'A3:C',
}

# --- KONSTANTA BARU: Pemetaan Situs ke Leader ---
# Format: { 'NAMA_SITUS_UPPER': 'NAMA_LEADER_UPPER' }
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

app = Flask(__name__)
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

# --- FUNGSI GOOGLE SHEETS API ---

def init_sheets_service():
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return build('sheets', 'v4', credentials=creds)

def get_sheet_names(service):
    global SHEETS_TO_HIDE
    
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
    sheet_names = get_sheet_names(SHEETS_SERVICE)
    summary_data = [] # Ringkasan Situs
    grand_total = 0 # Total Situs
    
    # staff_summary_map akan menyimpan total KESELURUHAN staff untuk pengurutan
    staff_summary_map = {} 
    staff_list_details = []
    
    # NEW: Struktur untuk Ringkasan Leader
    leader_summary_map = {}
    
    sheets_to_process = [name for name in sheet_names if name not in SHEET_KHUSUS]
    
    ranges_to_get = []
    for sheet_name in sheets_to_process:
        # Mengambil range staff dari setiap sheet
        ranges_to_get.append(f"'{sheet_name}'!{RANGE_STAFF_DEFAULT}")
    
    # Panggilan Batch Get (Mengurangi hit API dari N menjadi 1)
    batch_results = get_batch_sheet_data(SHEETS_SERVICE, ranges_to_get)
    
    for i, sheet_name in enumerate(sheets_to_process):
        if i < len(batch_results):
            result_range = batch_results[i]
            staff_data = result_range.get('values', [])
            
            filtered_staff_data = [
                row for row in staff_data if any(cell and cell.strip() for cell in row)
            ]
            
            total_situs, staff_rows = calculate_sheet_total(filtered_staff_data)
            
            # --- 1. Memproses Ringkasan Situs ---
            if total_situs > 0:
                summary_data.append({
                    'name': sheet_name,
                    'total': total_situs,
                    'url': url_for('show_data', sheet_name=sheet_name) 
                })
                grand_total += total_situs
                
                # NEW: Agregasi Total ke Leader
                leader_name = LEADER_MAPPING.get(sheet_name.strip().upper())
                if leader_name:
                    # leader_summary_map menyimpan total kesalahan PER LEADER
                    leader_summary_map[leader_name] = leader_summary_map.get(leader_name, 0) + total_situs
                    
            # --- 2. Memproses Ringkasan Staff (Pengumpulan Detail) ---
            for row in staff_rows:
                # Kolom 0 adalah NAMA, Kolom 1 adalah TOTAL
                if len(row) > 1:
                    staff_name = row[0].strip().upper()
                    # Membersihkan string angka (misalnya "4,643" menjadi "4643")
                    num_str = re.sub(r'[^\d]', '', row[1].strip()) 
                    staff_total = int(num_str) if num_str.isdigit() else 0
                    
                    if staff_name and staff_total > 0:
                        # Menambahkan detail kesalahan per staff/situs
                        staff_list_details.append({
                            'name': staff_name,
                            'situs': sheet_name, # Nama situs
                            'total': staff_total
                        })
                        # Agregasi total keseluruhan untuk staff_summary_map
                        staff_summary_map[staff_name] = staff_summary_map.get(staff_name, 0) + staff_total
    
    # --- 3. Finalisasi Data Ringkasan Staff (Pengelompokan & Pengurutan) ---
    
    # Kumpulkan semua nama staff unik dan urutkan berdasarkan total keseluruhan (menurun)
    unique_staff_names = sorted(
        staff_summary_map.keys(),
        key=lambda name: (-staff_summary_map[name], name)
    )
    
    final_summary_staff_data = []
    current_staff_index = 0
    staff_grand_total = 0 

    # Peta sementara untuk mengelompokkan detail situs per staff
    grouped_details = {} 
    
    for item in staff_list_details:
        name = item['name']
        if name not in grouped_details:
            grouped_details[name] = []
        grouped_details[name].append({'situs': item['situs'], 'total': item['total']})
    
    # Membangun final_summary_staff_data dengan format yang diinginkan
    for name in unique_staff_names:
        current_staff_index += 1
        total_keseluruhan = staff_summary_map[name]
        
        # Urutkan situs berdasarkan total (opsional, tetapi rapi)
        details = sorted(grouped_details[name], key=lambda x: x['total'], reverse=True)
        
        # Menggabungkan nama situs dan total per situs
        list_situs_dan_total = []
        for detail in details:
             # PENTING: Gunakan format_number() sebagai fungsi Python di sini
             list_situs_dan_total.append(f"{detail['situs']} ({format_number(detail['total'])})") 

        situs_gabungan = " / ".join(list_situs_dan_total)
        
        final_summary_staff_data.append({
            'no': current_staff_index,
            'name': name,
            # Situs digabungkan dengan format: NAMA_SITUS_1 (TOTAL) / NAMA_SITUS_2 (TOTAL)
            'situs_details': situs_gabungan, 
            'grand_total_staff': total_keseluruhan
        })
        
        staff_grand_total += total_keseluruhan
    
    # Urutkan ringkasan situs
    summary_data.sort(key=lambda x: x['total'], reverse=True)
    
    # --- 4. Finalisasi Data Ringkasan Leader (Pengelompokan & Pengurutan) ---
    final_summary_leader_data = []
    leader_grand_total = 0
    
    # Kumpulkan detail situs per Leader
    leader_details_map = {}
    for item in summary_data:
        situs_name = item['name'].strip().upper()
        leader_name = LEADER_MAPPING.get(situs_name)
        if leader_name:
            if leader_name not in leader_details_map:
                leader_details_map[leader_name] = {'total': 0, 'sites': []}
            
            leader_details_map[leader_name]['total'] += item['total']
            # Simpan detail situs untuk digabungkan di kolom 'NAMA SITUS'
            leader_details_map[leader_name]['sites'].append({'name': item['name'], 'total': item['total']})

    # Mengurutkan Leader berdasarkan total kesalahan (menurun)
    sorted_leaders = sorted(
        leader_details_map.keys(), 
        key=lambda name: (-leader_details_map[name]['total'], name)
    )
    
    current_leader_index = 0
    for leader_name in sorted_leaders:
        current_leader_index += 1
        total = leader_details_map[leader_name]['total']
        
        # Urutkan situs di bawah leader berdasarkan total
        sites_details = sorted(leader_details_map[leader_name]['sites'], key=lambda x: x['total'], reverse=True)
        
        # Gabungkan nama situs dan total per situs menjadi satu string
        # INI BARIS YANG DIPERBAIKI!
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
                            sheet_names=sheet_names,
                            summary_data=summary_data, # Ringkasan Situs
                            grand_total=grand_total, # Total Situs
                            summary_staff_data=final_summary_staff_data, # Ringkasan Staff
                            staff_grand_total=staff_grand_total, # Total Staff KESELURUHAN
                            
                            # NEW: Ringkasan Leader
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

if __name__ == '__main__':
    if not os.path.exists(CLIENT_SECRET_FILE):
        print(f"ERROR: File kredensial '{CLIENT_SECRET_FILE}' tidak ditemukan.")
    else:
        try:
            SHEETS_SERVICE = init_sheets_service()
            app.run(debug=True)
        except Exception as e:
            print(f"\nFATAL ERROR saat inisialisasi: {e}")