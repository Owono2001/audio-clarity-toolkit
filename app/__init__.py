import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from celery import Celery, Task
from config import Config
from flask_bootstrap import Bootstrap # For Bootstrap integration
import arrow # For the datetimeformat filter
import datetime # For the datetimeformat filter

# --- Celery Integration ---
def celery_init_app(app: Flask) -> Celery:
    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config, namespace='CELERY')
    celery_app.set_default()
    app.extensions["celery"] = celery_app
    return celery_app

# --- App Factory ---
def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize Celery
    celery_init_app(app)
    
    # Initialize Bootstrap
    bootstrap = Bootstrap(app) 

    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    # Configure Logging
    if not app.debug and not app.testing:
        if not os.path.exists(os.path.dirname(app.config['LOG_FILE'])):
            os.makedirs(os.path.dirname(app.config['LOG_FILE']))
        
        file_handler = RotatingFileHandler(
            app.config['LOG_FILE'],
            maxBytes=102400,  # 100KB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(app.config['LOG_LEVEL'])
        app.logger.addHandler(file_handler)
        app.logger.setLevel(app.config['LOG_LEVEL'])
        app.logger.info('Audio Processor App startup')

    # --- Custom Jinja Filters & Context Processors ---
    # Ensure these are defined and registered within the app factory
    # or at least before the first template rendering that uses them.

    @app.template_filter('datetimeformat_filter') # Correctly named decorator
    def datetimeformat_filter_func(value, format_str="%Y-%m-%d %H:%M:%S"): # Function name can be different
        if value == "now":
            # Get current time. Arrow defaults to local.
            dt = arrow.now() 
        elif isinstance(value, (datetime.datetime, datetime.date)):
            dt = arrow.get(value)
        else: 
            try:
                dt = arrow.get(value) # Try to parse if it's a string or timestamp
            except arrow.parser.ParserError: # Catch specific Arrow parsing error
                app.logger.warning(f"datetimeformat_filter: Could not parse value '{value}' with Arrow. Returning as is.")
                return value # Return original if parsing fails
            except Exception as e: # Catch other potential errors during parsing
                app.logger.error(f"datetimeformat_filter: Unexpected error parsing value '{value}': {e}")
                return value
        return dt.strftime(format_str) # Use strftime for standard formatting

    @app.context_processor
    def inject_now_variable(): # Renamed for clarity
        # This makes 'now_for_template' available in all templates.
        # The filter will then be applied to this variable in the template.
        return {'now_for_template': "now"} 

    # Register blueprints or import routes
    # It's important that routes (and thus templates) are processed *after*
    # filters and context processors are set up if they are used globally.
    with app.app_context():
        from . import routes

    # Ensure UPLOAD_FOLDER and PROCESSED_FOLDER exist (moved to end of factory for safety)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

    return app
