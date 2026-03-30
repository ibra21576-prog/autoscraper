import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'autoscraper-secret-key-change-me')

    # DB: PostgreSQL (Render/Cloud) oder SQLite (lokal)
    # Render/Neon setzen DATABASE_URL als postgres://...
    _db_url = os.environ.get('DATABASE_URL', '')
    # Heroku/Render nutzen "postgres://" aber SQLAlchemy braucht "postgresql://"
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = _db_url or ('sqlite:///' + os.path.join(basedir, 'instance', 'autoscraper.db'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Mail settings
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', '')

    # Scraper settings
    SCRAPE_DELAY_MIN = 2  # Sekunden
    SCRAPE_DELAY_MAX = 5
    ALERT_CHECK_INTERVAL = 30  # Minuten

    # Live-Scraper settings
    LIVE_SCRAPE_INTERVAL = 10  # Sekunden zwischen Scrapes pro Plattform
    LIVE_SCRAPE_ENABLED = os.environ.get('LIVE_SCRAPE_ENABLED', 'true').lower() == 'true'

    # Background-Scraper
    BG_SCRAPE_INTERVAL_HOURS = int(os.environ.get('BG_SCRAPE_INTERVAL_HOURS', 2))
