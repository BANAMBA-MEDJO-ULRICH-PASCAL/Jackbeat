import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DEV_SECRET_KEY = 'dev-key-a-changer-en-production'


def _env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


def _db_url(default):
    """Render fournit postgres:// ; on nomme explicitement le pilote installé
    (psycopg2) pour ne pas dépendre du pilote par défaut de SQLAlchemy."""
    url = os.environ.get('DATABASE_URL') or default
    for prefix in ('postgres://', 'postgresql://'):
        if url.startswith(prefix):
            url = 'postgresql+psycopg2://' + url[len(prefix):]
    return url


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or DEV_SECRET_KEY
    # Sel séparé pour l'anonymisation des IP (sinon dérivé de SECRET_KEY)
    IP_HASH_SALT = os.environ.get('IP_HASH_SALT')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}

    # ── Protection CSRF (Flask-WTF, activée globalement) ──
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 4 * 3600

    # ── Compte admin initial (créé uniquement si aucun admin n'existe) ──
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'admin'
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

    # ── Sessions & cookies ──
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_NAME = 'jb_session'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    REMEMBER_COOKIE_DURATION = timedelta(days=1)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'

    # ── Anti brute-force sur la connexion admin ──
    LOGIN_MAX_FAILS_PER_IP = 10           # sur la fenêtre ci-dessous
    LOGIN_MAX_FAILS_PER_USER = 20
    LOGIN_LOCKOUT_MINUTES = 15
    RATELIMIT_ENABLED = True

    # ── Langues ──
    BABEL_DEFAULT_LOCALE = 'fr'
    BABEL_DEFAULT_TIMEZONE = 'Africa/Douala'
    LANGUAGES = {'fr': 'Français', 'en': 'English'}

    # Nombre de proxys de confiance devant l'application (Render = 1)
    TRUSTED_PROXIES = int(os.environ.get('TRUSTED_PROXIES', '0'))

    # Requêtes plus grosses que ça : refusées (aucun upload sur ce site)
    MAX_CONTENT_LENGTH = 256 * 1024


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = _db_url('sqlite:///' + os.path.join(BASE_DIR, 'jackbeat_dev.db'))
    # Confort de développement uniquement — jamais utilisé en production
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'jackbeat2024'


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = 'test-secret-key-not-for-production-0123456789'
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    ADMIN_PASSWORD = 'Test-Admin-Pass-2026!'
    WTF_CSRF_ENABLED = os.environ.get('JB_TEST_CSRF', '0') == '1'
    RATELIMIT_ENABLED = False


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = _db_url('sqlite:///' + os.path.join(BASE_DIR, 'jackbeat.db'))
    TRUSTED_PROXIES = int(os.environ.get('TRUSTED_PROXIES', '1'))

    # Sécurité renforcée en production
    SESSION_COOKIE_SECURE   = True
    REMEMBER_COOKIE_SECURE  = True
    PREFERRED_URL_SCHEME    = 'https'

    @classmethod
    def validate(cls):
        """Refuse de démarrer avec une configuration dangereuse."""
        errors = []
        key = os.environ.get('SECRET_KEY', '')
        if len(key) < 32 or key == DEV_SECRET_KEY:
            errors.append('SECRET_KEY doit être définie (32 caractères aléatoires minimum).')
        if errors:
            raise RuntimeError('Configuration de production invalide : ' + ' '.join(errors))


config = {
    'development': DevelopmentConfig,
    'testing':     TestingConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}
