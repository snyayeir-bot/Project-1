from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash
from db import get_db_connection
from api.api_login import generate_token, JWT_EXPIRES_DAYS
import datetime

register_bp = Blueprint('register_bp', __name__)

# ----------------------------------------------------
# REGISTER API ENDPOINT (Creates new user account)
# ----------------------------------------------------
@register_bp.route('/api/register', methods=['POST', 'GET'])
def api_register():
    if request.method == 'GET':
        return jsonify({
            "status": "success",
            "message": "Register API ready. Please send POST request with 'username' (or 'name'), 'password', and optional 'role'."
        })

    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or data.get("name") or "").strip()
    password = data.get("password") or ""
    role = (data.get("role") or "Teacher").strip()

    if not username or not password:
        return jsonify({"status": "error", "message": "សូមបញ្ចូលឈ្មោះ និងលេខសំងាត់ (Please fill in username and password)"}), 400

    if len(password) < 4:
        return jsonify({"status": "error", "message": "លេខសំងាត់ត្រូវមានយ៉ាងហោចណាស់ ៤ តួអក្សរ (Password must be at least 4 characters)"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        # Check if username already exists
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            cursor.close()
            conn.close()
            return jsonify({
                "status": "error",
                "message": f"ឈ្មោះគណនី '{username}' មានរួចហើយ (Username already exists)"
            }), 400

        # Hash password
        hashed_password = generate_password_hash(password)

        # Normalize role to match MySQL enum('Admin','Teacher','Student')
        role_map = {'admin': 'Admin', 'teacher': 'Teacher', 'student': 'Student'}
        valid_role = role_map.get(role.strip().lower(), 'Teacher')

        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
            (username, hashed_password, valid_role)
        )
        conn.commit()

        new_user_id = cursor.lastrowid
        cursor.execute("SELECT * FROM users WHERE id = %s", (new_user_id,))
        new_user = cursor.fetchone()

        # If registered as Teacher, auto create record in teachers table
        if valid_role == 'Teacher':
            try:
                cursor.execute("SELECT teacher_id FROM teachers WHERE full_name = %s", (username,))
                if not cursor.fetchone():
                    cursor.execute("SELECT MAX(teacher_id) AS max_id FROM teachers")
                    max_row = cursor.fetchone()
                    next_tch_num = (max_row['max_id'] or 0) + 1
                    auto_tch_code = f"TCH-2026-{next_tch_num:03d}"
                    cursor.execute("SELECT teacher_id FROM teachers WHERE teacher_code = %s", (auto_tch_code,))
                    if cursor.fetchone():
                        import time
                        auto_tch_code = f"TCH-2026-{int(time.time()) % 10000:04d}"

                    cursor.execute(
                        """INSERT INTO teachers (teacher_code, full_name, gender, status)
                           VALUES (%s, %s, 'Male', 'Active')""",
                        (auto_tch_code, username)
                    )
                    conn.commit()
            except Exception as e_tch:
                pass

        cursor.close()
        conn.close()

        if not new_user:
            new_user = {
                'id': new_user_id,
                'username': username,
                'name': username,
                'role': valid_role
            }

        # Generate JWT token
        token = generate_token(new_user)
        user_role = str(new_user.get('role', valid_role)).strip()
        role_lower = user_role.lower()

        if role_lower in ['admin']:
            redirect_url = '/admin-desbord'
        elif role_lower in ['teacher', 'teachers']:
            redirect_url = '/teachers-desbord'
        else:
            redirect_url = '/desbord'

        print("\n==========================================")
        print(f" [REGISTER SUCCESS] User: {username} | Role: {user_role}")
        print(f" [TOKEN]: {token}")
        print("==========================================\n")

        user_info = {k: v for k, v in new_user.items() if k != 'password'}
        if 'created_at' in user_info and isinstance(user_info['created_at'], (datetime.datetime, datetime.date)):
            user_info['created_at'] = user_info['created_at'].isoformat()

        return jsonify({
            "status": "success",
            "message": "បង្កើតគណនីបានជោគជ័យ (Account created successfully)",
            "token": token,
            "token_type": "Bearer",
            "expires_in": JWT_EXPIRES_DAYS * 24 * 3600,
            "role": user_role,
            "redirect_url": redirect_url,
            "user": user_info
        }), 201

    except Exception as e:
        if conn and conn.is_connected():
            conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500
