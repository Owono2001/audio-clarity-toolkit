# Use an official Python runtime as a parent image
FROM python:3.10-slim-bullseye

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV FLASK_APP="app:create_app()"
ENV FLASK_ENV="production" 
# Note: FLASK_DEBUG should be False in production, typically set by Render's env vars or omitted here.

# Set work directory
WORKDIR /app

# Install system dependencies
# - ffmpeg is essential for pydub to handle various audio formats
# - libmagic1 is for python-magic-bin
# - build-essential might be needed for some Python packages with C extensions
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    libmagic1 \
    build-essential \
    # Add any other system dependencies your app might need
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the image
COPY . .

# Ensure necessary directories exist and are writable by the app user
# (Docker typically runs as root unless specified otherwise, which is fine for Render's environment)
RUN mkdir -p /app/uploads /app/processed_audio /app/logs
# If running as non-root, you'd add: RUN chown -R app_user:app_group /app/uploads ...

# Expose the port the app runs on (Gunicorn will bind to this)
EXPOSE 5000 

# The CMD will be overridden by Render's start command in render.yaml
# but it's good practice to have a default.
# This default won't run Redis or Celery, just the web app.
# CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:create_app()"]