import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-really-bad-secret-key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://postgres:postgres@localhost:5432/postgres'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # The image that's displayed at the top of every page.
    # Intentionally not committed to the repo to avoid copyright and trademark issues.
    # Should be located at wanikani-visualizer/app/static/
    basedir = os.path.abspath(os.path.dirname(__file__))
    LOGO = 'logo.png' if os.path.exists(basedir + '/app/static/logo.png') else None
