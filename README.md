# Audio Clarity Toolkit

## 1. Overview

The Audio Clarity Toolkit is a web application designed to improve the quality of audio files by performing a series of automated cleanup and enhancement steps. Users can upload their audio files through a web interface, and the application will process them asynchronously to normalize volume, reduce background noise, remove low-frequency rumble, and trim excessive silences. The goal is to produce clearer, more polished, and consistent-sounding audio.

## 2. Core Features

* **Volume Normalization:** Adjusts the audio to a consistent target loudness level (dBFS), making quiet parts audible and preventing loud parts from being too overpowering.
* **Noise Reduction:** Attenuates consistent background noise such as hiss, hum, or environmental sounds.
* **High-Pass Filter (Rumble Removal):** Removes unwanted very low frequencies, often perceived as rumble or mud, which can come from microphone handling, wind, or electrical interference.
* **Silence Trimming (Optional):**
    * Detects and removes or shortens excessively long silences at the beginning, end, or within an audio file.
    * Reconstructs the audio with shorter, standardized silences between valid audio segments.
* **User-Friendly Web Interface:** Allows users to easily upload files, select desired cleanup operations and their parameters, and monitor processing status.
* **Asynchronous Processing:** Audio processing tasks, which can be time-consuming, are handled in the background using Celery and Redis. This prevents the web browser from freezing and provides real-time progress updates to the user.
* **File Format Support:** Accepts common audio input formats (WAV, MP3, M4A, OGG, FLAC) and allows users to choose the output format (WAV, MP3, M4A).
* **File Validation:** Performs basic checks on uploaded file extensions and MIME types.
* **Automated File Cleanup:** Includes a scheduled task to periodically remove old uploaded and processed files from the server to manage disk space.

## 3. Technologies Used

* **Backend:**
    * **Python 3.10+**
    * **Flask:** Micro web framework for the web interface and API endpoints.
    * **Celery (with eventlet):** Distributed task queue for asynchronous background processing.
    * **Redis:** In-memory data store, used as a message broker for Celery and for storing task results.
    * **Pydub:** For high-level audio manipulation (loading, format conversion, volume adjustments, filtering, silence detection).
    * **NumPy:** For numerical operations on audio data, especially when interfacing with `noisereduce`.
    * **Noisereduce:** Library for performing spectral gating based noise reduction.
    * **(SciPy):** (Can be used for more advanced custom filters if needed, but Pydub's filters are used for simplicity for HPF/LPF in the current version).
    * **python-magic-bin:** For identifying file MIME types (Windows-friendly).
    * **python-dotenv:** For managing environment variables from a `.env` file.
    * **Arrow:** For improved date/time handling (used in a Jinja filter for display).
* **Frontend:**
    * **HTML5**
    * **CSS3** (with custom styling and Bootstrap 5)
    * **Bootstrap 5:** For responsive design and pre-styled UI components.
    * **JavaScript (Vanilla JS):** For AJAX file uploads, dynamic UI updates, and polling task status.
* **Development & Deployment (Considerations):**
    * **Virtual Environment (`venv`):** For isolating project dependencies.
    * **Gunicorn (Recommended for Production):** WSGI HTTP server for running Flask in a production environment.

## 4. Project Structure

```text
Audio_web_app/ (or your project root folder name)
├── .vscode/                # VS Code specific settings
├── app/                    # Main application package
│   ├── init.py         # Initializes Flask app, Celery, extensions
│   ├── routes.py           # Flask routes (upload, status, download)
│   ├── tasks.py            # Celery tasks (perform_audio_cleanup_task, cleanup_old_files_task)
│   ├── services/
│   │   ├── init.py
│   │   └── audio_processor.py # Core audio cleanup logic (cleanup_audio_core)
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/main.js
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html      # Main upload and tool selection page
│   │   └── result_page.html
│   └── utils/
│       ├── init.py
│       └── file_validator.py
├── logs/                   # For log files
├── uploads/                # Temporary storage for uploaded files
├── processed_audio/        # Storage for cleaned audio files
├── celery_worker.py        # Script to get Celery app instance for worker
├── config.py               # Application configuration
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (secrets, URLs)
├── .flaskenv               # Flask CLI environment variables
└── .gitignore              # Files ignored by Git
```

## 5. Setup and Installation

1.  **Prerequisites:**
    * Python 3.10 or newer.
    * Redis server installed and running (default `localhost:6379`).
    * FFmpeg installed and added to your system's PATH (Pydub relies on it for various audio format operations).

2.  **Clone the Repository (if applicable):**
    ```bash
    git clone <your-repository-url>
    cd Audio_Clarity_Toolkit
    ```

3.  **Create and Activate a Virtual Environment:**
    ```bash
    # Windows (PowerShell)
    py -3.10 -m venv venv
    .\venv\Scripts\activate

    # macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Ensure `requirements.txt` includes `Celery[eventlet]` and `noisereduce`)*

5.  **Configure Environment Variables:**
    * Create a `.env` file in the project root.
    * Populate it with necessary configurations:
        ```env
        FLASK_APP=app:create_app()
        FLASK_DEBUG=True # Set to False for production
        SECRET_KEY='a_very_strong_random_secret_key_please_change_this'
        CELERY_BROKER_URL='redis://localhost:6379/0'
        CELERY_RESULT_BACKEND='redis://localhost:6379/0'

        UPLOAD_FOLDER_REL='uploads'
        PROCESSED_FOLDER_REL='processed_audio'
        LOG_FILE_PATH='logs/app.log'

        CLEANUP_SCHEDULE_CRON_MINUTE='0'
        CLEANUP_SCHEDULE_CRON_HOUR='3' # e.g., 3 AM daily
        CLEANUP_MAX_FILE_AGE_DAYS=7
        ```
    * Create a `.flaskenv` file in the root:
        ```env
        FLASK_APP=app:create_app()
        FLASK_DEBUG=True
        ```

## 6. Running the Application

You will need at least two terminal windows with the virtual environment activated.

1.  **Start Redis Server:** Ensure it's running.

2.  **Start the Celery Worker (and Beat Scheduler for cleanup):**
    In one terminal:
    ```bash
    celery -A celery_worker.celery_app worker -l info -P eventlet -B
    ```

3.  **Start the Flask Web Application:**
    In another terminal:
    ```bash
    flask run --host=0.0.0.0 --port=5000
    ```

4.  **Access the Application:**
    Open your web browser and go to `http://localhost:5000`.

## 7. Application Workflow (How it Works)

1.  **File Upload & Tool Selection (Client-Side):**
    * User navigates to the homepage (`index.html`).
    * They upload an audio file.
    * They select which cleanup tools to enable (Normalization, Noise Reduction, High-Pass Filter, Silence Trimming) and adjust their respective parameters using sliders.
    * `static/js/main.js` captures these selections and the file.
    * On clicking "Clean & Process Audio", JavaScript constructs a `FormData` object containing the file and a JSON string of `cleanup_options`. This is sent via an AJAX `POST` request to the `/upload` endpoint.

2.  **File Reception & Task Dispatch (Flask - `app/routes.py`):**
    * The `/upload` route receives the file and the `cleanup_options` JSON string.
    * It validates the uploaded file (extension, MIME type via `app/utils/file_validator.py`).
    * It parses the `cleanup_options` JSON.
    * If valid, the file is saved to the `uploads/` directory.
    * A Celery task `app.tasks.perform_audio_cleanup_task` is dispatched to Redis. This task is given the file path, original filename, output details, and the `cleanup_options` dictionary.
    * Flask returns an HTTP 202 (Accepted) response with a `task_id` to the client.

3.  **Status Polling (Client-Side - `static/js/main.js`):**
    * JavaScript polls the `/status/<task_id>` endpoint every few seconds.
    * The UI (progress bar, status messages) is updated based on the task's state received from this endpoint.

4.  **Task Execution (Celery Worker - `app/tasks.py` & `app/services/audio_processor.py`):**
    * A Celery worker picks up the `perform_audio_cleanup_task`.
    * The task function in `app/tasks.py` calls `cleanup_audio_core` from `app/services/audio_processor.py`.
    * **Audio Cleanup Steps (`cleanup_audio_core`):**
        1.  **Load Audio:** Input file is loaded using Pydub.
        2.  **Conditional Processing:** Based on the `cleanup_options` received:
            * If **Noise Reduction** is enabled: `_apply_noise_reduction` is called (uses `noisereduce` library).
            * If **High-Pass Filter** is enabled: `_apply_high_pass_filter` is called (uses Pydub's filter).
            * If **Normalization** is enabled: `_apply_normalization` is called (uses Pydub's normalize).
            * If **Silence Trimming** is enabled: `_apply_silence_trimming` is called (uses Pydub's `detect_nonsilent` and reconstructs audio).
            * The order of these operations is defined within `cleanup_audio_core` for optimal results (e.g., noise reduction often best first).
        3.  **Export:** The processed audio is exported to the `processed_audio/` directory.
    * **Task State Updates:** The Celery task updates its state (`PROGRESS`, `SUCCESS`, `FAILURE`) and metadata (progress percentage, messages) in Redis.
    * **Input File Cleanup:** The original uploaded file in `uploads/` is deleted after processing.

5.  **Displaying Results (Client-Side & Flask):**
    * The `/status/<task_id>` endpoint provides the latest task information.
    * If `SUCCESS`, the UI shows a success message and a download link for the cleaned file (via `/download/<filename>`).
    * If `FAILURE`, an error message is displayed.

6.  **Scheduled File Cleanup (Celery Beat - `app/tasks.py`):**
    * The `cleanup_old_files_task` runs periodically (e.g., daily) to delete old files from `uploads/` and `processed_audio/` directories, managed by `CELERY_BEAT_SCHEDULE` in `config.py`.

## 8. Guide: Using the Audio Clarity Toolkit

This section helps you get the best results from the available tools.

**General Tips for Audio Cleanup:**

* **Listen Before and After:** Always compare the processed audio to the original to ensure the changes are improvements. It's easy to over-process.
* **Subtlety is Key:** Often, small adjustments yield more natural and pleasing results than aggressive settings.
* **Order of Operations:** The toolkit applies cleanup steps in a generally recommended order (Noise Reduction -> HPF -> Normalization -> Silence Trimming). If these were individual effects you could reorder, the outcome would change.
* **Source Quality:** The better the original recording, the better the potential for cleanup. These tools can't fix severe distortion or extremely poor recordings.
* **Use Good Playback:** Listen on good quality headphones or speakers to accurately judge the changes.

**Understanding and Using Each Tool:**

**A. Volume Normalization**
* **What it does:** Adjusts the overall loudness of your audio to a target level (measured in dBFS - Decibels Full Scale, where 0dBFS is the maximum possible digital level). This makes your audio have a more consistent perceived loudness.
* **Parameters:**
    * `Target Level (dBFS)`: (Slider: -24dBFS to -1dBFS, Default: -16dBFS)
        * `-16 dBFS` is a common target for general content.
        * Louder targets (e.g., -10dBFS) might be used for some music genres but risk clipping if the audio has high peaks.
        * Quieter targets (e.g., -20dBFS) can provide more headroom.
* **When to Use:**
    * If your recording is too quiet overall.
    * If your recording has widely varying volume levels that you want to even out.
    * To bring multiple audio clips to a similar loudness before combining them.
* **Tips:**
    * Normalization makes the loudest peak hit the target. If your audio already has peaks near 0dBFS, normalizing to a high target like -1dBFS might not change much or could cause issues if not handled carefully (though Pydub's normalize is generally safe).
    * It doesn't compress the audio (reduce dynamic range), it just scales the whole thing up or down.

**B. Noise Reduction**
* **What it does:** Attempts to identify and reduce consistent background noise like hiss, hum, or steady fan noise. It works by analyzing parts of the audio it thinks are noise and then trying to subtract that "noise profile" from the rest.
* **Parameters:**
    * `Strength (0.1 - 1.0)`: Controls how aggressively the noise is reduced. (Corresponds to `prop_decrease` in the `noisereduce` library).
        * `0.1 - 0.4`: Subtle reduction, good for light noise, less risk of artifacts.
        * `0.5 - 0.8`: Moderate reduction, effective for noticeable noise. (Default: 0.8)
        * `0.9 - 1.0`: Aggressive reduction, can remove a lot of noise but also risks creating "watery" or "phasey" artifacts, or dulling the desired audio.
* **When to Use:**
    * Recordings with audible background hiss (e.g., from preamps, tape).
    * Recordings with a steady hum (though a targeted EQ or hum remover is often better for specific hum frequencies).
    * Field recordings with consistent wind or environmental noise (results may vary).
* **Tips:**
    * **Start Low:** Begin with a lower strength (e.g., 0.5) and gradually increase if needed.
    * **Listen for Artifacts:** Overly aggressive noise reduction can damage the quality of the desired audio, making vocals sound robotic or music sound muffled.
    * **Not for Variable Noise:** Less effective for intermittent noises like coughs, clicks, or traffic passing by.
    * The `noisereduce` library uses a spectral gating approach.

**C. High-Pass Filter (HPF) / Rumble Removal**
* **What it does:** Cuts frequencies *below* the selected "Cutoff Frequency," letting higher frequencies pass. This is excellent for removing unwanted low-end noise.
* **Parameters:**
    * `Cutoff Frequency (Hz)`: (Slider: 20Hz to 300Hz, Default: 80Hz)
        * `20-40 Hz`: Removes very deep, often inaudible sub-bass rumble that consumes energy.
        * `60-100 Hz`: Good for removing microphone handling noise, floor vibrations, and general low-end "mud" from vocals or many instruments without making them sound too thin. (80Hz is a common starting point for vocals).
        * `100-200 Hz`: Can be used on instruments like acoustic guitars or pianos if their low end is boomy. Use with care on sources with important bass content.
        * `Above 200 Hz`: Starts to significantly thin out most sounds.
* **When to Use:**
    * Almost always beneficial for voice recordings to improve clarity.
    * To clean up recordings made in noisy environments with low-frequency sounds (e.g., traffic rumble, AC).
    * To prevent low-frequency buildup when layering multiple tracks.
* **Tips:**
    * Set the cutoff just high enough to remove the unwanted noise but not so high that it thins out the desired sound.
    * For a full music mix, be very cautious with HPFs above 30-40Hz, as you can easily remove the power of the kick drum and bass.

**D. Trim Excessive Silences**
* **What it does:** Identifies long periods of silence in your audio and replaces them with shorter, standardized silences. It can also trim silence from the beginning and end.
* **Parameters:**
    * `Min. Silence to Trim (ms)`: (Slider: 500ms to 10000ms, Default: 3000ms) - Any silence in the original audio longer than this will be considered for trimming.
    * `Silence to Insert (ms)`: (Slider: 0ms to 5000ms, Default: 500ms) - The length of the silence that will be inserted between the remaining audio chunks, and at the beginning.
    * (Internal defaults also used: `DEFAULT_TRIM_CHUNK_MIN_DURATION_MS = 500ms` - audio segments shorter than this after splitting are discarded; `DEFAULT_SILENCE_THRESH_DB = -40dB` - how quiet something needs to be to be considered silence).
* **When to Use:**
    * Long pauses in speech recordings (podcasts, lectures, voiceovers) to make them more concise.
    * Removing dead air at the beginning or end of a recording.
    * Tightening up musical performances with long gaps.
* **Tips:**
    * **For Speech:** A `Min. Silence to Trim` of 2000-5000ms and an `Insert Silence` of 500-1000ms often works well.
    * **For Music:** Be more cautious. Natural pauses are part of music. This tool is more for removing genuinely excessive dead air rather than fine-tuning musical phrasing.
    * If `Min. Silence to Trim` is set too low, you might cut into natural pauses that are part of the performance.
    * If `Insert Silence` is too short, the audio might sound unnaturally rushed between segments. If too long, it defeats the purpose of trimming.
    * If your audio is very quiet overall, it might be misinterpreted as silence. Consider Normalizing or increasing Gain *before* silence trimming if this is an issue.

**Example Scenarios for Cleanup:**

* **Cleaning a Voice Recording (Podcast/Narration):**
    1.  **Noise Reduction:** Enabled, Strength ~0.6-0.8 (adjust based on noise level).
    2.  **High-Pass Filter:** Enabled, Cutoff ~80-100Hz (to remove mic rumble and plosives).
    3.  **Normalization:** Enabled, Target ~ -16dBFS to -18dBFS (common for voice).
    4.  **Trim Silences:** Enabled, Min Silence to Trim ~3000ms, Silence to Insert ~750ms.

* **Preparing a Field Recording (e.g., nature sounds with wind):**
    1.  **Noise Reduction:** Enabled, Strength might need to be higher (e.g., 0.7-0.9) for wind, but listen carefully for artifacts.
    2.  **High-Pass Filter:** Enabled, Cutoff ~100-150Hz (wind noise often has significant low-frequency energy).
    3.  **Normalization:** Enabled, Target depends on desired final loudness (e.g., -18dBFS).
    4.  **Trim Silences:** Probably disabled, unless there are specific long unwanted gaps.

* **Quick Polish for a Demo Music Track (Full Mix):**
    1.  **Noise Reduction:** Enabled, Strength ~0.3-0.5 (very subtle, if there's noticeable hiss).
    2.  **High-Pass Filter:** Enabled, Cutoff ~30-40Hz (to remove sub-bass rumble, be very careful).
    3.  **Normalization:** Enabled, Target ~ -14dBFS to -16dBFS (a common general level, but not true mastering).
    4.  **Trim Silences:** Likely disabled for a full music track unless there are obvious long errors.

---

**9. Configuration**
*(This section remains largely the same as your previous README)*
* **`.env` file:** Stores environment-specific variables.
* **`config.py`:** Defines a `Config` class.
* **`.flaskenv` file:** Used by the `flask` CLI.

---

**10. Logging**
*(This section remains largely the same as your previous README)*
* Configured for file-based logging to `logs/app.log`.

---

**11. Potential Future Enhancements**
*(Tailored slightly for the new app focus)*
* User accounts and file management.
* More advanced noise reduction profiles (e.g., hum removal, de-clicker).
* Basic Equalizer (EQ) controls.
* Compressor/Limiter for dynamic range control.
* Batch processing of multiple files.
* Real-time audio preview of cleanup effects before full processing.
* Option to choose the order of cleanup operations.

---
