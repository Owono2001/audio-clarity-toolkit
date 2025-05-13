import os
import logging
from pydub import AudioSegment
from pydub.effects import normalize as pydub_normalize
from pydub.effects import high_pass_filter as pydub_high_pass
from pydub.silence import detect_nonsilent # For silence trimming
import numpy as np
import noisereduce # Ensure this is installed: pip install noisereduce
import math # For log10 if used in any effect

logger = logging.getLogger(__name__)

# --- Default Parameters for Cleanup Tools (DEFINED AT THE TOP) ---
DEFAULT_NORMALIZATION_TARGET_DBFS = -16.0
DEFAULT_NOISE_REDUCTION_STRENGTH = 0.8 
DEFAULT_HPF_CUTOFF_HZ = 80
DEFAULT_TRIM_MIN_SILENCE_MS = 3000
DEFAULT_TRIM_INSERT_SILENCE_MS = 500 
DEFAULT_TRIM_CHUNK_MIN_DURATION_MS = 500
DEFAULT_SILENCE_THRESH_DB = -40 # Crucial definition for silence trimming

# --- Helper Functions for Cleanup Operations ---

def _apply_normalization(audio_segment, target_dbfs=DEFAULT_NORMALIZATION_TARGET_DBFS):
    """Normalizes an AudioSegment to a target dBFS."""
    logger.info(f"Normalizing audio to {target_dbfs} dBFS.")
    if not isinstance(target_dbfs, (int, float)) or target_dbfs > 0:
        logger.warning(f"Invalid target_dbfs: {target_dbfs}. Must be 0 or negative. Using default.")
        target_dbfs = DEFAULT_NORMALIZATION_TARGET_DBFS
    headroom = abs(target_dbfs) 
    return pydub_normalize(audio_segment, headroom=headroom)

def _apply_noise_reduction(audio_segment, strength=DEFAULT_NOISE_REDUCTION_STRENGTH):
    """Reduces noise in an AudioSegment using the noisereduce library."""
    logger.info(f"Applying noise reduction with strength (prop_decrease): {strength}.")
    if not (0 < strength <= 1.0):
        logger.warning(f"Invalid noise reduction strength: {strength}. Must be > 0 and <= 1.0. Using default.")
        strength = DEFAULT_NOISE_REDUCTION_STRENGTH
    
    sample_rate = audio_segment.frame_rate
    samples_original_dtype = np.array(audio_segment.get_array_of_samples()).dtype
    samples = np.array(audio_segment.get_array_of_samples()).astype(np.float32)

    if audio_segment.sample_width == 2: # 16-bit int
        samples = samples / 32768.0
    elif audio_segment.sample_width == 4: # 32-bit int
        samples = samples / 2147483648.0
    elif audio_segment.sample_width == 1: # 8-bit int
        samples = (samples - 128.0) / 128.0
    
    if audio_segment.channels > 1:
        num_channels = audio_segment.channels
        channels_data = [samples[i::num_channels] for i in range(num_channels)]
        reduced_channels_data = []
        for channel_samples in channels_data:
            contiguous_channel_samples = np.ascontiguousarray(channel_samples)
            reduced_channel = noisereduce.reduce_noise(y=contiguous_channel_samples, sr=sample_rate, prop_decrease=float(strength), n_fft=2048, hop_length=512) # Added n_fft and hop_length
            reduced_channels_data.append(reduced_channel)
        
        interleaved_samples_float = np.zeros_like(samples, dtype=np.float32) 
        for i, channel_data in enumerate(reduced_channels_data):
            interleaved_samples_float[i::num_channels] = channel_data
        
        # Convert back to original integer type if necessary
        if np.issubdtype(samples_original_dtype, np.integer):
            if audio_segment.sample_width == 2:
                final_int_samples = (interleaved_samples_float * 32767).astype(np.int16)
            elif audio_segment.sample_width == 4:
                final_int_samples = (interleaved_samples_float * 2147483647).astype(np.int32)
            elif audio_segment.sample_width == 1:
                final_int_samples = ((interleaved_samples_float * 127) + 128).astype(np.uint8) # Assuming unsigned 8-bit
            else: # Fallback to int16 if unknown original int type
                final_int_samples = (interleaved_samples_float * 32767).astype(np.int16)
            sample_width_out = audio_segment.sample_width
        else: # If original was float, keep it float (though pydub might convert later)
            # For direct AudioSegment creation from float numpy, it's better to convert to int16 for pydub
            final_int_samples = (interleaved_samples_float * 32767).astype(np.int16)
            sample_width_out = 2


        return AudioSegment(
            final_int_samples.tobytes(), 
            frame_rate=sample_rate, 
            sample_width=sample_width_out, 
            channels=num_channels
        )
    else: # Mono
        contiguous_samples = np.ascontiguousarray(samples)
        reduced_noise_samples_float = noisereduce.reduce_noise(y=contiguous_samples, sr=sample_rate, prop_decrease=float(strength), n_fft=2048, hop_length=512)

        if np.issubdtype(samples_original_dtype, np.integer):
            if audio_segment.sample_width == 2:
                final_int_samples = (reduced_noise_samples_float * 32767).astype(np.int16)
            elif audio_segment.sample_width == 4:
                final_int_samples = (reduced_noise_samples_float * 2147483647).astype(np.int32)
            elif audio_segment.sample_width == 1:
                final_int_samples = ((reduced_noise_samples_float * 127) + 128).astype(np.uint8)
            else:
                final_int_samples = (reduced_noise_samples_float * 32767).astype(np.int16)
            sample_width_out = audio_segment.sample_width
        else:
            final_int_samples = (reduced_noise_samples_float * 32767).astype(np.int16)
            sample_width_out = 2
            
        return AudioSegment(
            final_int_samples.tobytes(), 
            frame_rate=sample_rate, 
            sample_width=sample_width_out, 
            channels=1
        )

def _apply_high_pass_filter(audio_segment, cutoff_hz=DEFAULT_HPF_CUTOFF_HZ):
    logger.info(f"Applying high-pass filter with cutoff {cutoff_hz} Hz.")
    if not isinstance(cutoff_hz, (int, float)) or cutoff_hz <= 0:
        logger.warning(f"Invalid high-pass cutoff: {cutoff_hz}. Must be positive. Using default.")
        cutoff_hz = DEFAULT_HPF_CUTOFF_HZ
    if cutoff_hz >= audio_segment.frame_rate / 2:
        logger.warning(f"High-pass cutoff {int(cutoff_hz)}Hz is too high for sample rate {audio_segment.frame_rate}Hz. Skipping filter.")
        return audio_segment
    return pydub_high_pass(audio_segment, int(cutoff_hz))

def _apply_silence_trimming(audio_segment, 
                            min_silence_ms=DEFAULT_TRIM_MIN_SILENCE_MS, 
                            insert_silence_ms=DEFAULT_TRIM_INSERT_SILENCE_MS,
                            chunk_min_duration_ms=DEFAULT_TRIM_CHUNK_MIN_DURATION_MS,
                            silence_thresh_db=DEFAULT_SILENCE_THRESH_DB):
    logger.info(f"Applying silence trimming: min_silence_to_trim={min_silence_ms}ms, "
                f"insert_silence={insert_silence_ms}ms, min_chunk_duration={chunk_min_duration_ms}ms, "
                f"silence_thresh={silence_thresh_db}dB")

    min_silence_ms = int(min_silence_ms if isinstance(min_silence_ms, (int, float)) and min_silence_ms >= 0 else DEFAULT_TRIM_MIN_SILENCE_MS)
    insert_silence_ms = int(insert_silence_ms if isinstance(insert_silence_ms, (int, float)) and insert_silence_ms >= 0 else DEFAULT_TRIM_INSERT_SILENCE_MS)
    chunk_min_duration_ms = int(chunk_min_duration_ms if isinstance(chunk_min_duration_ms, (int, float)) and chunk_min_duration_ms >= 0 else DEFAULT_TRIM_CHUNK_MIN_DURATION_MS)
    silence_thresh_db = int(silence_thresh_db if isinstance(silence_thresh_db, (int, float)) else DEFAULT_SILENCE_THRESH_DB)

    nonsilent_parts = detect_nonsilent(
        audio_segment,
        min_silence_len=min_silence_ms, 
        silence_thresh=silence_thresh_db,
        seek_step=25 
    )

    if not nonsilent_parts:
        logger.warning("Silence trimming: No non-silent parts detected. Outputting standard inserted silence.")
        return AudioSegment.silent(duration=insert_silence_ms, frame_rate=audio_segment.frame_rate)

    logger.info(f"Silence trimming: Found {len(nonsilent_parts)} potential non-silent parts.")
    
    processed_chunks = []
    for i, (start_ms, end_ms) in enumerate(nonsilent_parts):
        chunk = audio_segment[start_ms:end_ms]
        if len(chunk) >= chunk_min_duration_ms:
            processed_chunks.append(chunk)
            logger.info(f"  Keeping chunk {i+1}: {len(chunk)/1000.0:.2f}s")
        else:
            logger.info(f"  Discarding small chunk {i+1}: {len(chunk)/1000.0:.2f}s")
    
    if not processed_chunks:
        logger.warning("Silence trimming: All detected chunks were below minimum duration. Outputting standard inserted silence.")
        return AudioSegment.silent(duration=insert_silence_ms, frame_rate=audio_segment.frame_rate)

    standard_silence = AudioSegment.silent(duration=insert_silence_ms, frame_rate=audio_segment.frame_rate)
    
    final_audio = standard_silence 
    for i, chunk in enumerate(processed_chunks):
        final_audio += chunk
        if i < len(processed_chunks) - 1: 
            final_audio += standard_silence
    
    logger.info("Silence trimming: Audio reconstructed with standardized silences.")
    return final_audio

# --- Main Cleanup Processing Function ---
def cleanup_audio_core(
    input_path, 
    output_path, 
    output_format="wav",
    cleanup_options=None, 
    task_update_meta_func=None
    ):
    if cleanup_options is None: cleanup_options = {}
    
    try:
        logger.info(f"Audio cleanup task started. Input='{input_path}', Output='{output_path}', Options={cleanup_options}")
        if task_update_meta_func: task_update_meta_func(state='PROGRESS', meta={'status': 'Loading audio...', 'progress': 5})

        audio = AudioSegment.from_file(input_path)
        logger.info(f"Loaded audio: Duration={len(audio)/1000.0:.2f}s, Channels={audio.channels}, SR={audio.frame_rate}Hz, SampleWidth={audio.sample_width}")

        current_progress = 10
        active_steps = sum(1 for option_key in ['noise_reduce', 'high_pass', 'normalize', 'trim_silence'] if cleanup_options.get(option_key, {}).get('enabled'))
        progress_increment = (80 - current_progress) / active_steps if active_steps > 0 else 0


        if cleanup_options.get('noise_reduce', {}).get('enabled'):
            if task_update_meta_func: task_update_meta_func(state='PROGRESS', meta={'status': 'Applying Noise Reduction...', 'progress': int(current_progress)})
            strength = cleanup_options['noise_reduce'].get('strength', DEFAULT_NOISE_REDUCTION_STRENGTH)
            audio = _apply_noise_reduction(audio, strength)
            current_progress += progress_increment
            logger.info("Noise reduction applied.")

        if cleanup_options.get('high_pass', {}).get('enabled'):
            if task_update_meta_func: task_update_meta_func(state='PROGRESS', meta={'status': 'Applying High-Pass Filter...', 'progress': int(current_progress)})
            cutoff_hz = cleanup_options['high_pass'].get('cutoff_hz', DEFAULT_HPF_CUTOFF_HZ)
            audio = _apply_high_pass_filter(audio, cutoff_hz)
            current_progress += progress_increment
            logger.info("High-pass filter applied.")

        if cleanup_options.get('normalize', {}).get('enabled'):
            if task_update_meta_func: task_update_meta_func(state='PROGRESS', meta={'status': 'Normalizing Volume...', 'progress': int(current_progress)})
            target_dbfs = cleanup_options['normalize'].get('target_dbfs', DEFAULT_NORMALIZATION_TARGET_DBFS)
            audio = _apply_normalization(audio, target_dbfs)
            current_progress += progress_increment
            logger.info("Normalization applied.")

        if cleanup_options.get('trim_silence', {}).get('enabled'):
            if task_update_meta_func: task_update_meta_func(state='PROGRESS', meta={'status': 'Trimming Silences...', 'progress': int(current_progress)})
            params = cleanup_options['trim_silence']
            audio = _apply_silence_trimming(
                audio,
                min_silence_ms=params.get('min_silence_ms', DEFAULT_TRIM_MIN_SILENCE_MS),
                insert_silence_ms=params.get('insert_ms', DEFAULT_TRIM_INSERT_SILENCE_MS),
                chunk_min_duration_ms=params.get('chunk_min_duration_ms', DEFAULT_TRIM_CHUNK_MIN_DURATION_MS),
                silence_thresh_db=params.get('silence_thresh_db', DEFAULT_SILENCE_THRESH_DB)
            )
            # current_progress += progress_increment # Already accounted for if active_steps was calculated correctly
            logger.info("Silence trimming applied.")
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        logger.info(f"Exporting cleaned audio to '{output_path}' as '{output_format}'...")
        if task_update_meta_func: task_update_meta_func(state='PROGRESS', meta={'status': 'Exporting file...', 'progress': 90})
        
        export_params = {"format": "wav"}
        if output_format.lower() == "mp3": export_params = {"format": "mp3", "bitrate": "192k"}
        elif output_format.lower() == "m4a": export_params = {"format": "ipod"}
        audio.export(output_path, **export_params)
        
        logger.info("Audio cleanup processing complete.")
        if task_update_meta_func: task_update_meta_func(state='SUCCESS', meta={'status': 'Audio cleaned successfully!', 'progress': 100, 'result_filename': os.path.basename(output_path)})
        return True, os.path.basename(output_path)

    except Exception as e:
        logger.error(f"Error in cleanup_audio_core for '{input_path}': {e}", exc_info=True)
        if task_update_meta_func: task_update_meta_func(state='FAILURE', meta={'status': f'Error during cleanup: {str(e)}', 'progress': 0})
        if os.path.exists(output_path):
            try: os.remove(output_path)
            except OSError as oe: logger.error(f"Could not remove partial output '{output_path}': {oe}")
        return False, str(e)
    finally: pass
