import os
import pickle
import numpy as np
from flask import current_app, flash
import face_recognition # For actual face encoding

# --- Face Encoding Utilities ---

def generate_face_encoding(photo_file_path):
    """
    Generates a face encoding from a photo using the face_recognition library.
    Takes the absolute path to a photo file.
    Returns a face encoding object (numpy array), or None if no face is found or an error occurs.
    """
    current_app.logger.info(f"Attempting to generate real encoding for: {photo_file_path}")
    if not os.path.exists(photo_file_path):
        current_app.logger.error(f"Photo file not found for encoding: {photo_file_path}")
        return None

    try:
        # Load the image file
        image = face_recognition.load_image_file(photo_file_path)

        # Generate face encodings.
        # This function finds face locations first (defaulting to HOG model)
        # and then computes encodings.
        # For registration, we typically expect one face.
        # face_recognition.face_encodings returns a list of numpy arrays.
        face_encodings_list = face_recognition.face_encodings(image)

        if face_encodings_list:
            # Take the first encoding found.
            encoding = face_encodings_list[0]
            current_app.logger.info(f"Successfully generated real encoding for: {photo_file_path}")
            return encoding # This is a numpy array
        else:
            current_app.logger.warning(f"No faces found in {photo_file_path}.")
            return None

    except Exception as e:
        current_app.logger.error(f"Error processing {photo_file_path} for real encoding: {e}")
        return None

def save_encoding_to_file(encoding, person_id_system):
    """
    Saves the face encoding (numpy array) to a .pkl file.
    The filename is derived from person_id_system.
    Returns the filename of the saved encoding file, or None on failure.
    """
    if encoding is None: # Check if encoding is None (e.g. no face found)
        current_app.logger.warning(f"Attempted to save None encoding for {person_id_system}.")
        return None

    # Construct path within webapp/static/uploads/face_encodings/
    # current_app.config['UPLOAD_FOLDER'] is 'webapp/static/uploads/registered_photos'
    encodings_dir = os.path.abspath(os.path.join(current_app.config['UPLOAD_FOLDER'], '..', 'face_encodings'))

    if not os.path.exists(encodings_dir):
        try:
            os.makedirs(encodings_dir)
            current_app.logger.info(f"Created encodings directory: {encodings_dir}")
        except OSError as e:
            current_app.logger.error(f"Could not create encoding folder {encodings_dir}: {e}")
            return None

    filename = f"{person_id_system}_encoding.pkl"
    filepath = os.path.join(encodings_dir, filename)

    try:
        with open(filepath, 'wb') as f:
            pickle.dump(encoding, f) # Save the numpy array directly
        current_app.logger.info(f"Saved encoding to: {filepath}")
        return filename
    except Exception as e:
        current_app.logger.error(f"Error saving encoding file {filepath}: {e}")
        return None

def delete_encoding_file(encoding_filename):
    """
    Deletes an encoding file.
    `encoding_filename` is just the name of the file.
    """
    if not encoding_filename:
        return False

    encodings_dir = os.path.abspath(os.path.join(current_app.config['UPLOAD_FOLDER'], '..', 'face_encodings'))
    filepath = os.path.join(encodings_dir, encoding_filename)

    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            current_app.logger.info(f"Deleted encoding file: {filepath}")
            return True
        else:
            current_app.logger.warning(f"Attempted to delete non-existent encoding file: {filepath}")
            # Not necessarily an error if we try to delete something that was never created or already deleted.
            return False
    except Exception as e:
        current_app.logger.error(f"Error deleting encoding file {filepath}: {e}")
    return False

def get_photo_full_path(photo_filename):
    """Helper to get the full system path to a photo in the UPLOAD_FOLDER."""
    if not photo_filename:
        return None
    # current_app.config['UPLOAD_FOLDER'] should be an absolute path already set up in __init__.py
    return os.path.join(current_app.config['UPLOAD_FOLDER'], photo_filename)
