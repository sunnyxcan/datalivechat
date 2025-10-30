# api/routes_livechat.py

import re
from urllib.parse import unquote
from flask import render_template, redirect, url_for
import math

# Impor dari 'app' dan 'routes_main'
from .app import (
    app, SHEETS_SERVICE, 
    LIVECHAT_SPREADSHEET_ID, LIVECHAT_RANGE_KESALAHAN, LIVECHAT_RANGE_STAFF,
)
from .config import SUMMARY_LIVECHAT_ROUTE, TARGET_KESALAHAN_HEADERS, KHUSUS_KESALAHAN_HEADERS
# PERUBAHAN DI SINI: Mengganti get_leader_mapping menjadi get_livechat_leader_mapping
from .database import get_livechat_leader_mapping 
from .sheets_api import (
    get_sheet_data, get_batch_sheet_data, calculate_sheet_total
)
from .filters import format_number
from .routes_main import get_all_sheet_names # Impor fungsi pembantu

# =========================================================================
# ROUTE LIVECHAT
# =========================================================================

@app.route(f'/{SUMMARY_LIVECHAT_ROUTE}')
def show_summary_livechat():
    if SHEETS_SERVICE is None:
        return redirect(url_for('home'))

    # Ambil semua nama sheet untuk navigasi
    sheet_names_livechat, kesalahan_sheet_names, sheet_khusus = get_all_sheet_names()
    
    # PERUBAHAN DI SINI: Menggunakan fungsi yang baru
    leader_mapping = get_livechat_leader_mapping()
    sheet_names_from_api = sheet_names_livechat # Nama sheet Livechat bulanan
    
    # Livechat Summary TIDAK menggunakan leader_mapping, tapi menggunakan daftar sheet Livechat.
    # Namun, bagian di bawah ini menggunakan leader_mapped_sites_uppercase untuk menentukan situs mana yang VALID/dimonitor.
    leader_mapped_sites_uppercase = {k.upper(): v for k, v in leader_mapping.items()}
    all_sites_map = {}
    
    sheets_to_process = [name for name in sheet_names_from_api if name not in sheet_khusus]
    # Catatan: Jika sheet Livechat dan sheet Kesalahan memiliki nama yang sama, 
    # proses ini masih menggunakan nama sheet Livechat (karena kita mengambil dari sheet_names_livechat)
    sites_for_batch_read = list({name.upper() for name in sheets_to_process if name.upper() in leader_mapped_sites_uppercase})
    
    for site_upper, leader in leader_mapped_sites_uppercase.items():
        all_sites_map[site_upper] = {
            'total': 0,
            'url': url_for('show_data', sheet_name=site_upper)
        }

    ranges_to_get = [f"'{sheet_name}'!{LIVECHAT_RANGE_STAFF}" for sheet_name in sites_for_batch_read]
    batch_results = get_batch_sheet_data(SHEETS_SERVICE, ranges_to_get, LIVECHAT_SPREADSHEET_ID)
    
    grand_total = 0
    staff_summary_map = {} 
    staff_list_details = []
    leader_summary_map = {} 
    
    leader_names = {name.strip().upper() for name in leader_mapping.values()}
    all_staff_names_from_leaders = set(leader_names)

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

    summary_data = [] 
    for site_upper, details in all_sites_map.items():
        summary_data.append({
            'name': site_upper.title(),
            'total': details['total'],
            'url': details['url']
        })
        
    summary_data.sort(key=lambda x: x['total'], reverse=True) 
    
    # Perhitungan Staf Summary
    for staff_name in all_staff_names_from_leaders:
        if staff_name not in staff_summary_map:
            staff_summary_map[staff_name] = 0
            
    # Filter staf yang bukan Leader (berdasarkan leader_mapping.values())
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

    # Perhitungan Leader Summary
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
                           current_sheet='Ringkasan Livechat', 
                           sheet_names=sheet_names_livechat, 
                           kesalahan_sheet_names=kesalahan_sheet_names, 
                           summary_data=summary_data, 
                           grand_total=grand_total,
                           summary_staff_data=final_summary_staff_data, 
                           staff_grand_total=staff_grand_total,
                           summary_leader_data=final_summary_leader_data, 
                           leader_grand_total=leader_grand_total,
                           title_prefix='Data Kesalahan Livechat'
                           )


@app.route('/<sheet_name>')
def show_data(sheet_name):
    if SHEETS_SERVICE is None:
        return redirect(url_for('home'))

    sheet_name = unquote(sheet_name)
    
    # Ambil semua nama sheet untuk navigasi
    sheet_names_livechat, kesalahan_sheet_names, sheet_khusus = get_all_sheet_names()
    sheet_names = sheet_names_livechat 
    
    kesalahan_data = []
    kesalahan_headers = []
    staff_headers = []
    staff_rows = []
    total_kesalahan_staff = 0

    if sheet_name in sheet_khusus:
        # Sheet Khusus (custom range)
        range_kesalahan = sheet_khusus[sheet_name]

        kesalahan_data = get_sheet_data(
            SHEETS_SERVICE,
            sheet_name,
            range_kesalahan,
            expected_columns=3,
            spreadsheet_id=LIVECHAT_SPREADSHEET_ID
        )

        kesalahan_headers = KHUSUS_KESALAHAN_HEADERS

    else:
        # Sheet Livechat Bulanan (batch read untuk data kesalahan dan staf)
        ranges_for_sheet = [
            f"'{sheet_name}'!{LIVECHAT_RANGE_KESALAHAN}",
            f"'{sheet_name}'!{LIVECHAT_RANGE_STAFF}"
        ]
        
        batch_results = get_batch_sheet_data(SHEETS_SERVICE, ranges_for_sheet, LIVECHAT_SPREADSHEET_ID)
        
        # Data Kesalahan
        batch_0 = batch_results[0].get('values', []) if len(batch_results) > 0 else []
        
        filtered_kesalahan_data = [
            row for row in batch_0 if any(cell and cell.strip() for cell in row)
        ]

        kesalahan_headers = TARGET_KESALAHAN_HEADERS
        if filtered_kesalahan_data:
            kesalahan_data = [
                (row + [''] * (3 - len(row)))[:3] for row in filtered_kesalahan_data[1:]
            ]
        else:
            kesalahan_data = []

        # Data Staf
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
                           kesalahan_sheet_names=kesalahan_sheet_names, 
                           total_kesalahan_staff=total_kesalahan_staff,
                           SHEET_KHUSUS=sheet_khusus,
                           title_prefix='Data Kesalahan Livechat'
                           )