# api/routes_kesalahan.py

import re
import datetime # Import modul datetime
from urllib.parse import unquote
from flask import render_template, redirect, url_for, request
from collections import defaultdict

from .database import get_kesalahan_leader_mapping
from .app import (
    app, KESALAHAN_SHEETS_SERVICE, KESALAHAN_SPREADSHEET_ID,
    load_global_config
)
from .sheets_api import get_sheet_names, get_sheet_data
from .routes_main import get_all_sheet_names

KESALAHAN_RANGE_STAFF = 'Bukan A2:BP'
KESALAHAN_RANGE_FATAL = 'Bukan A:Z'

# =========================================================================
# FUNGSI PEMBANTU (HELPER)
# =========================================================================

def _get_global_kesalahan_ranges():
    with app.app_context():
        load_global_config()
        from .app import KESALAHAN_RANGE_STAFF as GLOBAL_RANGE_STAFF, KESALAHAN_RANGE_FATAL as GLOBAL_RANGE_FATAL
        return GLOBAL_RANGE_STAFF, GLOBAL_RANGE_FATAL

def _process_kesalahan_sheet(sheet_name, range_data_kesalahan, is_staff_sheet):
    if KESALAHAN_SHEETS_SERVICE is None:
        raise Exception("Google Sheets API Service untuk Kesalahan tidak tersedia.")

    sheet_name = unquote(sheet_name)
    
    raw_data = get_sheet_data(
        KESALAHAN_SHEETS_SERVICE,
        sheet_name,
        range_data_kesalahan,
        expected_columns=None,
        spreadsheet_id=KESALAHAN_SPREADSHEET_ID
    )

    if is_staff_sheet and len(raw_data) >= 2:
        header_row_1 = raw_data[0]
        header_row_2 = raw_data[1]
        kesalahan_headers = raw_data[0:2]
        data_rows = raw_data[2:]
    elif len(raw_data) >= 1:
        kesalahan_headers = raw_data[0]
        data_rows = raw_data[1:]
        header_row_1 = []
        header_row_2 = []
    else:
        kesalahan_headers = []
        data_rows = []
        header_row_1 = []
        header_row_2 = []

    kesalahan_data = data_rows
    rekap_per_staf = {}

    if is_staff_sheet and len(header_row_1) > 4 and len(header_row_2) > 4:
        START_COL_INDEX = 4

        date_mapping = {}
        current_date = ''
        for i in range(START_COL_INDEX, len(header_row_2)):
            if i < len(header_row_1) and header_row_1[i] and header_row_1[i].strip():
                current_date = header_row_1[i].strip()
            date_mapping[i] = current_date

        for row in kesalahan_data:
            if len(row) < START_COL_INDEX or not (row[1].strip() if len(row) > 1 and row[1] is not None else ''):
                continue
                
            passport = row[0].strip() if len(row) > 0 and row[0] is not None else ''
            staff_name = row[1].strip() if len(row) > 1 and row[1] is not None else ''
            status = row[2].strip() if len(row) > 2 and row[2] is not None else ''
            situs = row[3].strip() if len(row) > 3 and row[3] is not None else ''
            
            rekap_key = staff_name.upper()

            if not rekap_key or rekap_key in ['TOTAL']:
                continue

            if rekap_key not in rekap_per_staf:
                rekap_per_staf[rekap_key] = {
                    'passport': passport,
                    'nama': staff_name,
                    'status': status,
                    'situs': situs,
                    'total_kesalahan': 0.0,
                    'total_kesalahan_dp': 0.0,
                    'total_kesalahan_wd': 0.0,
                    'point_dp': 0.0,
                    'point_wd': 0.0,
                    'point_total': 0.0,
                    'details_per_date': []
                }

            for i in range(START_COL_INDEX, len(row)):
                if i < len(header_row_2):
                    jenis_kesalahan = header_row_2[i].strip().upper() if header_row_2[i] is not None else ''
                    tanggal = date_mapping.get(i, 'N/A')
                    
                    cell_value = row[i].strip() if i < len(row) and row[i] is not None else ''
                    
                    if re.match(r'^\d+(\.\d+)?$', cell_value) and float(cell_value) > 0:
                        jumlah_kesalahan = float(cell_value)
                        
                        rekap_per_staf[rekap_key]['total_kesalahan'] += jumlah_kesalahan
                        
                        point_dp_detail = 0.0
                        point_wd_detail = 0.0
                        
                        if jenis_kesalahan == 'DP':
                            rekap_per_staf[rekap_key]['total_kesalahan_dp'] += jumlah_kesalahan
                            point_dp_detail = jumlah_kesalahan * 0.25
                            
                        elif jenis_kesalahan == 'WD':
                            rekap_per_staf[rekap_key]['total_kesalahan_wd'] += jumlah_kesalahan
                            point_wd_detail = jumlah_kesalahan * 1.0
                            
                        rekap_per_staf[rekap_key]['details_per_date'].append({
                            'bulan': sheet_name,
                            'tanggal': tanggal,
                            'tipe': jenis_kesalahan,
                            'jumlah': jumlah_kesalahan,
                            'point_dp': round(point_dp_detail, 2),
                            'point_wd': round(point_wd_detail, 2)
                        })
    
    return kesalahan_headers, kesalahan_data, rekap_per_staf

def _finalize_rekap_data(rekap_per_staf):
    final_rekap_data = []
    
    for key in rekap_per_staf:
        total_dp = rekap_per_staf[key]['total_kesalahan_dp']
        total_wd = rekap_per_staf[key]['total_kesalahan_wd']
        
        point_dp_raw = total_dp * 0.25
        point_wd_raw = total_wd * 1.0
        
        point_total_raw = point_dp_raw + point_wd_raw
        
        rekap_per_staf[key]['point_dp'] = round(point_dp_raw, 2)
        rekap_per_staf[key]['point_wd'] = round(point_wd_raw, 2)
        rekap_per_staf[key]['point_total'] = round(point_total_raw, 2)
        
        total_kesalahan_float = rekap_per_staf[key]['total_kesalahan']
        rekap_per_staf[key]['total_kesalahan'] = int(round(total_kesalahan_float, 0))
        
        rekap_per_staf[key]['details_per_date'].sort(key=lambda x: (x.get('bulan', ''), x.get('tanggal', ''), x.get('tipe', '')), reverse=True)
    
    final_rekap_data = list(rekap_per_staf.values())
    final_rekap_data.sort(key=lambda x: x['total_kesalahan'], reverse=True)
    
    return final_rekap_data

def _recap_per_situs(final_rekap_data):
    rekap_situs = defaultdict(lambda: {
        'situs': '',
        'total_kesalahan': 0,
        'point_total': 0.0,
        'staff_terlibat': set()
    })

    for staf_data in final_rekap_data:
        situs_key = staf_data.get('situs', 'N/A').strip().upper()
        if not situs_key or situs_key in ['TOTAL']:
            situs_key = 'N/A'

        rekap_situs[situs_key]['situs'] = situs_key
        rekap_situs[situs_key]['total_kesalahan'] += staf_data['total_kesalahan']
        rekap_situs[situs_key]['point_total'] += staf_data['point_total']
        rekap_situs[situs_key]['staff_terlibat'].add(staf_data['passport'])

    final_rekap_situs = []
    for key, data in rekap_situs.items():
        data['staff_count'] = len(data['staff_terlibat'])
        del data['staff_terlibat']
        data['point_total'] = round(data['point_total'], 2)
        final_rekap_situs.append(data)
        
    final_rekap_situs.sort(key=lambda x: x['total_kesalahan'], reverse=True)
    
    return final_rekap_situs

# =========================================================================
# FUNGSI PEMBANTU BARU: REKAP PER LEADER
# =========================================================================

def _recap_per_leader(final_rekap_data, leader_mapping):
    leader_details_map = defaultdict(lambda: {
        'leader_name': '',
        'total_kesalahan': 0,
        'point_total': 0.0,
        'sites_recap': defaultdict(lambda: {'total_kesalahan': 0, 'point_total': 0.0})
    })
    
    all_leader_names = set(v.title() for v in leader_mapping.values())
    
    for name in all_leader_names:
        leader_details_map[name]['leader_name'] = name
    
    site_to_leader_map = {k.upper(): v.title() for k, v in leader_mapping.items()}

    for staf_data in final_rekap_data:
        situs_key = staf_data.get('situs', 'N/A').strip().upper()
        
        leader_name = site_to_leader_map.get(situs_key)
        
        if leader_name:
            leader_details_map[leader_name]['total_kesalahan'] += staf_data['total_kesalahan']
            leader_details_map[leader_name]['point_total'] += staf_data['point_total']
            
            leader_details_map[leader_name]['sites_recap'][situs_key]['total_kesalahan'] += staf_data['total_kesalahan']
            leader_details_map[leader_name]['sites_recap'][situs_key]['point_total'] += staf_data['point_total']

    for site, leader_raw in leader_mapping.items():
        leader_name = leader_raw.title()
        site_key = site.upper()
        
        # Memastikan semua situs Leader muncul, meskipun tidak ada data kesalahan
        leader_details_map[leader_name]['sites_recap'][site_key]
            
    final_rekap_leader = []
    for leader_name, data in leader_details_map.items():
        sites_details = []
        
        for site_key, site_data in data['sites_recap'].items():
            sites_details.append({
                'name': site_key.title(),
                'total_kesalahan': site_data['total_kesalahan'],
                'point_total': round(site_data['point_total'], 2)
            })
            
        sites_details.sort(key=lambda x: x['point_total'], reverse=True)
        
        site_list_str = [f"{site['name']} ({int(site['total_kesalahan'])})" for site in sites_details if site['total_kesalahan'] > 0]
        situs_gabungan = " / ".join(site_list_str)

        final_rekap_leader.append({
            'name': data['leader_name'],
            'total_kesalahan': data['total_kesalahan'],
            'point_total': round(data['point_total'], 2),
            'situs_details': situs_gabungan if situs_gabungan else '-'
        })
        
    final_rekap_leader.sort(key=lambda x: x['point_total'], reverse=True)
    
    return final_rekap_leader

# =========================================================================
# ROUTE KESALAHAN
# =========================================================================

@app.route('/kesalahan-summary')
def show_kesalahan_summary():
    KESALAHAN_RANGE_STAFF, KESALAHAN_RANGE_FATAL = _get_global_kesalahan_ranges()

    if KESALAHAN_SHEETS_SERVICE is None:
        config_url = url_for('show_db_config')
        message = f"Gagal terhubung ke Google Sheets API untuk Kesalahan. Silakan cek ID Spreadsheet dan kredensial. <a href='{config_url}' class='font-bold underline'>Atur Konfigurasi</a>."
        return render_template('error.html', message=message)
    
    sheet_names_livechat, kesalahan_sheet_names, sheet_khusus = get_all_sheet_names()
    
    leader_mapping = get_kesalahan_leader_mapping()
    
    # --- LOGIKA DEFAULT BULAN INI DIMULAI DI SINI ---
    
    # 1. Tentukan nama bulan saat ini (misalnya, 'NOV25')
    # Sesuaikan format ini jika sheet Anda menggunakan format tanggal yang berbeda!
    current_month_name = datetime.datetime.now().strftime('%b%y').upper()
    
    # Filter bulan-bulan yang relevan dari daftar sheet yang ada
    # Asumsi: Anda ingin memfilter bulan-bulan yang valid (misalnya, yang bukan sheet konfigurasi/fatal)
    available_months = [name for name in kesalahan_sheet_names if name not in ['FATAL!!!', 'KETENTUAN']]

    sheets_param_list = request.args.getlist('sheets')
    
    if sheets_param_list:
        # Jika pengguna SUDAH memilih bulan melalui URL/filter, gunakan pilihan mereka
        summary_sheet_names = [s.strip().upper() for s in sheets_param_list if s.strip().upper() in available_months]
    else:
        # Jika pengguna BELUM memilih (halaman dimuat pertama kali), SET DEFAULT
        if current_month_name in available_months:
            # Default ke bulan saat ini
            summary_sheet_names = [current_month_name]
        elif available_months:
            # Fallback: Jika bulan ini tidak tersedia, gunakan bulan terbaru (terakhir)
            summary_sheet_names = [available_months[-1]]
        else:
            # Fallback: Tidak ada bulan yang tersedia
            summary_sheet_names = []
            
    # Pastikan summary_sheet_names tidak kosong jika available_months tidak kosong
    if not summary_sheet_names and available_months:
        summary_sheet_names = [available_months[-1]]

    # --- LOGIKA DEFAULT BULAN INI SELESAI DI SINI ---

    current_sheets_title = ', '.join(summary_sheet_names)
    if set(summary_sheet_names) == set(available_months):
        current_sheets_title = 'Semua Bulan'
    elif not summary_sheet_names:
        current_sheets_title = 'Tidak Ada Bulan Dipilih'
    
    master_rekap_per_staf = defaultdict(lambda: {
        'passport': '', 'nama': '', 'status': '', 'situs': '',
        'total_kesalahan': 0.0, 'total_kesalahan_dp': 0.0,
        'total_kesalahan_wd': 0.0, 'point_dp': 0.0,
        'point_wd': 0.0, 'point_total': 0.0,
        'details_per_date': []
    })

    found_sheets = 0
    
    try:
        for sheet_name in summary_sheet_names:
            if sheet_name not in kesalahan_sheet_names:
                continue

            found_sheets += 1
            
            range_data_kesalahan = KESALAHAN_RANGE_STAFF or 'A2:BP'
            
            _, _, rekap_bulan_ini = _process_kesalahan_sheet(
                sheet_name,
                range_data_kesalahan,
                is_staff_sheet=True
            )

            for key, data in rekap_bulan_ini.items():
                # Pastikan data base staff tetap dari data sheet yang diproses
                if not master_rekap_per_staf[key]['passport']:
                    master_rekap_per_staf[key]['passport'] = data['passport']
                    master_rekap_per_staf[key]['nama'] = data['nama']
                    master_rekap_per_staf[key]['status'] = data['status']
                    master_rekap_per_staf[key]['situs'] = data['situs']
                
                master_rekap_per_staf[key]['total_kesalahan'] += data['total_kesalahan']
                master_rekap_per_staf[key]['total_kesalahan_dp'] += data['total_kesalahan_dp']
                master_rekap_per_staf[key]['total_kesalahan_wd'] += data['total_kesalahan_wd']
                
                master_rekap_per_staf[key]['details_per_date'].extend(data['details_per_date'])
        
        if found_sheets == 0:
            message = f"Tidak ada sheet bulanan yang ditemukan. Pastikan sheet bulanan ({', '.join(available_months)}) tersedia di Spreadsheet."
            return render_template('error.html', message=message)

        final_rekap_data = _finalize_rekap_data(master_rekap_per_staf)
        
        rekap_per_situs_data = _recap_per_situs(final_rekap_data)
        
        rekap_per_leader_data = _recap_per_leader(final_rekap_data, leader_mapping)
            
    except Exception as e:
        message = f"Gagal membuat ringkasan kesalahan: {e}"
        return render_template('error.html', message=message)

    return render_template('index.html',
                           kesalahan_headers=[],
                           kesalahan_data=[],
                           staff_headers=[],
                           staff_rows=[],
                           total_kesalahan_staff=0,
                           current_sheet='Ringkasan Kesalahan',
                           sheet_names=sheet_names_livechat,
                           kesalahan_sheet_names=kesalahan_sheet_names,
                           SHEET_KHUSUS={},
                           title_prefix=f'Ringkasan Kesalahan ({current_sheets_title})',
                           template_include='summary_kesalahan.html',
                           kesalahan_rekap_data=final_rekap_data,
                           rekap_per_situs_data=rekap_per_situs_data,
                           rekap_per_leader_data=rekap_per_leader_data,
                           summary_sheet_names=summary_sheet_names,
                           available_months=available_months
                           )

@app.route('/kesalahan-sheets')
def get_kesalahan_sheet_names_route():
    if KESALAHAN_SHEETS_SERVICE is None:
        config_url = url_for('show_db_config')
        message = f"Gagal terhubung ke Google Sheets API untuk Kesalahan. Silakan cek ID Spreadsheet dan kredensial. <a href='{config_url}' class='font-bold underline'>Atur Konfigurasi</a>."
        return render_template('error.html', message=message)

    try:
        sheet_names = get_sheet_names(KESALAHAN_SHEETS_SERVICE, {}, KESALAHAN_SPREADSHEET_ID)
        
        return render_template('debug_list.html',
                               current_sheet='Daftar Sheet Kesalahan',
                               items=sheet_names,
                               header="Nama-nama Sheet dari Spreadsheet Kesalahan")

    except Exception as e:
        message = f"Gagal mengambil nama sheet dari Spreadsheet Kesalahan: {e}"
        return render_template('error.html', message=message)


@app.route('/kesalahan/<sheet_name>')
def show_kesalahan_data(sheet_name):
    
    KESALAHAN_RANGE_STAFF, KESALAHAN_RANGE_FATAL = _get_global_kesalahan_ranges()

    if KESALAHAN_SHEETS_SERVICE is None:
        config_url = url_for('show_db_config')
        message = f"Gagal terhubung ke Google Sheets API untuk Spreadsheet Kesalahan. Silakan cek ID Spreadsheet dan kredensial. <a href='{config_url}' class='font-bold underline'>Atur Konfigurasi</a>."
        return render_template('error.html', message=message)

    sheet_name = unquote(sheet_name)

    sheet_names_livechat, kesalahan_sheet_names, sheet_khusus = get_all_sheet_names()
    
    final_rekap_data = []
    
    try:
        sheet_name_upper = sheet_name.upper()
        
        if sheet_name_upper == 'FATAL!!!' or sheet_name_upper == 'KETENTUAN':
            range_data_kesalahan = KESALAHAN_RANGE_FATAL or 'A:Z'
            template_include = 'detail_kesalahan_fatal.html'
            is_staff_sheet = False
            
            kesalahan_headers, kesalahan_data, _ = _process_kesalahan_sheet(
                sheet_name, range_data_kesalahan, is_staff_sheet)
        else:
            range_data_kesalahan = KESALAHAN_RANGE_STAFF or 'A2:BP'
            template_include = 'detail_kesalahan_staff.html'
            is_staff_sheet = True
            
            kesalahan_headers, kesalahan_data, rekap_per_staf = _process_kesalahan_sheet(
                sheet_name, range_data_kesalahan, is_staff_sheet)
            
            final_rekap_data = _finalize_rekap_data(rekap_per_staf)
            
            # --- LOGIKA FILTER BARU DIMULAI DI SINI ---
            
            # 1. Ambil filter dari request
            filter_situs = request.args.getlist('situs')
            
            # 2. Dapatkan daftar semua situs yang mungkin (untuk dropdown filter)
            all_situs = sorted(list(set(item.get('situs', '').upper().strip() for item in final_rekap_data if item.get('situs'))))
            
            # 3. Filter data berdasarkan situs
            if filter_situs:
                filter_situs_upper = [s.strip().upper() for s in filter_situs]
                final_rekap_data = [
                    item for item in final_rekap_data 
                    if item.get('situs', '').upper().strip() in filter_situs_upper
                ]

            # 4. Hitung total kesalahan setelah filter (hanya untuk tampilan ini)
            total_kesalahan_staff_sheet = sum(item['total_kesalahan'] for item in final_rekap_data)

            # --- LOGIKA FILTER BARU SELESAI DI SINI ---
                
    except Exception as e:
        message = f"Gagal mengambil data dari Sheet Kesalahan '{sheet_name}': {e}"
        final_rekap_data = []
        return render_template('error.html', message=message)

    return render_template('index.html',
                           kesalahan_headers=kesalahan_headers,
                           kesalahan_data=kesalahan_data,
                           staff_headers=[],
                           staff_rows=[],
                           total_kesalahan_staff=total_kesalahan_staff_sheet if 'total_kesalahan_staff_sheet' in locals() else 0, # Menggunakan total baru
                           current_sheet=sheet_name,
                           sheet_names=sheet_names_livechat,
                           kesalahan_sheet_names=kesalahan_sheet_names,
                           SHEET_KHUSUS={},
                           title_prefix='Data Kesalahan Mistake',
                           template_include=template_include,
                           kesalahan_rekap_data=final_rekap_data,
                           
                           # Data Baru untuk Filter
                           available_situs=all_situs if 'all_situs' in locals() else [],
                           selected_situs=filter_situs if 'filter_situs' in locals() else []
                           )