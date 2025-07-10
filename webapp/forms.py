from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed # For file uploads
from wtforms import StringField, PasswordField, SubmitField, BooleanField, TextAreaField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError, Optional
from .models import User, RegisteredPerson
from flask import current_app # To access app.config for ALLOWED_EXTENSIONS

class AddUserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=80)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    is_admin = BooleanField('Is Admin?') # For now, simple admin flag
    submit = SubmitField('Add User')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username is already taken. Please choose a different one.')

class EditUserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=80)])
    # Password fields are optional for editing.
    # Optional() allows the field to be empty. If it's not empty, other validators (Length) apply.
    # EqualTo should also be conditional or handle empty fields gracefully if one is empty and other is not.
    # For simplicity, if password is provided, confirm_password should also be provided and match.
    # This is typically handled by ensuring EqualTo works correctly with Optional,
    # or by adding custom validation logic if needed.
    # WTForms EqualTo validator works fine with Optional: if 'password' is empty, 'confirm_password' must also be empty (or also have Optional).
    password = PasswordField('New Password (leave blank to keep current)',
                             validators=[Optional(), Length(min=6), EqualTo('confirm_password', message='New passwords must match.')])
    confirm_password = PasswordField('Confirm New Password', validators=[Optional()])
    is_admin = BooleanField('Is Admin?')
    submit = SubmitField('Update User')

    def __init__(self, original_username, *args, **kwargs):
        super(EditUserForm, self).__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username):
        if username.data != self.original_username:
            user = User.query.filter_by(username=username.data).first()
            if user:
                raise ValidationError('That username is already taken. Please choose a different one.')

# --- Forms for Face Registration (RegisteredPerson model) ---

class RegisterPersonForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(max=100)])
    person_id_system = StringField('System ID (Unique)', validators=[DataRequired(), Length(max=50)])
    photo = FileField('Upload Photo', validators=[
        DataRequired(message="A photo is required."), # Make photo required for new registration
        FileAllowed(current_app.config['ALLOWED_EXTENSIONS'], 'Only image files (png, jpg, jpeg) are allowed!')
    ])
    other_data = TextAreaField('Other Information (Optional)', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Register Person')

    def validate_person_id_system(self, person_id_system):
        person = RegisteredPerson.query.filter_by(person_id_system=person_id_system.data).first()
        if person:
            raise ValidationError('That System ID is already registered. Please choose a different one.')

class EditPersonForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(max=100)])
    person_id_system = StringField('System ID (Unique)', validators=[DataRequired(), Length(max=50)])
    photo = FileField('Upload New Photo (Optional - leave blank to keep current)', validators=[
        Optional(), # Photo is optional during edit
        FileAllowed(current_app.config['ALLOWED_EXTENSIONS'], 'Only image files (png, jpg, jpeg) are allowed!')
    ])
    other_data = TextAreaField('Other Information (Optional)', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Update Person')

    def __init__(self, original_person_id_system, *args, **kwargs):
        super(EditPersonForm, self).__init__(*args, **kwargs)
        self.original_person_id_system = original_person_id_system

    def validate_person_id_system(self, person_id_system):
        if person_id_system.data != self.original_person_id_system:
            person = RegisteredPerson.query.filter_by(person_id_system=person_id_system.data).first()
            if person:
                raise ValidationError('That System ID is already registered. Please choose a different one.')
