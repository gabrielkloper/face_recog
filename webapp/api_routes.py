from flask import Blueprint, request, jsonify, current_app
from .models import RegisteredPerson, AccessLog, db, get_utc_now, sao_paulo_tz
from datetime import datetime
import pytz

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/log_access', methods=['POST'])
def log_access():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid or missing JSON payload"}), 400

    person_system_id = data.get('person_system_id')
    event_type = data.get('event_type') # 'entry' or 'exit'
    timestamp_str = data.get('timestamp_utc') # Expected in ISO 8601 UTC format, e.g., "2023-10-27T10:00:00Z"

    if not all([person_system_id, event_type, timestamp_str]):
        return jsonify({"error": "Missing required fields: person_system_id, event_type, timestamp_utc"}), 400

    if event_type not in ['entry', 'exit']:
        return jsonify({"error": "Invalid event_type. Must be 'entry' or 'exit'."}), 400

    try:
        # Parse the UTC timestamp string.
        # If it ends with 'Z', Python's fromisoformat handles it directly as UTC for versions 3.7+
        # For broader compatibility or if 'Z' is not guaranteed:
        if timestamp_str.endswith('Z'):
            timestamp_utc = datetime.fromisoformat(timestamp_str[:-1] + '+00:00')
        else: # Assume it's a naive UTC string or has timezone offset
            timestamp_utc = datetime.fromisoformat(timestamp_str)
            if timestamp_utc.tzinfo is None: # If naive, assume it's UTC
                timestamp_utc = timestamp_utc.replace(tzinfo=pytz.utc)
            else: # If it has offset, convert to UTC
                timestamp_utc = timestamp_utc.astimezone(pytz.utc)

    except ValueError:
        return jsonify({"error": "Invalid timestamp_utc format. Please use ISO 8601 format (e.g., YYYY-MM-DDTHH:MM:SSZ or with offset)."}), 400

    person = RegisteredPerson.query.filter_by(person_id_system=person_system_id).first()
    if not person:
        # Optionally, you could register an "unknown" person event here if desired.
        # For now, only log events for known persons.
        return jsonify({"error": f"Person with system ID '{person_system_id}' not found."}), 404

    try:
        new_log = AccessLog(
            person_id=person.id,
            person_name=person.name, # Denormalized for convenience
            timestamp=timestamp_utc, # Already UTC
            event_type=event_type
        )
        db.session.add(new_log)
        db.session.commit()

        # Convert to SP time for the response message if needed
        timestamp_sp = timestamp_utc.astimezone(sao_paulo_tz)

        return jsonify({
            "message": "Access logged successfully.",
            "person_name": person.name,
            "event_type": event_type,
            "timestamp_sao_paulo": timestamp_sp.strftime('%Y-%m-%d %H:%M:%S %Z%z'),
            "timestamp_utc_stored": timestamp_utc.strftime('%Y-%m-%d %H:%M:%S %Z%z')
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error logging access: {e}") # Requires app logger configuration
        return jsonify({"error": "Internal server error while logging access."}), 500

# It might be good to add a simple GET /api/health or /api/ping endpoint
@api_bp.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "pong", "timestamp": get_utc_now().isoformat()}), 200
