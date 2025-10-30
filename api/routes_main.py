# api/routes_main.py

import re
from urllib.parse import unquote
from flask import render_template, redirect, url_for, request, flash
import math

from .app import (
    app, SHEETS_SERVICE, KESALAHAN_SHEETS_SERVICE,
    LIVECHAT_SPREADSHEET_ID, KESALAHAN_SPREADSHEET_ID,
    load_global_config, init_sheets_api_service, init_kesalahan_sheets_service
)
from .config import SUMMARY_LIVECHAT_ROUTE
from .database import (
    get_special_sheets, SiteConfig, SpecialSheet,
    get_global_config, update_global_config,
    update_or_add_site_config, delete_site_config,
    update_or_add_special_sheet, delete_special_sheet
)
from .sheets_api import get_sheet_names

# =========================================================================
# FUNGSI PEMBANTU: Mengambil semua nama sheet (Livechat dan Kesalahan)
# =========================================================================

def get_all_sheet_names():
    """Mengambil daftar sheet dari Livechat dan Kesalahan untuk navigasi."""
    sheet_khusus = get_special_sheets()
    sheet_names_livechat = []
    kesalahan_sheet_names = []
    
    # 1. Sheet Livechat
    if SHEETS_SERVICE and LIVECHAT_SPREADSHEET_ID:
        try:
            # Gunakan try/except untuk menghindari kegagalan fatal
            sheet_names_livechat = get_sheet_names(SHEETS_SERVICE, sheet_khusus, LIVECHAT_SPREADSHEET_ID)
        except Exception as e:
            print(f"Peringatan: Gagal mengambil sheet Livechat: {e}")

    # 2. Sheet Kesalahan
    if KESALAHAN_SHEETS_SERVICE and KESALAHAN_SPREADSHEET_ID:
        try:
            # Sheet kesalahan tidak menggunakan filter sheet_khusus
            kesalahan_sheet_names = get_sheet_names(KESALAHAN_SHEETS_SERVICE, {}, KESALAHAN_SPREADSHEET_ID)
        except Exception as e:
            print(f"Peringatan: Gagal mengambil sheet Kesalahan: {e}")

    return sheet_names_livechat, kesalahan_sheet_names, sheet_khusus

# =========================================================================
# ROUTE UTAMA
# =========================================================================

@app.route('/')
def home():
    if SHEETS_SERVICE is None:
        config_url = url_for('show_db_config')
        message = f"Gagal terhubung ke Google Sheets API. Silakan cek kredensial. <a href='{config_url}' class='font-bold underline'>Atur Konfigurasi</a>."
        return render_template('error.html', message=message)
        
    return render_template('welcome.html', summary_route=SUMMARY_LIVECHAT_ROUTE)


@app.route('/config', methods=['GET', 'POST'])
def show_db_config():
    
    site_configs = SiteConfig.query.order_by(SiteConfig.id).all()
    special_sheets = SpecialSheet.query.order_by(SpecialSheet.id).all()
    
    sheets_service_reinitialized = False
    kesalahan_service_reinitialized = False
    config_save_error = False

    if request.method == 'POST':
        action = request.form.get('action')
        
        try:
            # --- Logika Delete ---
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

            # --- Logika Save All ---
            elif action == 'save_all':
                
                # Livechat Configuration Save
                new_livechat_id = request.form.get('spreadsheet_livechat', '').strip()
                global_id_changed = new_livechat_id != globals().get('LIVECHAT_SPREADSHEET_ID')
                if global_id_changed:
                    sheets_service_reinitialized = True

                update_global_config('SPREADSHEET_LIVECHAT', new_livechat_id)
                update_global_config('RANGE_KESALAHAN_DEFAULT', request.form.get('range_kesalahan', '').strip())
                update_global_config('RANGE_STAFF_DEFAULT', request.form.get('range_staff', '').strip())
                
                # Kesalahan Configuration Save
                new_kesalahan_id = request.form.get('spreadsheet_kesalahan', '').strip()
                kesalahan_id_changed = new_kesalahan_id != globals().get('KESALAHAN_SPREADSHEET_ID')
                if kesalahan_id_changed:
                    kesalahan_service_reinitialized = True
                
                update_global_config('SPREADSHEET_KESALAHAN', new_kesalahan_id)
                update_global_config('RANGE_KESALAHAN_STAFF', request.form.get('range_kesalahan_staff', '').strip())
                update_global_config('RANGE_KESALAHAN_FATAL', request.form.get('range_kesalahan_fatal', '').strip())
                
                # Update existing site configs
                for site in site_configs:
                    # Ambil kedua nama situs dari form
                    site_name_livechat = request.form.get(f'site_name_livechat_{site.id}', '').strip()
                    site_name_kesalahan = request.form.get(f'site_name_kesalahan_{site.id}', '').strip()
                    leader_name = request.form.get(f'leader_name_{site.id}', '').strip()
                    
                    if site_name_livechat and site_name_kesalahan and leader_name:
                        # Panggil fungsi yang diperbarui
                        if not update_or_add_site_config(site.id, site_name_livechat, site_name_kesalahan, leader_name):
                            config_save_error = True
                            flash(f'❌ Gagal menyimpan Situs (ID: {site.id}). Salah satu nama situs mungkin **sudah ada** atau kosong.', 'danger')
                        
                # Add new site configs
                for key, value in request.form.items():
                    if key.startswith('new_site_name_livechat_'):
                        new_id_suffix = key.replace('new_site_name_livechat_', '')
                        site_name_livechat = value.strip()
                        site_name_kesalahan = request.form.get(f'new_site_name_kesalahan_{new_id_suffix}', '').strip()
                        leader_name = request.form.get(f'new_leader_name_{new_id_suffix}', '').strip()
                        
                        if site_name_livechat and site_name_kesalahan and leader_name:
                            # Panggil fungsi yang diperbarui
                            if not update_or_add_site_config(f'new_{new_id_suffix}', site_name_livechat, site_name_kesalahan, leader_name):
                                config_save_error = True
                                flash(f'❌ Gagal menambahkan Situs baru. Salah satu nama situs mungkin **sudah ada**.', 'danger')

                # Update existing special sheets
                for sheet in special_sheets:
                    sheet_name = request.form.get(f'special_sheet_name_{sheet.id}', '').strip()
                    sheet_range = request.form.get(f'special_sheet_range_{sheet.id}', '').strip()
                    if sheet_name and sheet_range:
                        if not update_or_add_special_sheet(sheet.id, sheet_name, sheet_range):
                            config_save_error = True
                            flash(f'❌ Gagal menyimpan Sheet Khusus (ID: {sheet.id}). Nama "{sheet_name}" mungkin **sudah ada** atau kosong.', 'danger')

                # Add new special sheets
                for key, value in request.form.items():
                    if key.startswith('new_special_sheet_name_'):
                        new_id_suffix = key.replace('new_special_sheet_name_', '')
                        sheet_name = value.strip()
                        sheet_range = request.form.get(f'new_special_sheet_range_{new_id_suffix}', '').strip()
                        
                        if sheet_name and sheet_range:
                            if not update_or_add_special_sheet(f'new_{new_id_suffix}', sheet_name, sheet_range):
                                config_save_error = True
                                flash(f'❌ Gagal menambahkan Sheet Khusus baru. Nama "{sheet_name}" mungkin **sudah ada**.', 'danger')
                            
                # Re-initialize services if IDs changed
                with app.app_context():
                    load_global_config()
                    if sheets_service_reinitialized:
                        init_sheets_api_service()
                    if kesalahan_service_reinitialized:
                        init_kesalahan_sheets_service()
                
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