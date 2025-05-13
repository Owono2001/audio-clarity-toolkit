import os
from dotenv import load_dotenv
from datetime import timedelta

# Load environment variables from .env file
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess-this-dev-key'
    FLASK_DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')

    # Celery Configuration
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/0'
    # CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True # For Celery 5+

    # File Paths
    UPLOAD_FOLDER = os.path.join(basedir, os.environ.get('UPLOAD_FOLDER_REL', 'uploads'))
    PROCESSED_FOLDER = os.path.join(basedir, os.environ.get('PROCESSED_FOLDER_REL', 'processed_audio'))
    
    # Logging
    LOG_FILE = os.path.join(basedir, os.environ.get('LOG_FILE_PATH', 'logs/app.log'))
    LOG_LEVEL = 'DEBUG' if FLASK_DEBUG else 'INFO'

    # File Upload Configuration
    MAX_CONTENT_LENGTH = 300 * 1024 * 1024  # 300 MB
    ALLOWED_EXTENSIONS = {'wav', 'mp3', 'm4a', 'ogg', 'flac'}
    ALLOWED_MIME_TYPES = {
        'audio/wav', 'audio/wave', 'audio/x-wav', 'audio/vnd.wave',
        'audio/mpeg', 'audio/mp3',
        'audio/mp4', 'audio/x-m4a',
        'audio/ogg',
        'audio/flac', 'audio/x-flac'
    }

    # Cleanup Task Configuration (Celery Beat)
    CELERY_BEAT_SCHEDULE = {
        'cleanup-old-files': {
            'task': 'app.tasks.cleanup_old_files_task',
            'schedule': timedelta(days=1), # Default, can be overridden by cron from .env
            # For more specific cron-like scheduling:
            # 'schedule': crontab(
            # minute=os.environ.get('CLEANUP_SCHEDULE_CRON_MINUTE', '0'),
            # hour=os.environ.get('CLEANUP_SCHEDULE_CRON_HOUR', '3')
            # ),
            'args': (int(os.environ.get('CLEANUP_MAX_FILE_AGE_DAYS', 7)),)
        },
    }
    # For cron from .env to work, you'd import from celery.schedules.crontab
    # and adjust CELERY_BEAT_SCHEDULE accordingly. For simplicity timedelta is used here.
    # For cron: from celery.schedules import crontab


# Ensure directories exist
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(Config.PROCESSED_FOLDER, exist_ok=True)
os.makedirs(os.path.dirname(Config.LOG_FILE), exist_ok=True)