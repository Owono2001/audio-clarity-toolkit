// app/static/js/main.js
document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('upload-form');
    const submitButton = document.getElementById('submit-button');
    const fileInput = document.getElementById('file');
    const fileNameDisplay = document.getElementById('file-name-display');
    const fileDropZone = document.getElementById('file-drop-zone');

    const uploadProgressDiv = document.getElementById('upload-progress');
    const statusMessageDiv = document.getElementById('status-message');
    const progressBarInner = document.getElementById('progress-bar-inner');
    const resultLinkContainer = document.getElementById('result-link-container');
    const errorDetailsContainer = document.getElementById('error-details-container');

    let currentTaskPollInterval = null;

    function setupToolParameterSlider(checkboxId, sliderId, valueDisplayId, unit = '', isFloat = false) {
        const checkbox = document.getElementById(checkboxId);
        const slider = document.getElementById(sliderId);
        const valueDisplay = document.getElementById(valueDisplayId);

        if (checkbox && slider && valueDisplay) {
            slider.disabled = !checkbox.checked; // Initial state based on checkbox
            let initialValue = isFloat ? parseFloat(slider.value).toFixed(slider.step.includes('.') ? slider.step.split('.')[1].length : 1) : slider.value;
            valueDisplay.textContent = initialValue + unit;

            checkbox.addEventListener('change', function() {
                slider.disabled = !this.checked;
            });
            slider.addEventListener('input', function() {
                let displayValue = isFloat ? parseFloat(this.value).toFixed(this.step.includes('.') ? this.step.split('.')[1].length : 1) : this.value;
                valueDisplay.textContent = displayValue + unit;
            });
        } else {
            console.warn(`Could not find all elements for tool setup: ${checkboxId}, ${sliderId}, ${valueDisplayId}`);
        }
    }

    // Setup for cleanup tools
    setupToolParameterSlider('enable_noise_reduction', 'noise_reduction_strength', 'noise_reduction_strength_value', '', true);
    setupToolParameterSlider('enable_high_pass_filter', 'high_pass_cutoff_hz', 'high_pass_cutoff_hz_value', ' Hz');
    setupToolParameterSlider('enable_normalization', 'normalization_target_dbfs', 'normalization_target_dbfs_value', ' dBFS');
    setupToolParameterSlider('enable_silence_trimming', 'trim_min_silence_ms', 'trim_min_silence_ms_value', ' ms');
    setupToolParameterSlider('enable_silence_trimming', 'trim_insert_silence_ms', 'trim_insert_silence_ms_value', ' ms');


    if (fileInput && fileNameDisplay) {
        fileInput.addEventListener('change', function() {
            if (fileInput.files.length > 0) {
                fileNameDisplay.textContent = `Selected: ${fileInput.files[0].name}`;
                if(fileDropZone) fileDropZone.classList.add('file-selected-visual');
            } else {
                fileNameDisplay.textContent = 'No file selected.';
                if(fileDropZone) fileDropZone.classList.remove('file-selected-visual');
            }
        });
    }

    if (fileDropZone && fileInput) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            fileDropZone.addEventListener(eventName, preventDefaults, false);
        });
        function preventDefaults(e) { e.preventDefault(); e.stopPropagation(); }
        ['dragenter', 'dragover'].forEach(eventName => {
            fileDropZone.addEventListener(eventName, () => fileDropZone.classList.add('highlight-drop'), false);
        });
        ['dragleave', 'drop'].forEach(eventName => {
            fileDropZone.addEventListener(eventName, () => fileDropZone.classList.remove('highlight-drop'), false);
        });
        fileDropZone.addEventListener('drop', handleDrop, false);
        function handleDrop(e) {
            let dt = e.dataTransfer;
            let files = dt.files;
            if (files.length > 0) {
                fileInput.files = files;
                const event = new Event('change', { bubbles: true });
                fileInput.dispatchEvent(event);
            }
        }
    }

    if (uploadForm) {
        uploadForm.addEventListener('submit', function(event) {
            event.preventDefault();
            if (!fileInput.files || fileInput.files.length === 0) {
                handleError("Please select an audio file to process.", false, true);
                return;
            }

            clearPreviousStatus();
            disableForm(true, "Preparing audio...");

            const formData = new FormData();
            formData.append('file', fileInput.files[0], fileInput.files[0].name);
            
            const outputFormatSelect = document.getElementById('output_format');
            if (outputFormatSelect) {
                formData.append('output_format', outputFormatSelect.value);
            }

            const cleanup_options = {};
            if (document.getElementById('enable_normalization').checked) {
                cleanup_options.normalize = {
                    enabled: true,
                    target_dbfs: parseFloat(document.getElementById('normalization_target_dbfs').value)
                };
            }
            if (document.getElementById('enable_noise_reduction').checked) {
                cleanup_options.noise_reduce = {
                    enabled: true,
                    strength: parseFloat(document.getElementById('noise_reduction_strength').value)
                };
            }
            if (document.getElementById('enable_high_pass_filter').checked) {
                cleanup_options.high_pass = {
                    enabled: true,
                    cutoff_hz: parseInt(document.getElementById('high_pass_cutoff_hz').value)
                };
            }
            if (document.getElementById('enable_silence_trimming').checked) {
                cleanup_options.trim_silence = {
                    enabled: true,
                    min_silence_ms: parseInt(document.getElementById('trim_min_silence_ms').value),
                    insert_ms: parseInt(document.getElementById('trim_insert_silence_ms').value)
                };
            }
            formData.append('cleanup_options', JSON.stringify(cleanup_options));

            console.log("FormData entries (Cleanup):");
            for (let [key, value] of formData.entries()) {
                console.log(key, value);
            }
            
            const uploadUrl = '/upload';
            console.log("Attempting to POST to URL:", uploadUrl);

            uploadProgressDiv.style.display = 'block';
            statusMessageDiv.textContent = 'Uploading your audio file... Please wait.';
            statusMessageDiv.className = 'alert alert-info text-center';
            updateProgressBar(0, 'Initiating Upload');

            fetch(uploadUrl, {
                method: 'POST',
                body: formData,
            })
            .then(response => {
                console.log("Response status from server:", response.status);
                if (!response.ok) {
                    return response.json().then(errData => {
                        console.error("Server error JSON:", errData);
                        throw new Error(errData.error || `Server error: ${response.status}`);
                    }).catch((jsonParseError) => {
                        console.error("Error parsing JSON error or non-JSON error:", jsonParseError, response.statusText, response);
                        response.text().then(text => console.error("Non-JSON response body:", text));
                        throw new Error(`Server error: ${response.status} - ${response.statusText}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                console.log("Data received from server:", data);
                if (data.task_id && data.status_url) {
                    statusMessageDiv.textContent = 'Upload complete! Cleaning audio...';
                    statusMessageDiv.className = 'alert alert-primary text-center';
                    updateProgressBar(5, 'Processing Queued');
                    pollTaskStatus(data.task_id, fileInput.files[0].name);
                } else if (data.error) {
                    handleError(data.error);
                } else {
                    handleError('Unexpected response from server after upload.');
                }
            })
            .catch(error => {
                console.error('Upload fetch error:', error);
                handleError(`Upload failed: ${error.message}`);
            });
        });
    }

    function pollTaskStatus(taskId, originalFileName = "your file") {
        if (currentTaskPollInterval) { clearInterval(currentTaskPollInterval); }
        currentTaskPollInterval = setInterval(() => {
            fetch(`/status/${taskId}`).then(r => r.ok ? r.json() : Promise.reject(r)).then(data => {
                const dFN = (data.info && data.info.original_filename) ? data.info.original_filename : originalFileName;
                updateStatusDisplay(data, dFN);
                if (data.state === 'SUCCESS' || data.state === 'FAILURE') {
                    clearInterval(currentTaskPollInterval); currentTaskPollInterval = null; disableForm(false);
                    if (data.state === 'SUCCESS' && data.download_url && data.result_filename) {
                        displayDownloadLink(data.result_filename, data.download_url, dFN);
                        progressBarInner.classList.remove('progress-bar-animated', 'bg-primary'); progressBarInner.classList.add('bg-success');
                    } else if (data.state === 'FAILURE') {
                        let eM = (data.info && (data.info.status_message || data.info.error_details)) || data.status_message || 'Processing failed.';
                        if (dFN) eM = `Error processing ${dFN}: ${eM}`;
                        handleError(eM, true);
                        progressBarInner.classList.remove('progress-bar-animated', 'bg-primary'); progressBarInner.classList.add('bg-danger');
                    }
                }
            }).catch(err => { console.error('Polling error:', err); statusMessageDiv.textContent = `Error fetching status. Will retry.`; statusMessageDiv.className = 'alert alert-warning text-center'; });
        }, 2500);
    }

    function updateStatusDisplay(data, fileName) {
        let sT = (data.info && data.info.status) ? data.info.status : `Task is ${data.state}`;
        let p = (data.info && typeof data.info.progress !== 'undefined') ? data.info.progress : (data.state === 'SUCCESS' ? 100 : 0);
        if (fileName && (data.state === 'PROGRESS' || data.state === 'PENDING')) sT = `${sT} for "${fileName}"`;
        statusMessageDiv.textContent = sT; updateProgressBar(p, `${p}%`);
        progressBarInner.classList.remove('bg-success', 'bg-danger', 'bg-warning'); statusMessageDiv.classList.remove('alert-success', 'alert-danger', 'alert-warning', 'alert-primary');
        if (data.state === 'SUCCESS') { statusMessageDiv.className = 'alert alert-success text-center'; progressBarInner.classList.add('bg-success'); }
        else if (data.state === 'FAILURE') { statusMessageDiv.className = 'alert alert-danger text-center'; progressBarInner.classList.add('bg-danger'); }
        else if (data.state === 'PROGRESS' || data.state === 'PENDING') { statusMessageDiv.className = 'alert alert-info text-center'; progressBarInner.classList.add('bg-primary'); }
        else { statusMessageDiv.className = 'alert alert-warning text-center'; progressBarInner.classList.add('bg-warning'); }
    }

    function updateProgressBar(percentage, textContent = null) {
        percentage = Math.max(0, Math.min(100, parseInt(percentage, 10) || 0));
        progressBarInner.style.width = percentage + '%'; progressBarInner.textContent = textContent !== null ? textContent : percentage + '%'; progressBarInner.setAttribute('aria-valuenow', percentage);
        if (percentage < 100 && percentage > 0) progressBarInner.classList.add('progress-bar-animated'); else progressBarInner.classList.remove('progress-bar-animated');
    }

    function displayDownloadLink(filename, downloadUrl, originalFilename) {
        resultLinkContainer.innerHTML = ''; const link = document.createElement('a'); link.href = downloadUrl; link.textContent = `Download Cleaned Audio: ${filename}`; link.className = 'btn btn-success btn-lg'; link.setAttribute('download', filename);
        const icon = document.createElement('i'); icon.className = 'bi bi-download me-2'; link.prepend(icon);
        resultLinkContainer.appendChild(link); resultLinkContainer.style.display = 'block'; errorDetailsContainer.style.display = 'none';
    }

    function handleError(errorMessage, isProcessingError = false, isUIMessage = false) {
        if (isUIMessage) { statusMessageDiv.textContent = errorMessage; statusMessageDiv.className = 'alert alert-warning text-center'; uploadProgressDiv.style.display = 'block'; errorDetailsContainer.style.display = 'none'; resultLinkContainer.style.display = 'none'; }
        else { statusMessageDiv.textContent = isProcessingError ? 'Audio Cleanup Error' : 'Upload Error'; statusMessageDiv.className = 'alert alert-danger text-center'; updateProgressBar(0, 'Error'); progressBarInner.classList.add('bg-danger'); errorDetailsContainer.textContent = errorMessage; errorDetailsContainer.style.display = 'block'; resultLinkContainer.style.display = 'none'; }
        if (currentTaskPollInterval) { clearInterval(currentTaskPollInterval); currentTaskPollInterval = null; } disableForm(false);
    }

    function clearPreviousStatus() {
        uploadProgressDiv.style.display = 'none'; statusMessageDiv.textContent = ''; statusMessageDiv.className = 'alert alert-info text-center'; updateProgressBar(0, '0%'); progressBarInner.classList.remove('bg-success', 'bg-danger', 'bg-warning'); progressBarInner.classList.add('bg-primary', 'progress-bar-animated');
        resultLinkContainer.innerHTML = ''; resultLinkContainer.style.display = 'none'; errorDetailsContainer.innerHTML = ''; errorDetailsContainer.style.display = 'none';
        if (currentTaskPollInterval) { clearInterval(currentTaskPollInterval); currentTaskPollInterval = null; }
    }

    function disableForm(disabled, buttonTextOverride = null) {
        if (submitButton) {
            submitButton.disabled = disabled;
            if (disabled) { const pT = buttonTextOverride || "Cleaning Audio..."; submitButton.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> ${pT}`; }
            else { submitButton.innerHTML = '<i class="bi bi-magic"></i> Clean & Process Audio'; }
        }
        if (fileInput) fileInput.disabled = disabled;
        const oFS = uploadForm.querySelector('#output_format'); if (oFS) oFS.disabled = disabled;
        document.querySelectorAll('.tool-card input, .tool-card select').forEach(el => el.disabled = disabled);
    }
});