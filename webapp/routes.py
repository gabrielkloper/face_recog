from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from .models import User, RegisteredPerson, AccessLog, get_utc_now, sao_paulo_tz
from . import db
from .forms import AddUserForm, EditUserForm, RegisterPersonForm, EditPersonForm
from .face_utils import generate_face_encoding, save_encoding_to_file, delete_encoding_file, get_photo_full_path
from datetime import datetime, timedelta, date
import pytz
import io
import csv
from flask import Response

main_bp = Blueprint('main', __name__)


# --- Helper for file uploads ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def save_photo(photo_file, person_id_system):
    if photo_file and allowed_file(photo_file.filename):
        filename = secure_filename(f"{person_id_system}_{photo_file.filename}")
        # Use app.config['UPLOAD_FOLDER'] which is an absolute path
        upload_folder = current_app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        photo_path = os.path.join(upload_folder, filename)
        photo_file.save(photo_path)
        # Return the filename part to be stored in DB, as static folder path is known
        return filename
    return None

def delete_photo_file(filename_to_delete):
    if filename_to_delete:
        try:
            upload_folder = current_app.config['UPLOAD_FOLDER']
            file_path = os.path.join(upload_folder, filename_to_delete)
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
        except Exception as e:
            flash(f"Error deleting photo file: {e}", "danger") # Or log this
    return False

# --- Authentication Routes ---
@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    # Using request.form directly here, not a FlaskForm, so no CSRF token from form object
    # However, the overall app has CSRF protection via CSRFProtect.
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.index'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html', title='Login')

@main_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.login'))

# --- Main Application Routes ---
@main_bp.route('/')
@main_bp.route('/index')
@login_required
def index():
    return render_template('index.html', title='Main Page')

# --- User Management CRUD ---
@main_bp.route('/manage_users')
@login_required
def manage_users():
    form = AddUserForm() # For rendering the add user form
    users = User.query.order_by(User.username).all()
    return render_template('manage_users.html', title='Manage Users', users=users, form=form)

@main_bp.route('/add_user', methods=['POST'])
@login_required
def add_user():
    form = AddUserForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        new_user = User(username=form.username.data,
                        password_hash=hashed_password,
                        is_admin=form.is_admin.data)
        db.session.add(new_user)
        db.session.commit()
        flash(f'User {form.username.data} created successfully!', 'success')
        return redirect(url_for('main.manage_users'))
    else:
        # If form validation fails, redirect back to manage_users and let it render errors
        # For better UX, could store errors in session/flash and re-render form fields with values
        # For now, just flash a generic error and rely on the form object passed to manage_users template
        users = User.query.order_by(User.username).all()
        flash('Error creating user. Please check the form.', 'danger')
        # Re-render manage_users with the form object containing errors
        return render_template('manage_users.html', title='Manage Users', users=users, form=form)


@main_bp.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    user_to_edit = User.query.get_or_404(user_id)
    form = EditUserForm(original_username=user_to_edit.username)

    if form.validate_on_submit():
        user_to_edit.username = form.username.data
        if form.password.data: # If a new password was entered
            user_to_edit.password_hash = generate_password_hash(form.password.data, method='pbkdf2:sha256')

        # Prevent user from removing their own admin status
        if user_to_edit.id == current_user.id and not form.is_admin.data:
            flash('You cannot remove your own admin status.', 'warning')
        else:
            user_to_edit.is_admin = form.is_admin.data

        db.session.commit()
        flash(f'User {user_to_edit.username} updated successfully!', 'success')
        return redirect(url_for('main.manage_users'))
    elif request.method == 'GET':
        form.username.data = user_to_edit.username
        form.is_admin.data = user_to_edit.is_admin
        # Password field is left blank intentionally for security

    return render_template('edit_user.html', title=f'Edit User {user_to_edit.username}',
                           form=form, user_to_edit=user_to_edit)

@main_bp.route('/delete_user/<int:user_id>', methods=['POST']) # Should be POST for safety
@login_required
def delete_user(user_id):
    user_to_delete = User.query.get_or_404(user_id)
    if user_to_delete.id == current_user.id:
        flash('You cannot delete yourself.', 'danger')
        return redirect(url_for('main.manage_users'))

    # Consider what happens to content created by this user if applicable
    # For now, direct deletion:
    db.session.delete(user_to_delete)
    db.session.commit()
    flash(f'User {user_to_delete.username} deleted successfully.', 'success')
    return redirect(url_for('main.manage_users'))


# --- Face Management (CRUD) ---
@main_bp.route('/manage_faces')
@login_required
def manage_faces():
    form = RegisterPersonForm()
    people_query = RegisteredPerson.query.order_by(RegisteredPerson.name).all()

    people_display = []
    for person in people_query:
        created_at_sp_str = "N/A"
        if person.created_at:
            created_at_sp_str = person.created_at.replace(tzinfo=pytz.utc).astimezone(sao_paulo_tz).strftime('%Y-%m-%d %H:%M')

        people_display.append({
            'id': person.id,
            'name': person.name,
            'photo_path': person.photo_path,
            'person_id_system': person.person_id_system,
            'other_data': person.other_data,
            'face_encoding_path': person.face_encoding_path,
            'created_at_sp_str': created_at_sp_str
        })

    return render_template('manage_faces.html', title='Manage Faces',
                           people=people_display, form=form)

@main_bp.route('/add_person', methods=['POST'])
@login_required
def add_person():
    form = RegisterPersonForm()
    if form.validate_on_submit():
        photo_filename = None
        photo_filename = None
        encoding_filename = None
        if form.photo.data:
            photo_filename = save_photo(form.photo.data, form.person_id_system.data)
            if not photo_filename:
                flash('Invalid photo file or type. Could not save photo.', 'danger')
                registered_people = RegisteredPerson.query.order_by(RegisteredPerson.name).all()
                return render_template('manage_faces.html', title='Manage Faces', people=registered_people, form=form)

            # Generate and save encoding
            full_photo_path = get_photo_full_path(photo_filename)
            face_encoding = generate_face_encoding(full_photo_path)
            if face_encoding is not None:
                encoding_filename = save_encoding_to_file(face_encoding, form.person_id_system.data)
                if not encoding_filename:
                    # Failed to save encoding, but photo is saved. Decide on handling.
                    # For now, flash a warning. Could delete photo or proceed without encoding.
                    flash('Photo saved, but failed to generate or save face encoding. Please try editing the person to re-generate.', 'warning')
            else:
                flash('Photo saved, but no face found or error during encoding generation. Please try a different photo or edit later.', 'warning')

        new_person = RegisteredPerson(
            name=form.name.data,
            person_id_system=form.person_id_system.data,
            photo_path=photo_filename,
            face_encoding_path=encoding_filename, # Store encoding filename
            other_data=form.other_data.data
        )
        db.session.add(new_person)
        db.session.commit()
        flash(f'Person {form.name.data} registered successfully! Encoding status: {"Generated" if encoding_filename else "Not generated/Error"}.', 'success')
        return redirect(url_for('main.manage_faces'))
    else:
        registered_people = RegisteredPerson.query.order_by(RegisteredPerson.name).all()
        flash('Error registering person. Please check the form.', 'danger')
        return render_template('manage_faces.html', title='Manage Faces',
                               people=registered_people, form=form)


@main_bp.route('/edit_person/<int:person_id>', methods=['GET', 'POST'])
@login_required
def edit_person(person_id):
    person_to_edit = RegisteredPerson.query.get_or_404(person_id)
    form = EditPersonForm(original_person_id_system=person_to_edit.person_id_system)

    if form.validate_on_submit():
        old_photo_filename = person_to_edit.photo_path
        old_encoding_filename = person_to_edit.face_encoding_path
        new_person_id_system = form.person_id_system.data # Get new system ID from form

        # Handle photo update
        if form.photo.data: # If a new photo is uploaded
            # Save new photo
            new_photo_filename = save_photo(form.photo.data, new_person_id_system) # Use new system ID for new photo name
            if new_photo_filename:
                # Delete old photo and old encoding
                if old_photo_filename:
                    delete_photo_file(old_photo_filename)
                if old_encoding_filename:
                    delete_encoding_file(old_encoding_filename)

                person_to_edit.photo_path = new_photo_filename

                # Generate and save new encoding for the new photo
                full_new_photo_path = get_photo_full_path(new_photo_filename)
                new_face_encoding = generate_face_encoding(full_new_photo_path)
                if new_face_encoding is not None:
                    new_encoding_filename = save_encoding_to_file(new_face_encoding, new_person_id_system)
                    person_to_edit.face_encoding_path = new_encoding_filename
                    if not new_encoding_filename:
                        flash('New photo uploaded, but failed to save new face encoding.', 'warning')
                else:
                    person_to_edit.face_encoding_path = None # No encoding if face not found in new photo
                    flash('New photo uploaded, but no face found or error during encoding.', 'warning')
            else:
                flash('Invalid new photo file or type. Photo not updated.', 'warning')
        elif person_to_edit.person_id_system != new_person_id_system:
            # Photo not changed, but system ID changed. Rename existing photo and encoding if they exist.
            if old_photo_filename:
                # Rename photo file
                renamed_photo_filename = save_photo(get_photo_full_path(old_photo_filename), new_person_id_system) # This is a bit of a hack with save_photo
                                                                                                                    # A dedicated rename function would be better.
                                                                                                                    # For now, assuming save_photo can handle this by re-saving with new name.
                                                                                                                    # This needs careful implementation of save_photo or a new rename_file utility.
                                                                                                                    # Let's simplify: if ID changes, and photo doesn't, user might need to re-upload for encoding name consistency.
                                                                                                                    # Or, we just update the DB path, and the filename itself doesn't change.
                                                                                                                    # For now, let's not rename files automatically if only ID changes and not photo to avoid complexity.
                                                                                                                    # The encoding filename is tied to person_id_system.
                pass # Current save_photo will save with new name, but we'd need to provide file object.
                     # This path needs more robust file management for renaming.
                     # For now, if ID changes, existing photo/encoding filenames DON'T change. This is simpler.
                     # The consequence is that photo/encoding filenames might not match the new person_id_system.

            if old_encoding_filename:
                # If system ID changed, the encoding filename should ideally change too.
                # Similar to photo, this requires renaming the encoding file.
                # If we don't rename, the old encoding filename (based on old ID) is kept.
                # This is simpler for now.
                pass


        person_to_edit.name = form.name.data
        person_to_edit.person_id_system = new_person_id_system # Update system ID
        person_to_edit.other_data = form.other_data.data

        db.session.commit()
        flash(f'Details for {person_to_edit.name} updated successfully!', 'success')
        return redirect(url_for('main.manage_faces'))
    elif request.method == 'GET':
        form.name.data = person_to_edit.name
        form.person_id_system.data = person_to_edit.person_id_system
        form.other_data.data = person_to_edit.other_data
        # Photo field is left blank by default in the form

    return render_template('edit_person.html', title=f'Edit {person_to_edit.name}',
                           form=form, person_to_edit=person_to_edit)


@main_bp.route('/delete_person/<int:person_id>', methods=['POST'])
@login_required
def delete_person(person_id):
    person_to_delete = RegisteredPerson.query.get_or_404(person_id)
    photo_filename_to_delete = person_to_delete.photo_path
    encoding_filename_to_delete = person_to_delete.face_encoding_path

    # Future: Check for related AccessLog entries and decide on handling (e.g., anonymize, cascade delete, or prevent).
    # For now, we will delete the person and their logs if foreign key is set to cascade.
    # If not, logs will remain with a person_id that no longer exists in RegisteredPerson (orphaned).
    # Current model: `access_logs = db.relationship('AccessLog', backref='person', lazy=True)` - default is no cascade on delete for parent.
    # If we want to delete logs: access_logs = db.relationship('AccessLog', backref='person', lazy=True, cascade="all, delete-orphan")
    # For now, let's assume we want to keep logs but they might refer to a deleted person.
    # Or, we can delete logs associated with this person:
    AccessLog.query.filter_by(person_id=person_id).delete()
    # This should be done before deleting the person if there's a FK constraint.

    db.session.delete(person_to_delete)
    db.session.commit() # Commit deletion from DB first

    if photo_filename_to_delete:
        delete_photo_file(photo_filename_to_delete)
    if encoding_filename_to_delete:
        delete_encoding_file(encoding_filename_to_delete)

    flash(f'Person {person_to_delete.name}, their photo, encoding, and access logs have been deleted.', 'success')
    return redirect(url_for('main.manage_faces'))


# --- Entry/Exit Tracking ---
@main_bp.route('/track_entries')
@login_required
def track_entries():
    sao_paulo_tz = pytz.timezone('America/Sao_Paulo')
    today_sp = datetime.now(sao_paulo_tz).date()

    # For now, let's fetch all logs. We'll add filtering later.
    raw_logs = AccessLog.query.order_by(AccessLog.timestamp.desc()).all()

    # Structure logs for display: group by person and day for entry/exit pairs
    # This is a simplified approach; a more robust solution would handle missing entries/exits

    processed_entries = {} # {(person_id, date_obj): {'name': name, 'entry': time, 'exit': time, 'duration': duration}}

    # Sort logs by person and then by time to correctly pair entry/exit
    # log.timestamp from DB is naive but represents UTC
    sorted_logs = sorted(raw_logs, key=lambda log: (log.person_id, log.timestamp))

    temp_entries = {} # {person_id: entry_log}

    for log in sorted_logs:
        # Make the naive UTC timestamp aware, then convert to Sao Paulo time
        log_timestamp_utc_aware = log.timestamp.replace(tzinfo=pytz.utc)
        log_time_sp = log_timestamp_utc_aware.astimezone(sao_paulo_tz)
        log_date_sp = log_time_sp.date()

        key = (log.person_id, log_date_sp)

        if log.event_type == 'entry':
            if key not in processed_entries or processed_entries[key].get('entry') is None: # Prioritize first entry of the day
                 processed_entries.setdefault(key, {'name': log.person_name, 'entry_obj': log.timestamp})
                 processed_entries[key]['entry'] = log_time_sp.strftime('%H:%M:%S')
            temp_entries[log.person_id] = log # Store last entry event to match with exit

        elif log.event_type == 'exit':
            # Match with the most recent entry for that person on the same day or if no entry for that day, it's just an exit
            if key in processed_entries and 'entry_obj' in processed_entries[key]:
                entry_log_timestamp = processed_entries[key]['entry_obj']
                # Ensure exit is after entry
                if log.timestamp > entry_log_timestamp:
                    # Only update if this exit is later than any existing exit for this entry
                    if processed_entries[key].get('exit_obj') is None or log.timestamp > processed_entries[key].get('exit_obj'):
                        processed_entries[key]['exit'] = log_time_sp.strftime('%H:%M:%S')
                        processed_entries[key]['exit_obj'] = log.timestamp

                        duration_delta = processed_entries[key]['exit_obj'] - processed_entries[key]['entry_obj']

                        hours, remainder = divmod(duration_delta.total_seconds(), 3600)
                        minutes, seconds = divmod(remainder, 60)
                        processed_entries[key]['duration'] = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
            # If there's no matching entry for the exit on that day in processed_entries, we can log it as an exit-only event if needed
            # For now, we are focusing on paired entry/exit for duration.

    # Convert processed_entries dict to a list of dicts for easier template rendering, sorted by date and then entry time
    display_logs = []
    for key_tuple, data in processed_entries.items():
        log_date_sp = key_tuple[1] # date object
        display_logs.append({
            'date': log_date_sp.strftime('%Y-%m-%d'),
            'name': data.get('name'),
            'entry': data.get('entry'),
            'exit': data.get('exit'),
            'duration': data.get('duration', 'N/A')
        })

    # Sort: newest date first, then by name
    display_logs.sort(key=lambda x: (datetime.strptime(x['date'], '%Y-%m-%d'), x['name'] if x['name'] else ""), reverse=True)

    return render_template('track_entries.html', title='Track Entries/Exits', logs=display_logs, today_date=datetime.now(sao_paulo_tz).strftime('%Y-%m-%d'))


@main_bp.route('/export_tracking_logs_csv', methods=['GET'])
@login_required
def export_tracking_logs_csv():
    export_date_str = request.args.get('date')
    if not export_date_str:
        flash("Please select a date for export.", "warning")
        return redirect(url_for('main.track_entries'))

    try:
        export_date = datetime.strptime(export_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash("Invalid date format. Please use YYYY-MM-DD.", "danger")
        return redirect(url_for('main.track_entries'))

    # Define the start and end of the day in UTC, from the perspective of Sao Paulo
    # Start of the day in SP
    start_of_day_sp_naive = datetime.combine(export_date, datetime.min.time())
    start_of_day_sp_aware = sao_paulo_tz.localize(start_of_day_sp_naive)
    start_of_day_utc = start_of_day_sp_aware.astimezone(pytz.utc)

    # End of the day in SP
    end_of_day_sp_naive = datetime.combine(export_date, datetime.max.time())
    end_of_day_sp_aware = sao_paulo_tz.localize(end_of_day_sp_naive)
    end_of_day_utc = end_of_day_sp_aware.astimezone(pytz.utc)

    logs_for_day = AccessLog.query.filter(
        AccessLog.timestamp >= start_of_day_utc,
        AccessLog.timestamp <= end_of_day_utc
    ).order_by(AccessLog.person_id, AccessLog.timestamp).all()

    if not logs_for_day:
        flash(f"No logs found for {export_date_str}.", "info")
        return redirect(url_for('main.track_entries'))

    # Process logs for CSV (similar to display logic but for a single day)
    processed_for_csv = {}
    for log in logs_for_day:
        # log.timestamp from DB is naive but represents UTC. Make aware then convert.
        log_timestamp_utc_aware = log.timestamp.replace(tzinfo=pytz.utc)
        log_time_sp = log_timestamp_utc_aware.astimezone(sao_paulo_tz)

        # Key for CSV processing is just person_id for that specific day
        key = log.person_id

        processed_for_csv.setdefault(key, {
            'name': log.person_name,
            'date': export_date_str, # Date is fixed for the export
            'entry_obj_utc': None, 'exit_obj_utc': None, # Store UTC datetime objects for duration
            'entry_sp_str': None, 'exit_sp_str': None, 'duration_str': 'N/A'
        })

        if log.event_type == 'entry':
            # If no entry recorded yet for this person, or this entry is earlier than stored one
            if processed_for_csv[key].get('entry_obj_utc') is None or log_timestamp_utc_aware < processed_for_csv[key]['entry_obj_utc']:
                processed_for_csv[key]['entry_obj_utc'] = log_timestamp_utc_aware # Store aware UTC
                processed_for_csv[key]['entry_sp_str'] = log_time_sp.strftime('%H:%M:%S')

        elif log.event_type == 'exit':
            # If no exit recorded yet, or this exit is later than stored one
            if processed_for_csv[key].get('exit_obj_utc') is None or log_timestamp_utc_aware > processed_for_csv[key]['exit_obj_utc']:
                processed_for_csv[key]['exit_obj_utc'] = log_timestamp_utc_aware # Store aware UTC
                processed_for_csv[key]['exit_sp_str'] = log_time_sp.strftime('%H:%M:%S')

    output_data = []
    for person_id, data in processed_for_csv.items():
        if data['entry_obj_utc'] and data['exit_obj_utc'] and data['exit_obj_utc'] > data['entry_obj_utc']:
            duration_delta = data['exit_obj_utc'] - data['entry_obj_utc'] # Difference of aware UTC times
            hours, remainder = divmod(duration_delta.total_seconds(), 3600)
            minutes, _ = divmod(remainder, 60)
            data['duration_str'] = f"{int(hours):02d}h{int(minutes):02d}m"
        elif data['entry_obj_utc'] and not data['exit_obj_utc']:
             data['duration_str'] = "Still in room?"

        output_data.append({
            'Date (Sao Paulo)': data['date'],
            'Person Name': data['name'],
            'Entry Time (Sao Paulo)': data['entry_sp_str'] if data['entry_sp_str'] else '---',
            'Exit Time (Sao Paulo)': data['exit_sp_str'] if data['exit_sp_str'] else '---',
            'Duration': data['duration_str']
        })

    output_data.sort(key=lambda x: x['Person Name'])

    # Generate CSV
    si = io.StringIO()
    fieldnames = ['Date (Sao Paulo)', 'Person Name', 'Entry Time (Sao Paulo)', 'Exit Time (Sao Paulo)', 'Duration']
    writer = csv.DictWriter(si, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(output_data)

    # filename includes the specific date
    csv_filename = f"entry_exit_logs_{export_date_str}.csv"

    response = Response(si.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename={csv_filename}'
    return response


# --- Helper route to add a default admin user if none exists ---
@main_bp.route('/init_admin')
def init_admin():
    if User.query.count() == 0:
        hashed_password = generate_password_hash('admin', method='pbkdf2:sha256')
        admin_user = User(username='admin', password_hash=hashed_password, is_admin=True)
        db.session.add(admin_user)
        db.session.commit()
        flash('Admin user created with username "admin" and password "admin". Please change this password!', 'success')
        return redirect(url_for('main.login'))
    else:
        flash('Admin user already exists or database is not empty.', 'info')
        return redirect(url_for('main.login'))

# Placeholder for adding dummy data for testing tracking page
@main_bp.route('/add_dummy_log_data')
@login_required
def add_dummy_log_data():
    # sao_paulo_tz is imported from models now
    # Ensure users exist or create them
    person1_name = "Alice Wonderland"
    person2_name = "Bob The Builder"

    person1 = RegisteredPerson.query.filter_by(name=person1_name).first()
    if not person1:
        person1 = RegisteredPerson(name=person1_name, person_id_system="ALICE001", photo_path="dummy.jpg")
        db.session.add(person1)

    person2 = RegisteredPerson.query.filter_by(name=person2_name).first()
    if not person2:
        person2 = RegisteredPerson(name=person2_name, person_id_system="BOB002", photo_path="dummy.jpg")
        db.session.add(person2)

    db.session.commit() # Commit persons to get their IDs

    # Clear existing logs to avoid duplicates if this is run multiple times
    # AccessLog.query.delete()
    # db.session.commit()

    # Helper to create SP time and convert to UTC for storage
    def sp_to_utc(sp_datetime_naive, sp_tz_obj):
        aware_sp_time = sp_tz_obj.localize(sp_datetime_naive)
        return aware_sp_time.astimezone(pytz.utc)

    now_sp_naive = datetime.now() # Naive local time, assume server runs in SP or this is desired reference for 'today'

    logs_to_add = [
        # Alice - Today
        AccessLog(person_id=person1.id, person_name=person1.name, timestamp=sp_to_utc(now_sp_naive.replace(hour=9, minute=0, second=0, microsecond=0), sao_paulo_tz), event_type='entry'),
        AccessLog(person_id=person1.id, person_name=person1.name, timestamp=sp_to_utc(now_sp_naive.replace(hour=12, minute=30, second=0, microsecond=0), sao_paulo_tz), event_type='exit'),
        AccessLog(person_id=person1.id, person_name=person1.name, timestamp=sp_to_utc(now_sp_naive.replace(hour=13, minute=30, second=0, microsecond=0), sao_paulo_tz), event_type='entry'),
        AccessLog(person_id=person1.id, person_name=person1.name, timestamp=sp_to_utc(now_sp_naive.replace(hour=17, minute=45, second=0, microsecond=0), sao_paulo_tz), event_type='exit'),

        # Bob - Today
        AccessLog(person_id=person2.id, person_name=person2.name, timestamp=sp_to_utc(now_sp_naive.replace(hour=8, minute=15, second=0, microsecond=0), sao_paulo_tz), event_type='entry'),
        AccessLog(person_id=person2.id, person_name=person2.name, timestamp=sp_to_utc(now_sp_naive.replace(hour=17, minute=5, second=0, microsecond=0), sao_paulo_tz), event_type='exit'),

        # Alice - Yesterday
        AccessLog(person_id=person1.id, person_name=person1.name, timestamp=sp_to_utc((now_sp_naive - timedelta(days=1)).replace(hour=9, minute=5, second=0, microsecond=0), sao_paulo_tz), event_type='entry'),
        AccessLog(person_id=person1.id, person_name=person1.name, timestamp=sp_to_utc((now_sp_naive - timedelta(days=1)).replace(hour=17, minute=30, second=0, microsecond=0), sao_paulo_tz), event_type='exit'),

        # Bob - Yesterday (entry only)
        AccessLog(person_id=person2.id, person_name=person2.name, timestamp=sp_to_utc((now_sp_naive - timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0), sao_paulo_tz), event_type='entry'),

        # Alice - Day before yesterday (exit only)
        AccessLog(person_id=person1.id, person_name=person1.name, timestamp=sp_to_utc((now_sp_naive - timedelta(days=2)).replace(hour=17, minute=0, second=0, microsecond=0), sao_paulo_tz), event_type='exit'),
    ]

    db.session.bulk_save_objects(logs_to_add)
    db.session.commit()
    flash('Dummy log data added.', 'success')
    return redirect(url_for('main.track_entries'))
