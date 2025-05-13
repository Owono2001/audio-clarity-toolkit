import os
from app import create_app # Import your app factory

# Create a Flask app instance to configure Celery
# This loads the configuration from config.py via the app factory
flask_app = create_app()

# Get the Celery instance from the Flask app
celery_app = flask_app.extensions["celery"]

# You might need to run the worker with:
# celery -A celery_worker.celery_app worker --loglevel=info
# Or, if your tasks are in app.tasks:
# celery -A app.tasks.celery worker --loglevel=info (if celery is defined in tasks.py)
# The celery_init_app in __init__.py should make `flask_app.extensions["celery"]` the main celery app.

# To run Celery Beat for scheduled tasks (like cleanup):
# celery -A celery_worker.celery_app beat --loglevel=info -s /path/to/celerybeat-schedule
# The schedule path helps persist schedule state.

# If you define tasks within the app package (e.g. app.tasks),
# the worker needs to discover them.
# Ensure your tasks.py file is imported somewhere or Celery's autodiscover_tasks is used.
# celery_app.autodiscover_tasks(['app']) # if your tasks are in 'app.tasks' module

# The command to run will typically be:
# celery -A celery_worker.celery_app worker -l INFO -B
# The -B flag runs the beat scheduler embedded in the worker, useful for development.
# For production, run worker and beat as separate processes.