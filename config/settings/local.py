"""
Local development settings.
"""
from .base import *

DEBUG = True

# Use SQLite for local development
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'mon_projet_db',
        'USER': 'admin',
        'PASSWORD': 'password123',
        'HOST': '127.0.0.1',
        'PORT': '5432',
    }
}


# Disable throttling in development
REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = []
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {}

# CORS - allow all in dev
CORS_ALLOW_ALL_ORIGINS = True

# Email - mettre ton email Gmail et le mot de passe d'application (16 caractères)
# Pour obtenir le mot de passe d'application : https://myaccount.google.com/apppasswords
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'gestioninfinie01@gmail.com'        
EMAIL_HOST_PASSWORD = 'qtfh lomj ugqe stkt'      
DEFAULT_FROM_EMAIL = 'G-Infini <gestioninfinie01@gmail.com>'  
