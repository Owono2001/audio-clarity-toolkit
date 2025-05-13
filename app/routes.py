import os
import uuid
import json 
from flask import (
    render_template, request, jsonify,
    current_app, send_from_directory, flash, redirect, url_for
)
from werkzeug.utils import secure_filename
from celery.result import AsyncResult

# Import the NEW Celery task for cleanup
from .tasks import perform_audio_cleanup_task # <<< ENSURE THIS IS THE IMPORT
from .utils.file_validator import is_allowed_file

@current_app.route('/', methods=['GET'])
def index():
    return render_template('index.html', app_name="Audio Clarity Toolkit")

@current_app.route('/upload', methods=['POST'])
def upload_audio():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected for uploading'}), 400

    output_format = request.form.get('output_format', 'wav').lower()
    if output_format not in current_app.config['ALLOWED_EXTENSIONS']:
        output_format = 'wav'

    cleanup_options_json = request.form.get('cleanup_options', '{}') 
    try:
        cleanup_options = json.loads(cleanup_options_json)
        if not isinstance(cleanup_options, dict):
            raise ValueError("Cleanup options must be a dictionary.")
    except json.JSONDecodeError:
        current_app.logger.error(f"Invalid JSON for cleanup_options: {cleanup_options_json}")
        return jsonify({'error': 'Invalid cleanup configuration data.'}), 400
    except ValueError as ve:
        current_app.logger.error(f"Validation error for cleanup_options: {ve}")
        return jsonify({'error': str(ve)}), 400

    is_valid, validation_msg = is_allowed_file(file.filename, file.stream)
    if not is_valid:
        current_app.logger.warning(f"Upload rejected: {file.filename}, Reason: {validation_msg}")
        return jsonify({'error': validation_msg}), 400

    try:
        original_filename = secure_filename(file.filename)
        file_ext = ''
        if '.' in original_filename:
            file_ext = original_filename.rsplit('.', 1)[1].lower()
        
        unique_id = uuid.uuid4().hex
        temp_input_filename = f"{unique_id}_input.{file_ext}" if file_ext else f"{unique_id}_input"
        input_filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], temp_input_filename)
        
        file.save(input_filepath)
        current_app.logger.info(f"File {original_filename} (saved as {temp_input_filename}) uploaded to {input_filepath}")

        output_filename_base = f"cleaned_{unique_id}_{os.path.splitext(original_filename)[0]}"

        task = perform_audio_cleanup_task.delay( # Calls the cleanup task
            input_filepath, 
            original_filename, 
            output_filename_base, 
            output_format,
            cleanup_options 
        )
        current_app.logger.info(f"Dispatched Celery cleanup task {task.id} for {original_filename} with options: {cleanup_options}")

        return jsonify({
            'task_id': task.id,
            'status_url': url_for('task_status', task_id=task.id, _external=True),
            'message': 'File upload successful, audio cleanup started...'
        }), 202

    except Exception as e:
        current_app.logger.error(f"Error during file upload or task dispatch for {file.filename if file else 'Unknown file'}: {e}", exc_info=True)
        if 'input_filepath' in locals() and os.path.exists(input_filepath) and 'task' not in locals():
             try:
                os.remove(input_filepath)
                current_app.logger.info(f"Cleaned up {input_filepath} after upload error.")
             except OSError:
                current_app.logger.error(f"Could not remove {input_filepath} after upload error.")
        return jsonify({'error': f'Server error during upload: {str(e)}'}), 500

@current_app.route('/status/<task_id>', methods=['GET'])
def task_status(task_id):
    celery_app = current_app.extensions['celery']
    task = celery_app.AsyncResult(task_id) 
    response_data = {'task_id': task_id, 'state': task.state}
    task_info = task.info if isinstance(task.info, dict) else {}

    if task.state == 'PENDING':
        response_data['status'] = 'Task is pending or not yet started.'
        response_data['progress'] = 0
    elif task.state == 'PROGRESS':
        response_data.update(task_info) 
    elif task.state == 'SUCCESS':
        response_data.update(task_info)
        if response_data.get('result_filename'): 
             response_data['download_url'] = url_for('download_processed_file', filename=response_data['result_filename'], _external=True)
        response_data['progress'] = 100
    elif task.state == 'FAILURE':
        response_data.update(task_info)
        response_data['status'] = task_info.get('status', 'Task failed.')
        response_data['status_message'] = task_info.get('error_details', str(task.info if not isinstance(task.info, dict) else 'Unknown error'))
        response_data['progress'] = 0
    else: 
        response_data['status'] = f'Task is in state: {task.state}'
        response_data.update(task_info)
    return jsonify(response_data)

@current_app.route('/download/<filename>', methods=['GET'])
def download_processed_file(filename):
    directory = current_app.config['PROCESSED_FOLDER']
    current_app.logger.info(f"Download requested for: {filename} from {directory}")
    try:
        return send_from_directory(directory, secure_filename(filename), as_attachment=True)
    except FileNotFoundError:
        current_app.logger.error(f"Download failed: File {filename} not found in {directory}.")
        flash("Requested file not found.", "error")
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify({'error': 'File not found'}), 404
        return redirect(url_for('index')) 
    except Exception as e:
        current_app.logger.error(f"Error during download of {filename}: {e}", exc_info=True)
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify({'error': 'Server error during download'}), 500
        flash("An error occurred while trying to download the file.", "error")
        return redirect(url_for('index'))

@current_app.route('/results/<task_id>', methods=['GET'])
def result_page(task_id):
    celery_app = current_app.extensions['celery']
    task = celery_app.AsyncResult(task_id)
    return render_template('result_page.html', task=task)
