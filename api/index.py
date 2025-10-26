# api/index.py

from .app import app, SHEETS_SERVICE

# PENTING: Import routes agar terdaftar di instance 'app'
from . import routes 


if __name__ == '__main__':
    # Di lingkungan produksi, Anda akan menggunakan WSGI seperti Gunicorn, 
    # tetapi untuk pengembangan, app.run sudah cukup.
    if SHEETS_SERVICE is not None:
        try:
            app.run(debug=True)
        except Exception:
            pass
    else:
        try:
            app.run(debug=True)
        except Exception:
            pass