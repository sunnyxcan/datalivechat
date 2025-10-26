# api/database.py

import json
import redis
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from .config import DATABASE_URL, REDIS_URL

db = SQLAlchemy()

try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
except Exception:
    redis_client = None

# --- MODELS ---

class SiteConfig(db.Model):
    __tablename__ = 'site_config'
    id = db.Column(db.Integer, primary_key=True) 
    site_name = db.Column(db.String(100), unique=True, nullable=False)
    leader_name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    def __repr__(self):
        return f"<SiteConfig site='{self.site_name}' leader='{self.leader_name}'>"

class SpecialSheet(db.Model):
    __tablename__ = 'special_sheet'
    id = db.Column(db.Integer, primary_key=True)
    sheet_name = db.Column(db.String(100), unique=True, nullable=False)
    sheet_range = db.Column(db.String(50), nullable=False)
    def __repr__(self):
        return f"<SpecialSheet name='{self.sheet_name}' range='{self.sheet_range}'>"
        
class GlobalConfig(db.Model):
    __tablename__ = 'global_config'
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, nullable=False)
    def __repr__(self):
        return f"<GlobalConfig key='{self.key}' value='{self.value[:30]}...'>"

# --- FUNGSI CACHE REDIS ---

CACHE_TTL_24_JAM = 3600 * 24 

def get_data_with_cache(cache_key, fetch_func, cache_ttl=300):
    if redis_client:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            try:
                return json.loads(cached_data)
            except (json.JSONDecodeError, TypeError):
                if redis_client:
                    redis_client.delete(cache_key)
    
    data = fetch_func()
    
    if redis_client and data:
        try:
            redis_client.set(cache_key, json.dumps(data), ex=cache_ttl) 
        except Exception:
            pass
        
    return data

# --- FUNGSI HELPER (TTL 24 JAM) ---

def _fetch_leader_mapping_from_db():
    try:
        results = SiteConfig.query.filter_by(is_active=True).order_by(SiteConfig.id).all()
        return {item.site_name.upper(): item.leader_name for item in results}
    except Exception:
        return {}

def get_leader_mapping():
    return get_data_with_cache('config:leader_mapping', _fetch_leader_mapping_from_db, cache_ttl=CACHE_TTL_24_JAM) 


def _fetch_special_sheets_from_db():
    try:
        results = SpecialSheet.query.order_by(SpecialSheet.id).all()
        return {item.sheet_name: item.sheet_range for item in results}
    except Exception:
        return {}

def get_special_sheets():
    return get_data_with_cache('config:special_sheets', _fetch_special_sheets_from_db, cache_ttl=CACHE_TTL_24_JAM)


def _fetch_global_config_from_db():
    try:
        results = GlobalConfig.query.all()
        config_map = {item.key: item.value for item in results}
        
        if 'SCOPES' in config_map and isinstance(config_map['SCOPES'], str):
            try:
                config_map['SCOPES'] = json.loads(config_map['SCOPES'])
            except (json.JSONDecodeError, TypeError):
                config_map['SCOPES'] = [s.strip() for s in config_map['SCOPES'].split(',')]

        return config_map
    except Exception:
        return {}
        
def get_global_config():
    return get_data_with_cache('config:global_config', _fetch_global_config_from_db, cache_ttl=CACHE_TTL_24_JAM)


# --- FUNGSI UPDATE/HAPUS ---

def _clear_cache(keys):
    if redis_client:
        try:
            if isinstance(keys, str):
                keys = [keys]
            redis_client.delete(*keys)
        except Exception:
            pass

def update_global_config(key, new_value):
    try:
        config_item = GlobalConfig.query.get(key)
        
        if isinstance(new_value, (list, dict)):
            value_to_store = json.dumps(new_value)
        else:
            value_to_store = str(new_value)

        if config_item:
            config_item.value = value_to_store
        else:
            config_item = GlobalConfig(key=key, value=value_to_store)
            db.session.add(config_item)
            
        db.session.commit()
        _clear_cache('config:global_config') 
        return True
    except Exception:
        db.session.rollback()
        return False

def update_or_add_site_config(site_id, site_name, leader_name):
    try:
        if str(site_id).startswith('new_'):
            new_site = SiteConfig(site_name=site_name, leader_name=leader_name)
            db.session.add(new_site)
        else:
            site = SiteConfig.query.get(int(site_id))
            if site:
                site.site_name = site_name
                site.leader_name = leader_name
        
        db.session.commit()
        _clear_cache('config:leader_mapping') 
        return True
    except IntegrityError:
        db.session.rollback()
        return False
    except Exception:
        db.session.rollback()
        return False

def delete_site_config(site_id):
    try:
        site = SiteConfig.query.get(int(site_id))
        if site:
            db.session.delete(site)
            db.session.commit()
            _clear_cache('config:leader_mapping') 
            return True
        return False
    except Exception:
        db.session.rollback()
        return False

def update_or_add_special_sheet(sheet_id, sheet_name, sheet_range):
    try:
        if str(sheet_id).startswith('new_'):
            new_sheet = SpecialSheet(sheet_name=sheet_name, sheet_range=sheet_range)
            db.session.add(new_sheet)
        else:
            sheet = SpecialSheet.query.get(int(sheet_id))
            if sheet:
                sheet.sheet_name = sheet_name
                sheet.sheet_range = sheet_range

        db.session.commit()
        _clear_cache('config:special_sheets') 
        return True
    except IntegrityError:
        db.session.rollback()
        return False
    except Exception:
        db.session.rollback()
        return False

def delete_special_sheet(sheet_id):
    try:
        sheet = SpecialSheet.query.get(int(sheet_id))
        if sheet:
            db.session.delete(sheet)
            db.session.commit()
            _clear_cache('config:special_sheets') 
            return True
        return False
    except Exception:
        db.session.rollback()
        return False