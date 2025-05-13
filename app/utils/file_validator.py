import magic
import os
from flask import current_app # Use current_app to access config

def is_allowed_file(filename, file_stream):
    """
    Checks if the file extension and MIME type are allowed.
    file_stream should be the raw file stream (e.g., request.files['file'].stream)
    """
    config = current_app.config # Access config through current_app proxy

    # 1. Check extension
    if not ('.' in filename and filename.rsplit('.', 1)[1].lower() in config['ALLOWED_EXTENSIONS']):
        current_app.logger.warning(f"File validation failed: Disallowed extension for {filename}")
        return False, "File extension not allowed."

    # 2. Check MIME type using python-magic
    try:
        # Read a small portion of the file to determine MIME type
        # Ensure the stream is at the beginning
        file_stream.seek(0)
        file_header = file_stream.read(2048) # Read first 2KB
        file_stream.seek(0) # Reset stream position for further processing (like saving)

        mime_detector = magic.Magic(mime=True)
        actual_mime_type = mime_detector.from_buffer(file_header)

        if actual_mime_type not in config['ALLOWED_MIME_TYPES']:
            current_app.logger.warning(f"File validation failed: Disallowed MIME type {actual_mime_type} for {filename}")
            return False, f"File content type ({actual_mime_type}) not allowed."
        
        current_app.logger.info(f"File validation success for {filename}, MIME: {actual_mime_type}")
        return True, "File is valid."

    except Exception as e:
        current_app.logger.error(f"Error during MIME type detection for {filename}: {e}", exc_info=True)
        return False, "Could not verify file content type."