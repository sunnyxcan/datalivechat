# api/seed_db.py

import json
from .index import app
from .database import db, SiteConfig, SpecialSheet, GlobalConfig
from sqlalchemy.orm.exc import NoResultFound

# --- DATA KONFIGURASI AWAL UNTUK SITE_CONFIG (LEADER_MAPPING) ---
LEADER_MAPPING_INITIAL = {
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

# --- DATA KONFIGURASI AWAL UNTUK SPECIAL_SHEET (SHEET_KHUSUS) ---
SHEET_KHUSUS_INITIAL = {
    'POIN-POIN KESALAHAN LC': 'A3:C',
}

# --- DATA KONFIGURASI AWAL UNTUK GLOBAL_CONFIG ---
GLOBAL_CONFIG_INITIAL = {
    'SPREADSHEET_ID': '1TkOeAMhwlmG1WftjAyJAlSBYzbR-JPum4sTIKliPtss', 
    'SCOPES': json.dumps(['https://www.googleapis.com/auth/spreadsheets.readonly']),
    'RANGE_LIVECHAT_DEFAULT': 'A1:C',
    'RANGE_STAFF_DEFAULT': 'H1:AH',
}

def seed_database():
    """Memasukkan data awal ke database."""
    print("Memulai proses seeding database...")
    with app.app_context():
        # Memastikan tabel dibuat (Berguna jika database baru atau skema diubah)
        db.create_all()

        # 1. SEED GLOBAL CONFIG
        print("\n== 1. GLOBAL CONFIG ==")
        for key, value in GLOBAL_CONFIG_INITIAL.items():
            existing_config = GlobalConfig.query.get(key)
            if not existing_config:
                new_config = GlobalConfig(key=key, value=value)
                db.session.add(new_config)
                print(f" 🟢 Menambahkan {key}")
            else:
                existing_config.value = value
                print(f" 🔄 Memperbarui {key}")


        # 2. SEED SITE CONFIG (LEADER_MAPPING)
        print("\n== 2. LEADER MAPPING (SiteConfig) ==")
        for site, leader in LEADER_MAPPING_INITIAL.items():
            site_upper = site.upper()
            
            # PERBAIKAN: Menggunakan filter_by karena site_name bukan lagi Primary Key
            existing_config = SiteConfig.query.filter_by(site_name=site_upper).first()
            
            if not existing_config:
                new_config = SiteConfig(site_name=site_upper, leader_name=leader)
                db.session.add(new_config)
                print(f" 🟢 Menambahkan {site_upper}")
            else:
                existing_config.leader_name = leader
                print(f" 🔄 Memperbarui {site_upper}")

        # 3. SEED SPECIAL SHEET (SHEET_KHUSUS)
        print("\n== 3. SPECIAL SHEET ==")
        for sheet, sheet_range in SHEET_KHUSUS_INITIAL.items():
            
            # PERBAIKAN: Menggunakan filter_by karena sheet_name bukan lagi Primary Key
            existing_sheet = SpecialSheet.query.filter_by(sheet_name=sheet).first()
            
            if not existing_sheet:
                new_sheet = SpecialSheet(sheet_name=sheet, sheet_range=sheet_range)
                db.session.add(new_sheet)
                print(f" 🟢 Menambahkan {sheet}")
            else:
                existing_sheet.sheet_range = sheet_range
                print(f" 🔄 Memperbarui {sheet}")

        try:
            db.session.commit()
            print("\n✅ Data awal berhasil dimasukkan dan diperbarui!")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Gagal memasukkan data. Rolling back sesi: {e}")

if __name__ == '__main__':
    seed_database()