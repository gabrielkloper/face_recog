import os
import pickle
import numpy as np # Assuming encodings might be numpy arrays
from flask import current_app, flash

# --- Placeholder Face Encoding Utilities ---
# These will be replaced with actual logic from the user's face_recognition branch/code.

def generate_face_encoding(photo_file_path):
    """
    Placeholder for generating a face encoding from a photo.
    Takes the absolute path to a photo file.
    Returns a face encoding object (e.g., a numpy array or list of floats).
    Returns None if no face is found or an error occurs.
    """
    current_app.logger.info(f"Attempting to generate dummy encoding for: {photo_file_path}")
    if not os.path.exists(photo_file_path):
        current_app.logger.error(f"Photo file not found for encoding: {photo_file_path}")
        return None

    # Simulate encoding generation (e.g., could be a 128-dimension vector)
    # In a real scenario, this would involve:
    # 1. Loading the image (e.g., with face_recognition.load_image_file)
    # 2. Finding face locations (e.g., with face_recognition.face_locations)
    # 3. Generating encodings (e.g., with face_recognition.face_encodings)
    # For this placeholder, we'll just return a dummy numpy array.
    # This assumes only one face per registration photo for simplicity.
    try:
        # Simulate some processing that might fail if image is invalid
        with open(photo_file_path, 'rb') as f:
            f.read(10) # Try to read a few bytes

        dummy_encoding = np.random.rand(128).tolist() # Example: 128-dim vector as a list
        current_app.logger.info(f"Successfully generated dummy encoding for: {photo_file_path}")
        return dummy_encoding
    except Exception as e:
        current_app.logger.error(f"Dummy encoding generation failed for {photo_file_path}: {e}")
        return None

def save_encoding_to_file(encoding, person_id_system):
    """
    Saves the face encoding to a file (e.g., using pickle).
    The filename is derived from person_id_system.
    Returns the filename (not the full path) of the saved encoding file, or None on failure.
    """
    if encoding is None:
        return None

    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], '../face_encodings') # Relative to photo uploads
    if not os.path.exists(upload_folder):
        try:
            os.makedirs(upload_folder)
        except OSError as e:
            current_app.logger.error(f"Could not create encoding folder {upload_folder}: {e}")
            return None

    filename = f"{person_id_system}_encoding.pkl"
    filepath = os.path.join(upload_folder, filename)

    try:
        with open(filepath, 'wb') as f:
            pickle.dump(encoding, f)
        current_app.logger.info(f"Saved encoding to: {filepath}")
        return filename # Return just the filename, similar to photo_path
    except Exception as e:
        current_app.logger.error(f"Error saving encoding file {filepath}: {e}")
        return None

def delete_encoding_file(encoding_filename):
    """
    Deletes an encoding file.
    `encoding_filename` is just the name of the file, not the full path.
    """
    if not encoding_filename:
        return False

    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], '../face_encodings')
    filepath = os.path.join(upload_folder, encoding_filename)

    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            current_app.logger.info(f"Deleted encoding file: {filepath}")
            return True
    except Exception as e:
        current_app.logger.error(f"Error deleting encoding file {filepath}: {e}")
    return False

def get_photo_full_path(photo_filename):
    """Helper to get the full system path to a photo."""
    if not photo_filename:
        return None
    return os.path.join(current_app.config['UPLOAD_FOLDER'], photo_filename)

# --- End Placeholder ---
