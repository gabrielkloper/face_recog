# This file makes the 'webapp' directory a Python package.
# We can also initialize extensions or the app factory here later if needed.
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
import os

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)

    # Configuration
    # It's good practice to use environment variables for sensitive data.
    # For now, we'll set a default secret key and database URI.
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'your_default_secret_key_for_csrf_too')
    # Flask-WTF uses SECRET_KEY for CSRF by default if WTF_CSRF_SECRET_KEY is not set
    # app.config['WTF_CSRF_SECRET_KEY'] = 'a_different_csrf_secret_key'

    # Define the path for the SQLite database
    # It will be created in the root directory of the project (outside webapp)
    # base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..')) # Project root
    # app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(base_dir, "site.db")}')

    # --- MySQL Configuration ---
    # IMPORTANT: Replace with your actual MySQL connection details.
    # You can use environment variables for security.
    # Example: mysql+mysqlclient://username:password@host:port/database_name
    MYSQL_USER = os.environ.get('MYSQL_USER', 'your_mysql_user')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'your_mysql_password')
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost') # Or your MySQL server IP/hostname
    MYSQL_DB = os.environ.get('MYSQL_DB', 'facial_recognition_db')
    MYSQL_PORT = os.environ.get('MYSQL_PORT', '3306')

    app.config['SQLALCHEMY_DATABASE_URI'] = \
        os.environ.get('DATABASE_URL') or \
        f'mysql+mysqlclient://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}'
    # --- End MySQL Configuration ---

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Configuration for file uploads
    # Store uploads inside the 'webapp/static/' directory to make them easily servable
    # For production, you might want a more robust solution or serve static files differently.
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/uploads/registered_photos')
    app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}


    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app) # Initialize CSRF protection
    login_manager.login_view = 'main.login' # 'main' is the blueprint name, 'login' is the route
    login_manager.login_message_category = 'info'

    from .routes import main_bp
    app.register_blueprint(main_bp)

    from .api_routes import api_bp # Import the new API blueprint
    app.register_blueprint(api_bp) # Register the API blueprint

    from .models import User # Import models here to ensure they are registered with SQLAlchemy

    with app.app_context():
        db.create_all() # Create database tables if they don't exist

    return app
