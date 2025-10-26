# api/routes.py

import re
from urllib.parse import unquote
from flask import render_template, redirect, url_for, request, flash

from .app import (
    app, SHEETS_SERVICE, GLOBAL_SPREADSHEET_ID, 
    GLOBAL_RANGE_KESALAHAN, GLOBAL_RANGE_STAFF, 
    load_global_config, init_sheets_api_service
)
from .config import SUMMARY_ROUTE, TARGET_KESALAHAN_HEADERS, KHUSUS_KESALAHAN_HEADERS
from .database import (
    get_leader_mapping, get_special_sheets, SiteConfig, SpecialSheet,
    get_global_config, update_global_config, 
    update_or_add_site_config, delete_site_config,
    update_or_add_special_sheet, delete_special_sheet
)
from .sheets_api import (
    get_sheet_names, get_sheet_data, 
    get_batch_sheet_data, calculate_sheet_total
)
from .filters import format_number


@app.route('/')
def home():
    if SHEETS_SERVICE is None:
        config_url = url_for('show_db_config')
        message = f"Gagal terhubung ke Google Sheets API. Silakan cek kredensial. <a href='{config_url}' class='font-bold underline'>Atur Konfigurasi</a>."
        return render_template('error.html', message=message)
        
    return render_template('welcome.html', summary_route=SUMMARY_ROUTE)


@app.route('/config', methods=['GET', 'POST'])
def show_db_config():
    
    site_configs = SiteConfig.query.order_by(SiteConfig.id).all()
    special_sheets = SpecialSheet.query.order_by(SpecialSheet.id).all()
    
    sheets_service_reinitialized = False
    config_save_error = False

    if request.method == 'POST':
        action = request.form.get('action')
        
        try:
            # --- 1. HANDLE DELETE ACTIONS (HAPUS) ---
            if action and action.startswith('delete_site_'):
                site_id = action.replace('delete_site_', '')
                if delete_site_config(site_id):
                    flash(f'Pemetaan Situs (ID: {site_id}) berhasil dihapus.', 'success')
                else:
                    flash('Gagal menghapus pemetaan situs.', 'danger')
                return redirect(url_for('show_db_config'))

            elif action and action.startswith('delete_special_'):
                sheet_id = action.replace('delete_special_', '')
                if delete_special_sheet(sheet_id):
                    flash(f'Sheet Khusus (ID: {sheet_id}) berhasil dihapus.', 'success')
                else:
                    flash('Gagal menghapus sheet khusus.', 'danger')
                return redirect(url_for('show_db_config'))

            # --- 2. HANDLE SAVE ALL (SIMPAN) ---
            elif action == 'save_all':
                
                # A. GLOBAL CONFIGURATION
                new_spreadsheet_id = request.form.get('spreadsheet_id', '').strip()
                global_id_changed = new_spreadsheet_id != globals().get('GLOBAL_SPREADSHEET_ID')
                if global_id_changed:
                    sheets_service_reinitialized = True

                update_global_config('SPREADSHEET_ID', new_spreadsheet_id)
                update_global_config('RANGE_KESALAHAN_DEFAULT', request.form.get('range_kesalahan', '').strip())
                update_global_config('RANGE_STAFF_DEFAULT', request.form.get('range_staff', '').strip())
                
                # B. SITE CONFIGURATION (Update & Add)
                for site in site_configs: 
                    site_name = request.form.get(f'site_name_{site.id}', '').strip()
                    leader_name = request.form.get(f'leader_name_{site.id}', '').strip()
                    if site_name and leader_name:
                        if not update_or_add_site_config(site.id, site_name, leader_name):
                            config_save_error = True
                            flash(f'❌ Gagal menyimpan Situs (ID: {site.id}). Nama "{site_name}" mungkin **sudah ada** atau kosong.', 'danger')
                        
                for key, value in request.form.items():
                    if key.startswith('new_site_name_'):
                        new_id_suffix = key.replace('new_site_name_', '')
                        site_name = value.strip()
                        leader_name = request.form.get(f'new_leader_name_{new_id_suffix}', '').strip()
                        
                        if site_name and leader_name:
                            if not update_or_add_site_config(f'new_{new_id_suffix}', site_name, leader_name):
                                config_save_error = True
                                flash(f'❌ Gagal menambahkan Situs baru. Nama "{site_name}" mungkin **sudah ada**.', 'danger')

                # C. SPECIAL SHEETS (Update & Add)
                for sheet in special_sheets:
                    sheet_name = request.form.get(f'special_sheet_name_{sheet.id}', '').strip()
                    sheet_range = request.form.get(f'special_sheet_range_{sheet.id}', '').strip()
                    if sheet_name and sheet_range:
                        if not update_or_add_special_sheet(sheet.id, sheet_name, sheet_range):
                            config_save_error = True
                            flash(f'❌ Gagal menyimpan Sheet Khusus (ID: {sheet.id}). Nama "{sheet_name}" mungkin **sudah ada** atau kosong.', 'danger')

                for key, value in request.form.items():
                    if key.startswith('new_special_sheet_name_'):
                        new_id_suffix = key.replace('new_special_sheet_name_', '')
                        sheet_name = value.strip()
                        sheet_range = request.form.get(f'new_special_sheet_range_{new_id_suffix}', '').strip()
                        
                        if sheet_name and sheet_range:
                            if not update_or_add_special_sheet(f'new_{new_id_suffix}', sheet_name, sheet_range):
                                config_save_error = True
                                flash(f'❌ Gagal menambahkan Sheet Khusus baru. Nama "{sheet_name}" mungkin **sudah ada**.', 'danger')
                            
                # D. INISIALISASI ULANG & PESAN AKHIR
                # Gunakan app context untuk memuat konfigurasi ke variabel global di app.py
                with app.app_context():
                    load_global_config()
                    if sheets_service_reinitialized:
                        init_sheets_api_service()
                
                if not config_save_error:
                    flash('✅ Semua konfigurasi berhasil disimpan!', 'success')
                else:
                    flash('⚠️ Perhatian: Terdapat kegagalan saat menyimpan beberapa konfigurasi. Silakan periksa pesan error di atas.', 'warning')
            
            else:
                flash('Aksi penyimpanan tidak valid.', 'danger')

        except Exception as e:
            flash(f'❌ Gagal memproses permintaan: {e}', 'danger')
        
        return redirect(url_for('show_db_config'))

    return render_template(
        'config_db.html',
        current_sheet='Konfigurasi Database',
        global_config=get_global_config(), 
        site_configs=SiteConfig.query.order_by(SiteConfig.id).all(), 
        special_sheets=SpecialSheet.query.order_by(SpecialSheet.id).all()
    )


@app.route(f'/{SUMMARY_ROUTE}')
def show_summary():
    if SHEETS_SERVICE is None:
        return redirect(url_for('home')) 

    leader_mapping = get_leader_mapping()
    sheet_khusus = get_special_sheets()
    sheet_names_from_api = get_sheet_names(SHEETS_SERVICE, sheet_khusus, GLOBAL_SPREADSHEET_ID)
    
    leader_mapped_sites_uppercase = {k.upper(): v for k, v in leader_mapping.items()}
    all_sites_map = {}
    
    sheets_to_process = [name for name in sheet_names_from_api if name not in sheet_khusus]
    sites_for_batch_read = list({name.upper() for name in sheets_to_process if name.upper() in leader_mapped_sites_uppercase})
    
    for site_upper, leader in leader_mapped_sites_uppercase.items():
        all_sites_map[site_upper] = { 
            'total': 0,
            'url': url_for('show_data', sheet_name=site_upper)
        }

    # 1. Ambil semua data Staff sekaligus (Batch Read)
    ranges_to_get = [f"'{sheet_name}'!{GLOBAL_RANGE_STAFF}" for sheet_name in sites_for_batch_read]
    batch_results = get_batch_sheet_data(SHEETS_SERVICE, ranges_to_get, GLOBAL_SPREADSHEET_ID) 
    
    grand_total = 0 
    staff_summary_map = {} 
    staff_list_details = []
    leader_summary_map = {}
    
    leader_names = {name.strip().upper() for name in leader_mapping.values()} 
    all_staff_names_from_leaders = set(leader_names)

    # 2. Proses hasil Batch Read
    for i, sheet_name_upper in enumerate(sites_for_batch_read):
        
        if i < len(batch_results) and sheet_name_upper in all_sites_map:
            result_range = batch_results[i]
            staff_data = result_range.get('values', [])
            
            filtered_staff_data = [
                row for row in staff_data if any(cell and cell.strip() for cell in row)
            ]
            
            total_situs, staff_rows = calculate_sheet_total(filtered_staff_data)
            
            all_sites_map[sheet_name_upper]['total'] = total_situs 
            grand_total += total_situs
            
            leader_name = leader_mapping.get(sheet_name_upper) 
            if leader_name:
                leader_summary_map[leader_name] = leader_summary_map.get(leader_name, 0) + total_situs
            
            for row in staff_rows:
                if len(row) > 1:
                    staff_name = row[0].strip().upper()
                    if not staff_name or staff_name.lower() == 'total':
                        continue
                        
                    num_str = re.sub(r'[^\d]', '', row[1].strip()) 
                    staff_total = int(num_str) if num_str.isdigit() else 0
                    
                    all_staff_names_from_leaders.add(staff_name) 
                    
                    if staff_name: 
                        staff_list_details.append({
                            'name': staff_name,
                            'situs': sheet_name_upper, 
                            'total': staff_total
                        })
                        staff_summary_map[staff_name] = staff_summary_map.get(staff_name, 0) + staff_total

    # 3. Finalisasi Data Ringkasan Situs
    summary_data = []
    for site_upper, details in all_sites_map.items():
        summary_data.append({
            'name': site_upper.title(), 
            'total': details['total'],
            'url': details['url']
        })
        
    summary_data.sort(key=lambda x: x['total'], reverse=True)
    
    # 4. Finalisasi Data Ringkasan Staff Non-Leader
    for staff_name in all_staff_names_from_leaders:
        if staff_name not in staff_summary_map:
            staff_summary_map[staff_name] = 0
            
    staff_names_only = {name for name in staff_summary_map.keys() if name.title() not in leader_mapping.values()} 
    staff_summary_map_filtered = {
        name: staff_summary_map[name] for name in staff_names_only
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

    # 5. Finalisasi Data Ringkasan Leader
    final_summary_leader_data = []
    leader_grand_total = 0
    leader_details_map = {leader: {'total': 0, 'sites': []} for leader in leader_mapping.values()}
    
    for original_situs_name_upper, details in all_sites_map.items(): 
        leader_name = leader_mapping.get(original_situs_name_upper) 

        if leader_name:
            leader_details_map[leader_name]['total'] += details['total']
            
            leader_details_map[leader_name]['sites'].append({
                'name': original_situs_name_upper.title(), 
                'total': details['total']
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
        
    return render_template('index.html',
                           current_sheet='Ringkasan Total', 
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
    if SHEETS_SERVICE is None:
        return redirect(url_for('home')) 

    sheet_name = unquote(sheet_name)
    
    sheet_khusus = get_special_sheets()
    sheet_names = get_sheet_names(SHEETS_SERVICE, sheet_khusus, GLOBAL_SPREADSHEET_ID)

    kesalahan_data = []
    kesalahan_headers = []
    staff_headers = []
    staff_rows = []
    total_kesalahan_staff = 0 

    if sheet_name in sheet_khusus:
        range_kesalahan = sheet_khusus[sheet_name]

        kesalahan_data = get_sheet_data(
            SHEETS_SERVICE,
            sheet_name,
            range_kesalahan,
            expected_columns=3,
            spreadsheet_id=GLOBAL_SPREADSHEET_ID
        )

        kesalahan_headers = KHUSUS_KESALAHAN_HEADERS 

    else:
        ranges_for_sheet = [
            f"'{sheet_name}'!{GLOBAL_RANGE_KESALAHAN}",
            f"'{sheet_name}'!{GLOBAL_RANGE_STAFF}"
        ]
        
        batch_results = get_batch_sheet_data(SHEETS_SERVICE, ranges_for_sheet, GLOBAL_SPREADSHEET_ID)
        
        # 1. Proses Data Kesalahan
        kesalahan_data_with_header = batch_results[0].get('values', []) if len(batch_results) > 0 else []
        
        filtered_kesalahan_data = [
            row for row in kesalahan_data_with_header if any(cell and cell.strip() for cell in row)
        ]

        kesalahan_headers = TARGET_KESALAHAN_HEADERS
        if filtered_kesalahan_data:
            kesalahan_data = [
                (row + [''] * (3 - len(row)))[:3] for row in filtered_kesalahan_data[1:]
            ]
        else:
            kesalahan_data = []

        # 2. Proses Data Staff
        staff_data = batch_results[1].get('values', []) if len(batch_results) > 1 else []

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
                           SHEET_KHUSUS=sheet_khusus)