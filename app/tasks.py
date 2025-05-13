import os
import time
from datetime import datetime, timedelta
from celery import shared_task, current_task
from flask import current_app 

# Import the NEW core processing function for cleanup
from app.services.audio_processor import cleanup_audio_core # <<< ENSURE THIS IS THE IMPORT

import logging
logger = logging.getLogger(__name__)

@shared_task(bind=True)
def perform_audio_cleanup_task(self, input_filepath, original_filename, output_filename_base, output_format, cleanup_options): # Renamed task
    """
    Celery task to perform audio cleanup operations.
    """
    logger.info(f"Celery audio cleanup task {self.request.id} started for {original_filename} with options: {cleanup_options}")
    
    output_folder = current_app.config['PROCESSED_FOLDER']
    output_filepath = os.path.join(output_folder, f"{output_filename_base}.{output_format}")

    try:
        self.update_state(state='PROGRESS', meta={'status': 'Initializing audio cleanup...', 'progress': 1, 'original_filename': original_filename})
        
        def update_celery_meta(state, meta):
            meta_to_update = {'original_filename': original_filename}
            meta_to_update.update(meta)
            self.update_state(state=state, meta=meta_to_update)

        success, result_or_error = cleanup_audio_core( # Calls the cleanup core function
            input_path=input_filepath,
            output_path=output_filepath,
            output_format=output_format,
            cleanup_options=cleanup_options,
            task_update_meta_func=update_celery_meta
        )

        if success:
            logger.info(f"Cleanup task {self.request.id} completed successfully. Output: {result_or_error}")
            return {'status': 'Audio cleaned successfully!', 'progress': 100, 'result_filename': result_or_error, 'original_filename': original_filename}
        else:
            logger.error(f"Cleanup task {self.request.id} failed for {original_filename}. Error: {result_or_error}")
            failure_meta = {
                'status': f'Audio cleanup error: {result_or_error}', 
                'progress': 0, 
                'original_filename': original_filename, 
                'error_details': result_or_error
            }
            if self.AsyncResult(self.request.id).state != 'FAILURE':
                 self.update_state(state='FAILURE', meta=failure_meta)
            return failure_meta

    except Exception as e:
        logger.critical(f"Critical error in Celery cleanup task {self.request.id} for {original_filename}: {e}", exc_info=True)
        critical_error_meta = {
            'status': f'Critical task error: {str(e)}', 
            'progress': 0, 
            'original_filename': original_filename,
            'error_details': str(e)
        }
        self.update_state(state='FAILURE', meta=critical_error_meta)
        return critical_error_meta
    finally:
        if os.path.exists(input_filepath):
            try:
                os.remove(input_filepath)
                logger.info(f"Cleaned up uploaded file for cleanup task: {input_filepath}")
            except OSError as e:
                logger.error(f"Error cleaning up uploaded file {input_filepath} for cleanup task: {e}")


@shared_task(name='app.tasks.cleanup_old_files_task')
def cleanup_old_files_task(max_age_days=7):
    upload_folder = current_app.config['UPLOAD_FOLDER']
    processed_folder = current_app.config['PROCESSED_FOLDER']
    try:
        max_age_days_config = current_app.config.get('CLEANUP_MAX_FILE_AGE_DAYS', str(max_age_days))
        max_age_days_int = int(max_age_days_config)
    except ValueError:
        logger.warning(f"Invalid CLEANUP_MAX_FILE_AGE_DAYS: '{max_age_days_config}'. Using {max_age_days} days.")
        max_age_days_int = int(max_age_days)
    now = time.time()
    cutoff = now - (max_age_days_int * 24 * 60 * 60)
    logger.info(f"Running cleanup task. Deleting files older than {max_age_days_int} days.")
    cleaned_count = 0
    for folder_path in [upload_folder, processed_folder]:
        if not os.path.isdir(folder_path):
            logger.warning(f"Cleanup: Folder '{folder_path}' does not exist. Skipping.")
            continue
        try:
            for filename in os.listdir(folder_path):
                filepath = os.path.join(folder_path, filename)
                if os.path.isfile(filepath): 
                    try:
                        if os.path.getmtime(filepath) < cutoff:
                            os.remove(filepath)
                            logger.info(f"Cleanup: Deleted old file '{filepath}'")
                            cleaned_count += 1
                    except FileNotFoundError:
                        logger.warning(f"Cleanup: File '{filepath}' not found. Skipping.")
                    except OSError as e:
                        logger.error(f"Cleanup: Error deleting file '{filepath}': {e}")
        except Exception as e:
             logger.error(f"Cleanup: Error listing files in '{folder_path}': {e}", exc_info=True)
    logger.info(f"Cleanup task finished. Deleted {cleaned_count} old files.")
    return f"Cleaned up {cleaned_count} files older than {max_age_days_int} days."
