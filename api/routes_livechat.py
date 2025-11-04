# api/routes_livechat.py

import re
from urllib.parse import unquote
from flask import render_template, redirect, url_for, abort
import math
from datetime import datetime, timedelta

from .app import (
    app, SHEETS_SERVICE, 
    LIVECHAT_SPREADSHEET_ID, LIVECHAT_RANGE_KESALAHAN, LIVECHAT_RANGE_STAFF,
)
from .config import SUMMARY_LIVECHAT_ROUTE, TARGET_KESALAHAN_HEADERS, KHUSUS_KESALAHAN_HEADERS
from .database import get_livechat_leader_mapping 
from .sheets_api import (
    get_sheet_data, get_batch_sheet_data, calculate_sheet_total
)
from .filters import format_number
from .routes_main import get_all_sheet_names 

# =========================================================================
# FUNGSI UNTUK PERHITUNGAN KESALAHAN STAFF DARI DATA KESALAHAN
# (Tidak ada perubahan, hanya untuk kelengkapan)
# =========================================================================

def calculate_staff_errors_from_kesalahan(kesalahan_data_all, staff_list):
    
    KESALAHAN_TYPES = [
        "Tidak membantu / menyelesaikan kendala dengan benar", 
        "Note Pengecekkan tidak berujung", 
        "Tidak melakukan pengecekan", 
        "Memberikan data penting ke member", 
        "Reset pass tanpa persetujuan",
        "Tidak memahami permainan", 
        "Tidak respon permainan",
        "Ubah data tanpa data lengkap",
        "Salah indikator bank", 
        "Mempermainkan member", 
        "Telat minta maaf", 
        "Salah informasi", 
        "Salah respon", 
        "Tidak respon", 
        "Telat respon", 
        "Tidak teliti", 
        "Asal spam pk", 
        "Tidak minta userid", 
        "Fatal", 
        "Capslock", 
        "Tidak sopan", 
        "Tidak meminta data pendukung", 
        "SS admin", 
        "Note", 
    ]
    
    NEW_STAFF_HEADERS_ORDER = [
        "Salah respon", "Salah informasi", "Telat minta maaf", "Tidak respon", "Telat respon", 
        "Tidak membantu / menyelesaikan kendala dengan benar", "Tidak melakukan pengecekan", 
        "Tidak teliti", "Asal spam pk", "Tidak minta userid", "Fatal", "Tidak memahami permainan", 
        "Tidak respon permainan", "Memberikan data penting ke member", "Salah indikator bank", 
        "Mempermainkan member", "Capslock", "Tidak sopan", "Ubah data tanpa data lengkap", 
        "Reset pass tanpa persetujuan", "Tidak meminta data pendukung", "SS admin", "Note"
    ]
    NEW_STAFF_HEADERS_ORDER.append("PENGECEKKAN TIDAK BERUJUNG")

    def normalize_name(name_raw):
        if not name_raw:
            return ""
        name_str = str(name_raw)
        name_clean = name_str.encode('ascii', 'ignore').decode('ascii').upper()
        name_normalized = re.sub(r'[^A-Z0-9/]', '', name_clean) 
        return name_normalized
        
    def clean_for_display(name_raw):
        return re.sub(r'\s+', ' ', str(name_raw)).strip().title()
    
    staff_full_names = {}
    staff_key_to_display_name = {} 
    staff_summary = {}
    
    for row in staff_list:
        if row and row[0].strip():
            full_name_raw = row[0].strip()
            
            # --- GUARDRAIL TAMBAHAN: Skip baris yang bernama 'TOTAL' ---
            if full_name_raw.upper() == 'TOTAL':
                continue
            # ---------------------------------------------------------

            display_name_key_upper = normalize_name(full_name_raw) 
            display_name_clean_title = clean_for_display(full_name_raw)

            if display_name_key_upper not in staff_summary:
                staff_summary[display_name_key_upper] = {
                    'NAMA LENGKAP': display_name_clean_title,
                    'TOTAL KESALAHAN': 0,
                    'Detail Kesalahan': {k: 0 for k in NEW_STAFF_HEADERS_ORDER}
                }
            
            staff_full_names[display_name_key_upper] = full_name_raw
            staff_key_to_display_name[display_name_key_upper] = display_name_key_upper

            name_parts = re.split(r'\s*/\s*|\s+/\s*', full_name_raw)
            
            for part in name_parts:
                part_stripped = part.strip()
                if part_stripped:
                    clean_name_key = normalize_name(part_stripped)
                    
                    staff_full_names[clean_name_key] = part_stripped
                    staff_key_to_display_name[clean_name_key] = display_name_key_upper
    
    note_pengecekan_map = {} 
    
    for row in kesalahan_data_all:
        if len(row) < 3: 
            continue
        
        staff_name_from_error = row[0].strip()
        clean_staff_name_error = normalize_name(staff_name_from_error)
        
        error_type_from_error = row[2].strip()
        clean_error_type = re.sub(r'\s+', ' ', error_type_from_error).strip().upper()

        matching_staff_name_key = None
        
        if clean_staff_name_error in staff_full_names:
            matching_staff_name_key = clean_staff_name_error
            
        if not matching_staff_name_key:
            continue
            
        display_name_key = staff_key_to_display_name.get(matching_staff_name_key)
        
        if not display_name_key:
            continue
            
        error_type_base = None
        for et in KESALAHAN_TYPES:
            if clean_error_type.startswith(et.upper()):
                error_type_base = et
                break
            
        if not error_type_base:
            continue

        if error_type_base == "Note Pengecekkan tidak berujung":
            note_pengecekan_map[display_name_key] = note_pengecekan_map.get(display_name_key, 0) + 1
            staff_summary[display_name_key]['Detail Kesalahan']['Note'] += 1
            
        elif error_type_base == "Note":
            staff_summary[display_name_key]['Detail Kesalahan']['Note'] += 1
            
        elif error_type_base in NEW_STAFF_HEADERS_ORDER:
            staff_summary[display_name_key]['Detail Kesalahan'][error_type_base] += 1
            staff_summary[display_name_key]['TOTAL KESALAHAN'] += 1
        
    for staff_name_key, count in note_pengecekan_map.items():
        if staff_name_key in staff_summary:
            jumlah_pengecekan_berujung = math.floor(count / 10)
            
            staff_summary[staff_name_key]['Detail Kesalahan']['PENGECEKKAN TIDAK BERUJUNG'] = jumlah_pengecekan_berujung
            
            staff_summary[staff_name_key]['Detail Kesalahan']['Note'] -= count 
            staff_summary[staff_name_key]['TOTAL KESALAHAN'] += jumlah_pengecekan_berujung 

    new_staff_rows = []
    final_headers = ["NAMA STAFF", "TOTAL KESALAHAN"] + NEW_STAFF_HEADERS_ORDER
    total_kesalahan_staff_new = 0
    
    sorted_staff_keys = sorted(
        staff_summary.keys(), 
        key=lambda k: staff_summary[k]['TOTAL KESALAHAN'], 
        reverse=True
    )

    for name_key in sorted_staff_keys:
        data = staff_summary[name_key]
            
        row = [data['NAMA LENGKAP']] 
        row.append(format_number(data['TOTAL KESALAHAN'])) 
        total_kesalahan_staff_new += data['TOTAL KESALAHAN']
        
        for error_type in NEW_STAFF_HEADERS_ORDER:
            val = max(0, data['Detail Kesalahan'].get(error_type, 0))
            row.append(format_number(val))
            
        new_staff_rows.append(row)
    
    return final_headers, new_staff_rows, total_kesalahan_staff_new


# =========================================================================
# FUNGSI PEMBANTU UNTUK FILTER BULAN BERBASIS DELIMITER
# (Tidak ada perubahan, hanya untuk kelengkapan)
# =========================================================================

def is_date_string(date_str, format_list=['%d/%m/%Y', '%d/%m/%y']): 
    if not date_str:
        return None
    date_str = date_str.strip().encode('ascii', 'ignore').decode('ascii') 
    
    for fmt in format_list:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

def get_delimiter_indexes(kesalahan_data):
    delimiter_map = {}
    
    for i, row in enumerate(kesalahan_data): 
        if len(row) < 3: 
            if len(row) > 1 and row[1]: 
                date_obj = is_date_string(row[1])
                if date_obj:
                    month_key = date_obj.strftime('%m-%Y')
                    if month_key not in delimiter_map:
                         delimiter_map[month_key] = i
                         
            continue 
            
        is_delimiter_row = (not row[0] or not row[0].strip()) and (not row[2] or not row[2].strip())
        
        if is_delimiter_row:
            date_obj = is_date_string(row[1])
            if date_obj:
                month_key = date_obj.strftime('%m-%Y')
                if month_key not in delimiter_map:
                    delimiter_map[month_key] = i
                             
    return delimiter_map

def filter_kesalahan_by_month(kesalahan_data, month_filter):
    # LOGIKA INI SUDAH BENAR: Jika 'all' atau None, kembalikan semua data.
    if not month_filter or month_filter.lower() == 'all':
        return kesalahan_data
        
    delimiter_map = get_delimiter_indexes(kesalahan_data)
    
    sorted_months = sorted(
        delimiter_map.keys(), 
        key=lambda x: datetime.strptime(x, '%m-%Y'), 
        reverse=True
    )
    
    if not sorted_months and month_filter not in delimiter_map:
        return []
        
    end_index = len(kesalahan_data)
    
    try:
        current_index_in_sorted = sorted_months.index(month_filter)
        
        if current_index_in_sorted > 0:
            next_month_key = sorted_months[current_index_in_sorted - 1] 
            end_index = delimiter_map[next_month_key] 
            
    except ValueError:
        pass 
        
    start_index = 0
    
    try:
        if month_filter in delimiter_map:
            start_index = delimiter_map[month_filter] 
        else:
            if sorted_months:
                latest_month_str = sorted_months[0]
                start_index = delimiter_map[latest_month_str] + 1
            
    except Exception: 
        pass
        
    if start_index >= end_index:
        return []
    
    return kesalahan_data[start_index:end_index]

def get_available_months(kesalahan_data):
    delimiter_map = get_delimiter_indexes(kesalahan_data)
    months = list(delimiter_map.keys()) 
    
    now = datetime.now()
    current_month_str = now.strftime('%m-%Y')

    if months:
        latest_month_str = max(months, key=lambda x: datetime.strptime(x, '%m-%Y'))
        latest_delimiter_index = delimiter_map[latest_month_str]
        latest_month_obj = datetime.strptime(latest_month_str, '%m-%Y')
        
        has_new_error_data = False
        
        for i in range(latest_delimiter_index + 1, len(kesalahan_data)):
            row = kesalahan_data[i]
            
            if (len(row) >= 3 and 
                row[0] and row[0].strip() and           
                row[2] and row[2].strip() and           
                not is_date_string(row[1])
               ):
                has_new_error_data = True
                break
        
        if has_new_error_data:
            
            next_month = (latest_month_obj.replace(day=28) + timedelta(days=4)).replace(day=1)
            next_month_str = next_month.strftime('%m-%Y')
            
            if next_month_str == current_month_str:
                 if next_month_str not in months:
                     months.append(next_month_str)
        
    elif kesalahan_data:
        if len(kesalahan_data) > 0 and kesalahan_data[0][0] and kesalahan_data[0][0].strip():
             months.append(current_month_str)

    try:
        sorted_months = sorted(
            months, 
            key=lambda x: datetime.strptime(x, '%m-%Y'), 
            reverse=True
        )
    except ValueError:
        sorted_months = sorted(months, reverse=True)
            
    return sorted_months


# =========================================================================
# ROUTE LIVECHAT (show_summary_livechat) - MODIFIED
# =========================================================================

@app.route(f'/{SUMMARY_LIVECHAT_ROUTE}')
@app.route(f'/{SUMMARY_LIVECHAT_ROUTE}/<month_filter>') 
def show_summary_livechat(month_filter=None): 
    if SHEETS_SERVICE is None:
        return redirect(url_for('home'))

    sheet_names_livechat, kesalahan_sheet_names, sheet_khusus = get_all_sheet_names()
    leader_mapping = get_livechat_leader_mapping()
    
    sheets_to_process = [name for name in sheet_names_livechat if name not in sheet_khusus]
    leader_mapped_sites_uppercase = {k.upper(): v for k, v in leader_mapping.items()}
    sites_for_batch_read = list({name.upper() for name in sheets_to_process if name.upper() in leader_mapped_sites_uppercase})

    # Siapkan ranges, combined_ranges, num_sites
    ranges_to_get_kesalahan = [f"'{sheet_name}'!{LIVECHAT_RANGE_KESALAHAN}" for sheet_name in sites_for_batch_read]
    ranges_to_get_staff = [f"'{sheet_name}'!{LIVECHAT_RANGE_STAFF}" for sheet_name in sites_for_batch_read]
    combined_ranges = ranges_to_get_kesalahan + ranges_to_get_staff
    num_sites = len(sites_for_batch_read)
    
    batch_results = get_batch_sheet_data(SHEETS_SERVICE, combined_ranges, LIVECHAT_SPREADSHEET_ID)

    site_errors_map = {} 
    staff_total_map_per_site = {} 
    available_months_set = set()
    
    # 1. Kumpulkan semua bulan yang tersedia
    for i, sheet_name_upper in enumerate(sites_for_batch_read):
        raw_error_data_range = batch_results[i]
        filtered_kesalahan_data_raw = raw_error_data_range.get('values', [])
        
        if filtered_kesalahan_data_raw and len(filtered_kesalahan_data_raw) > 0:
            kesalahan_data_raw_no_header = filtered_kesalahan_data_raw[1:]
            
            current_months = get_available_months(kesalahan_data_raw_no_header)
            available_months_set.update(current_months)

    # Sortir bulan yang tersedia
    try:
        final_available_months = sorted(
            list(available_months_set), 
            key=lambda x: datetime.strptime(x, '%m-%Y'), 
            reverse=True
        )
    except ValueError:
        final_available_months = sorted(list(available_months_set), reverse=True)

    # Tambahkan opsi 'all' ke daftar bulan yang tersedia (untuk ditampilkan di dropdown)
    if 'all' not in final_available_months:
        final_available_months.insert(0, 'all')
        
    latest_month = final_available_months[1] if len(final_available_months) > 1 else 'all'

    # =======================================================
    # LOGIKA FINAL UNTUK PENENTUAN FILTER SUMMARY
    # =======================================================
    
    # A. Tentukan filter yang akan digunakan untuk perhitungan data (actual_month_filter_for_calc)
    if not month_filter: # URL default: /livechat_summary
        # Default: Paksa ke bulan terbaru untuk beban default yang ringan
        actual_month_filter_for_calc = latest_month
        current_month_filter_display = latest_month # Bulan terbaru terpilih di dropdown
    elif month_filter.lower() == 'all': # URL: /livechat_summary/all
        # Sesuai permintaan: MEMUAT SEMUA DATA
        actual_month_filter_for_calc = 'all'
        current_month_filter_display = 'all' # Opsi 'all' terpilih
    else: # URL: /livechat_summary/08-2025
        actual_month_filter_for_calc = month_filter
        current_month_filter_display = month_filter
        
    # Memastikan current_month_filter_display adalah salah satu yang valid
    if current_month_filter_display not in final_available_months:
        current_month_filter_display = latest_month # Fallback ke bulan terbaru

    # 3. Iterasi Ulang dan Hitung Total Menggunakan Filter yang Tepat
    for i, sheet_name_upper in enumerate(sites_for_batch_read):
        
        raw_error_data_range = batch_results[i]
        filtered_kesalahan_data_raw = raw_error_data_range.get('values', [])
        
        if filtered_kesalahan_data_raw and len(filtered_kesalahan_data_raw) > 0:
            kesalahan_data_raw_no_header = filtered_kesalahan_data_raw[1:]
            
            # Filter data berdasarkan actual_month_filter_for_calc
            kesalahan_data_filtered_by_month = filter_kesalahan_by_month(kesalahan_data_raw_no_header, actual_month_filter_for_calc)
            
            raw_staff_data_range = batch_results[i + num_sites]
            staff_data_raw = raw_staff_data_range.get('values', [])
            staff_list_for_calc = []
            if staff_data_raw and len(staff_data_raw) > 1:
                staff_list_for_calc = [row for row in staff_data_raw[1:] if row and row[0].strip()]

            if staff_list_for_calc:
                _, staff_rows_calculated, total_kesalahan_situs = calculate_staff_errors_from_kesalahan(
                    kesalahan_data_filtered_by_month, staff_list_for_calc 
                )
                
                site_errors_map[sheet_name_upper] = total_kesalahan_situs
                
                staff_total_map_per_site[sheet_name_upper] = {}
                for row in staff_rows_calculated:
                    staff_name = row[0].strip().upper()
                    total_str = row[1].replace('.', '') 
                    staff_total_map_per_site[sheet_name_upper][staff_name] = int(total_str) if total_str.isdigit() else 0
                
            else:
                site_errors_map[sheet_name_upper] = 0
        else:
            site_errors_map[sheet_name_upper] = 0

    # 4. Agregasi Hasil Perhitungan (Situs, Staf, Leader)
    
    # Filter bulan untuk link detail situs: 
    # Jika ringkasan menampilkan 'all', link detail situs harus default ke bulan terbaru untuk menghindari beban berlebih.
    month_filter_for_detail_link = actual_month_filter_for_calc
    if month_filter_for_detail_link == 'all':
        month_filter_for_detail_link = latest_month
    
    grand_total = sum(site_errors_map.values())
    all_sites_map = {}
    
    for site_upper, total in site_errors_map.items():
        all_sites_map[site_upper] = {
            'total': total,
            # Link detail situs menggunakan bulan terbaru jika ringkasan saat ini adalah 'all'
            'url': url_for('show_data', sheet_name=site_upper, month_filter=month_filter_for_detail_link) 
        }

    summary_data = [] 
    for site_upper, details in all_sites_map.items():
        summary_data.append({
            'name': site_upper.title(),
            'total': details['total'],
            'url': details['url']
        })
        
    summary_data.sort(key=lambda x: x['total'], reverse=True) 

    # Agregasi Staf
    staff_summary_map_total = {}
    staff_list_details = []
    
    for site_upper, staff_data in staff_total_map_per_site.items():
        for staff_name, total in staff_data.items():
            staff_summary_map_total[staff_name] = staff_summary_map_total.get(staff_name, 0) + total
            if total > 0: 
                 staff_list_details.append({
                     'name': staff_name,
                     'situs': site_upper,
                     'total': total
                   })
                   
    all_staff_names_from_leaders = {name.strip().upper() for name in leader_mapping.values()}
    all_staff_names_from_leaders.update(staff_summary_map_total.keys())
    
    staff_names_only = {name for name in all_staff_names_from_leaders if name.title() not in leader_mapping.values()}
    staff_summary_map_filtered = {
        name: staff_summary_map_total.get(name, 0) for name in staff_names_only
    }
    
    unique_staff_names = sorted(
        staff_summary_map_filtered.keys(),
        key=lambda name: (-staff_summary_map_filtered[name], name)
    )

    final_summary_staff_data = [] 
    staff_grand_total = 0
    grouped_details = {}
    
    for item in staff_list_details:
        name = item['name']
        if name in staff_names_only:
            if name not in grouped_details:
                grouped_details[name] = []
            grouped_details[name].append({'situs': item['situs'].title(), 'total': item['total']})
    
    for current_staff_index, name in enumerate(unique_staff_names, 1):
        total_keseluruhan = staff_summary_map_filtered[name]
        details = sorted(grouped_details.get(name, []), key=lambda x: x['total'], reverse=True)
        
        list_situs_dan_total = [f"{detail['situs']} ({format_number(detail['total'])})" for detail in details]
        situs_gabungan = " / ".join(list_situs_dan_total)
        
        if total_keseluruhan == 0 and not situs_gabungan:
            situs_gabungan = "TIDAK ADA KESALAHAN (0)"

        final_summary_staff_data.append({
            'no': current_staff_index,
            'name': name.title(),
            'situs_details': situs_gabungan,
            'grand_total_staff': total_keseluruhan
        })
        staff_grand_total += total_keseluruhan
    
    # Perhitungan Leader Summary 
    final_summary_leader_data = [] 
    leader_grand_total = 0
    leader_details_map = {leader: {'total': 0, 'sites': []} for leader in leader_mapping.values()}
    
    for original_situs_name_upper, total_error_site in site_errors_map.items():
        leader_name = leader_mapping.get(original_situs_name_upper)

        if leader_name:
            leader_details_map[leader_name]['total'] += total_error_site
            
            leader_details_map[leader_name]['sites'].append({
                'name': original_situs_name_upper.title(),
                'total': total_error_site
            })

    sorted_leaders = sorted(
        leader_details_map.keys(),
        key=lambda name: (-leader_details_map[name]['total'], name)
    )
    
    for current_leader_index, leader_name in enumerate(sorted_leaders, 1):
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
        
    # Tambahkan available_months dan current_month_filter ke render_template
    return render_template('index.html',
                            current_sheet='Ringkasan Livechat', 
                            sheet_names=sheet_names_livechat, 
                            kesalahan_sheet_names=kesalahan_sheet_names, 
                            summary_data=summary_data, 
                            grand_total=grand_total,
                            summary_staff_data=final_summary_staff_data, 
                            staff_grand_total=staff_grand_total,
                            summary_leader_data=final_summary_leader_data, 
                            leader_grand_total=leader_grand_total,
                            title_prefix='Data Kesalahan Livechat',
                            available_months=final_available_months, 
                            # Menggunakan 'current_month_filter_display'
                            current_month_filter=current_month_filter_display 
                            )


# =========================================================================
# ROUTE LIVECHAT (show_data) - MODIFIED
# =========================================================================

@app.route('/<sheet_name>')
@app.route('/<sheet_name>/<month_filter>') 
def show_data(sheet_name, month_filter=None): 
    if SHEETS_SERVICE is None:
        return redirect(url_for('home'))

    sheet_name = unquote(sheet_name)
    
    sheet_names_livechat, kesalahan_sheet_names, sheet_khusus = get_all_sheet_names()
    sheet_names = sheet_names_livechat 
    
    range_kesalahan_default = LIVECHAT_RANGE_KESALAHAN 

    kesalahan_data_all = [] 
    kesalahan_data_filtered = [] 
    kesalahan_headers = []
    staff_headers = []
    staff_rows = []
    total_kesalahan_staff = 0
    available_months = [] 
    latest_month = None # Inisialisasi

    # Logika untuk sheet khusus tetap sama
    if sheet_name in sheet_khusus:
        # ... (Logika untuk sheet khusus tetap sama) ...
        range_kesalahan = sheet_khusus[sheet_name]
        kesalahan_data_all = get_sheet_data(
            SHEETS_SERVICE, sheet_name, range_kesalahan, expected_columns=3, spreadsheet_id=LIVECHAT_SPREADSHEET_ID
        )
        kesalahan_headers = KHUSUS_KESALAHAN_HEADERS
        kesalahan_data_filtered = kesalahan_data_all
        total_kesalahan_staff = len(kesalahan_data_filtered)
        
        if kesalahan_data_all:
             available_months = get_available_months(kesalahan_data_all)
        
        # Karena ini sheet khusus, tidak perlu penanganan 'all' yang kompleks
        current_filter_to_display = month_filter if month_filter else 'all' 
        
    else:
        ranges_for_sheet = [
            f"'{sheet_name}'!{range_kesalahan_default}", 
            f"'{sheet_name}'!{LIVECHAT_RANGE_STAFF}" 
        ]
        
        batch_results = get_batch_sheet_data(SHEETS_SERVICE, ranges_for_sheet, LIVECHAT_SPREADSHEET_ID)
        
        batch_0 = batch_results[0].get('values', []) if len(batch_results) > 0 else []
        filtered_kesalahan_data_raw = [
            row for row in batch_0 if any(cell and cell.strip() for cell in row)
        ]

        
        if filtered_kesalahan_data_raw:
            kesalahan_data_raw_no_header = filtered_kesalahan_data_raw[1:] 
            available_months = get_available_months(kesalahan_data_raw_no_header)
            
            # Tambahkan opsi 'all' untuk ditampilkan di dropdown detail
            if 'all' not in available_months:
                 available_months.insert(0, 'all')
            
            # Tentukan bulan terbaru
            latest_month = available_months[1] if len(available_months) > 1 else 'all'

            # =======================================================
            # MODIFIKASI INTI: Tentukan filter yang akan digunakan untuk data
            # =======================================================
            if not month_filter: # URL default: /namasitus
                # Default: Paksa ke bulan terbaru 
                actual_month_filter = latest_month
                current_filter_to_display = latest_month # Bulan terbaru terpilih di dropdown
            elif month_filter.lower() == 'all': # URL: /namasitus/all
                # Sesuai permintaan: MEMUAT SEMUA DATA
                actual_month_filter = 'all'
                current_filter_to_display = 'all' # Opsi 'all' terpilih
            else: # URL: /namasitus/08-2025
                actual_month_filter = month_filter
                current_filter_to_display = month_filter

            
            # Gunakan actual_month_filter untuk memfilter data
            kesalahan_data_for_calc = filter_kesalahan_by_month(kesalahan_data_raw_no_header, actual_month_filter)
            
            kesalahan_data_filtered = [
                (row + [''] * (3 - len(row)))[:3] for row in kesalahan_data_for_calc
            ]
            # data_all digunakan untuk perhitungan staff, harus sesuai dengan filter yang aktif
            kesalahan_data_all = kesalahan_data_for_calc 
        else:
            kesalahan_data_all = []
            kesalahan_data_filtered = []
            available_months = ['all']
            current_filter_to_display = 'all'
        
        # ... (Logika staff data tetap sama) ...

        kesalahan_headers = TARGET_KESALAHAN_HEADERS
        
        batch_1 = batch_results[1].get('values', []) if len(batch_results) > 1 else []
        staff_data_raw = [
            row for row in batch_1 if row and row[0].strip()
        ]
        
        staff_list_for_calc = []
        if staff_data_raw and len(staff_data_raw) > 1:
            staff_list_for_calc = staff_data_raw[1:]

        if staff_list_for_calc: 
            staff_headers, staff_rows, total_kesalahan_staff = calculate_staff_errors_from_kesalahan(
                kesalahan_data_all, staff_list_for_calc # menggunakan data yang sudah difilter
            )
        else:
            staff_headers = staff_data_raw[0] if staff_data_raw else []
            total_kesalahan_staff = 0
            staff_rows = []
            
    # Akhir dari blok else (untuk non-sheet khusus)
             
    # Memastikan current_filter_to_display valid
    if current_filter_to_display not in available_months:
        current_filter_to_display = available_months[0] if available_months else 'all'

    return render_template('index.html',
                           kesalahan_headers=kesalahan_headers,
                           kesalahan_data=kesalahan_data_filtered, 
                           staff_headers=staff_headers,
                           staff_rows=staff_rows,
                           current_sheet=sheet_name,
                           sheet_names=sheet_names,
                           kesalahan_sheet_names=kesalahan_sheet_names, 
                           total_kesalahan_staff=total_kesalahan_staff,
                           SHEET_KHUSUS=sheet_khusus,
                           title_prefix='Data Kesalahan Livechat',
                           available_months=available_months, 
                           current_month_filter=current_filter_to_display # Menggunakan nilai yang benar untuk display
                           )